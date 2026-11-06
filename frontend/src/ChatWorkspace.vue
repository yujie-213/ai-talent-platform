<script setup lang="ts">
import {ref,onMounted,onUnmounted} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import type {Api} from './api'
export interface ChatScope {kind:'selected'|'filtered'|'authorized';ids?:string[];filters?:Record<string,string>}
interface Evidence {fact_id:string;quote:string;talent_id:string;source_type:string;source_version:number}
interface Entry {id:string;talent_id:string;name:string;version:number;stale:boolean;state:string;error_code:string|null;result:{criteria:{criterion:string;state:string;evidence:Evidence[]}[]}|null}
interface Job {id:string;state:string;run_version:number;error_code:string|null;scope:ChatScope;coverage:Record<string,number>;answer:{text:string;confirmation_required:boolean}|null;entries:Entry[]}
interface Message {id:string;question:string;answer:Job['answer'];job:Job;scope:ChatScope}
interface Conversation {id:string;version:number;scope:ChatScope;conditions:Record<string,unknown>;pending:unknown;messages:Message[];created_at:number}
const props=defineProps<{api:Api;token:string;context:ChatScope}>()
const conv=ref<Conversation|null>(null),history=ref<Conversation[]>([]),question=ref(''),busy=ref(false),job=ref<Job|null>(null),streamText=ref(''),disconnected=ref(false)
const citation=ref<{name:string;profile_version:number;fact:{category:string;content:string;source_type:string;source_version:number;locator?:unknown;source_task_id?:string};reference:Evidence;file:{id:string;name:string}|null}|null>(null),showCitation=ref(false)
const scopeFilterText=()=>{const f=(conv.value?.scope||props.context).filters||{};return Object.entries(f).filter(([,v])=>v).map(([k,v])=>(k==='kind'?'身份':k==='skill'?'技能原文包含':k==='education'?'教育原文包含':'经历原文包含')+'：'+(k==='kind'?(v==='internal'?'内部员工':'外部候选人'):v)).join('，')}
const conditionText=()=>{const c=conv.value?.conditions;if(!c)return '';const parts:string[]=[];if(c.kind)parts.push(c.kind==='internal'?'内部员工':'外部候选人');if(c.skill)parts.push('技能：'+c.skill);if(c.education)parts.push('最高已完成学历：'+c.education+(c.education_op==='ge'?'及以上':''));if(c.years!=null)parts.push('总工作经验'+(c.years_op==='gt'?'超过':'至少')+c.years+'年');if(c.skill_years && typeof c.skill_years==='object')for(const [skill,years] of Object.entries(c.skill_years))parts.push(skill+'使用经验'+(c.skill_years_op==='gt'?'超过':'至少')+years+'年');if(Array.isArray(c.criteria)&&c.criteria.length)parts.push('语义判据：'+c.criteria.join('；'));return parts.join('，')||'未附加结构化条件'}
const states:Record<string,string>={queued:'待处理',running:'处理中',succeeded:'已完成',failed:'执行失败',supported:'有证据支持',unknown:'信息不足',not_supported:'有相反证据',insufficient:'结构条件信息不足',excluded:'结构条件不符合',not_retrieved:'未列入当前检索结果',pending:'待处理'}
let controller:AbortController|null=null,disposed=false,viewSerial=0,streamSerial=0,streamOffset=0
let pendingSend:{key:string;body:{version:number;question:string;confirm:boolean}}|null=null
function cancelStream(){streamSerial++;controller?.abort()}
function resetView(){const ticket=++viewSerial;cancelStream();job.value=null;streamText.value='';streamOffset=0;disconnected.value=false;pendingSend=null;showCitation.value=false;citation.value=null;return ticket}
async function run(fn:()=>Promise<void>){busy.value=true;try{await fn()}catch(e){ElMessage.error((e as Error).message)}finally{busy.value=false}}
async function loadHistory(){const result=await props.api<{items:Conversation[]}>('/chat/conversations?limit=100');if(!disposed)history.value=result.items}
async function create(scope=props.context){const ticket=resetView();conv.value=null;const result=await props.api<Conversation>('/chat/conversations','POST',scope,crypto.randomUUID());if(disposed||ticket!==viewSerial)return;conv.value=result;await loadHistory()}
async function open(id:string){const ticket=resetView();conv.value=null;const result=await props.api<Conversation>('/chat/conversations/'+id);if(disposed||ticket!==viewSerial)return;conv.value=result;const last=result.messages.at(-1);if(last?.job){const data=await props.api<Job>('/chat/jobs/'+last.job.id);if(disposed||ticket!==viewSerial)return;job.value=data;if(['queued','running'].includes(data.state))void stream()}}
async function viewRound(id:string){const ticket=resetView();const result=await props.api<Job>('/chat/jobs/'+id);if(disposed||ticket!==viewSerial)return;job.value=result;if(['queued','running'].includes(result.state))void stream()}
async function send(confirm=false){await run(async()=>{
  if(!conv.value){const before=viewSerial;await create();if(viewSerial!==before+1||!conv.value)return}
  const ticket=viewSerial,cid=conv.value!.id,body={version:conv.value!.version,question:confirm?'确认范围与判据':question.value,confirm}
  if(!body.question.trim())return
  cancelStream()
  if(!pendingSend||JSON.stringify(pendingSend.body)!==JSON.stringify(body))pendingSend={key:crypto.randomUUID(),body}
  const result=await props.api<Job>(`/chat/conversations/${cid}/messages`,'POST',body,pendingSend.key)
  if(disposed||ticket!==viewSerial)return
  job.value=result;pendingSend=null;question.value='';streamText.value='';streamOffset=0
  const updated=await props.api<Conversation>('/chat/conversations/'+cid)
  if(disposed||ticket!==viewSerial)return
  conv.value=updated;void stream()
})}
async function stream(){
  if(!job.value||!conv.value)return
  cancelStream();const serial=streamSerial,id=job.value.id,cid=conv.value.id,ticket=viewSerial,ownController=new AbortController();controller=ownController;disconnected.value=false
  const active=()=>!disposed&&serial===streamSerial&&ticket===viewSerial&&job.value?.id===id
  let offset=streamOffset
  try{
    while(active()){
      const res=await fetch(`/api/chat/jobs/${id}/events?offset=${offset}`,{headers:{Authorization:`Bearer ${props.token}`},signal:ownController.signal})
      if(!active())return
      if(!res.ok)throw new Error('任务流不可读取，请刷新检查当前权限')
      const reader=res.body!.getReader(),decoder=new TextDecoder();let buffer='',reconnect=false
      while(active()){
        const {done,value}=await reader.read();if(!active())return;if(done)break
        buffer+=decoder.decode(value,{stream:true});let end:number
        while((end=buffer.indexOf('\n\n'))>=0){
          if(!active())return
          const event=buffer.slice(0,end);buffer=buffer.slice(end+2)
          const type=event.match(/^event: (.+)$/m)?.[1],data=JSON.parse(event.match(/^data: (.*)$/m)?.[1]||'{}')
          if(type==='revoked'){job.value=null;conv.value=null;streamText.value='';streamOffset=0;throw new Error('授权或来源已变化，旧内容已隐藏')}
          if(type==='chunk'){streamText.value+=data.text;offset=data.offset;streamOffset=offset}
          if(type==='entry'&&job.value){const i=job.value.entries.findIndex(e=>e.id===data.id);if(i<0)job.value.entries.push(data);else job.value.entries[i]=data}
          if(type==='progress'&&job.value){job.value.state=data.state;job.value.coverage=data.coverage}
          if(type==='done'){
            const result=await props.api<Job>('/chat/jobs/'+id);if(!active())return;job.value=result
            const updated=await props.api<Conversation>('/chat/conversations/'+cid);if(!active())return;conv.value=updated;return
          }
          if(type==='reconnect')reconnect=true
        }
      }
      if(!reconnect)break
    }
  }catch(e){if((e as Error).name==='AbortError'||disposed||serial!==streamSerial||ticket!==viewSerial)return;ElMessage.error((e as Error).message)}
  if(active())disconnected.value=true
}
async function refresh(){await run(async()=>{if(conv.value)await open(conv.value.id);await loadHistory()})}
async function retry(){await run(async()=>{const ticket=viewSerial,id=job.value!.id,version=job.value!.run_version;cancelStream();const result=await props.api<Job>(`/chat/jobs/${id}/retry`,'POST',{version});if(disposed||ticket!==viewSerial||job.value?.id!==id)return;job.value=result;streamText.value='';streamOffset=0;void stream()})}
async function source(e:Entry,r:Evidence){await run(async()=>{const ticket=viewSerial,id=job.value!.id;const result=await props.api<NonNullable<typeof citation.value>>(`/chat/jobs/${id}/entries/${e.id}/citations/${r.fact_id}`);if(disposed||ticket!==viewSerial||job.value?.id!==id)return;citation.value=result;showCitation.value=true})}
async function downloadSource(){await run(async()=>{const file=citation.value?.file;if(!file)return;const ticket=viewSerial;const response=await fetch(`/api/files/${file.id}/download`,{headers:{Authorization:`Bearer ${props.token}`}});if(!response.ok)throw new Error('原文件不可读取或授权已变化');const blob=await response.blob();if(disposed||ticket!==viewSerial)return;const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=file.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)})}
async function all(){try{await ElMessageBox.confirm('新会话将使用当前全部授权人才。确认使用这个范围？','明确范围',{confirmButtonText:'确认范围',cancelButtonText:'取消'})}catch{return}await run(()=>create({kind:'authorized'}))}
onMounted(()=>run(loadHistory));onUnmounted(()=>{disposed=true;viewSerial++;cancelStream()})
</script>
<template><section class="archive-chat"><div class="title-row"><div><h1>档案聊天</h1><p class="muted">直接找人、问单人、比较、统计或追问。聊天只读，技能声明不等于测评结果。</p></div><el-button @click="refresh">刷新当前权限与记录</el-button></div>
<el-card><el-button @click="run(()=>create())">按当前页面上下文新建会话</el-button><el-button @click="all">新建全部授权范围会话</el-button><el-select placeholder="打开历史会话" @change="(id:string)=>run(()=>open(id))" style="width:340px"><el-option v-for="h in history" :key="h.id" :value="h.id" :label="`${new Date(h.created_at*1000).toLocaleString()} · ${h.scope.ids?.length||0}人`"/></el-select><p>当前范围：{{(conv?.scope||context).kind==='selected'?'明确选中':(conv?.scope||context).kind==='filtered'?'筛选快照':'全部授权快照'}} · {{(conv?.scope||context).ids?.length??'将在新建时固定'}} 人</p><p v-if="scopeFilterText()">范围筛选条件：{{scopeFilterText()}}</p><p v-if="conv" class="muted">范围在新建时固定；追问继承条件。扩大范围或松开条件需明确确认，新资料版本会显示。</p><p v-if="conv && Object.keys(conv.conditions).length" style="white-space:pre-wrap">已明确条件：{{conditionText()}}</p></el-card>
<el-card v-for="m in conv?.messages||[]" :key="m.id" :data-job-id="m.job.id"><strong>你：{{m.question}}</strong><p v-if="m.answer && m.job.id!==job?.id">{{m.answer.text}}</p><el-button v-if="m.job.id!==job?.id" text @click="run(()=>viewRound(m.job.id))">查看该轮进度、逐人证据与版本</el-button></el-card>
<el-card v-if="job" data-testid="chat-job"><p>该轮固定范围 {{job.scope.ids?.length||0}} 人</p><p>任务 {{job.id}} · {{states[job.state]}} · 执行版本 {{job.run_version}}</p><p v-if="job.coverage.total!==undefined">覆盖进度 {{job.coverage.processed}} / {{job.coverage.total}}；有证据支持 {{job.coverage.supported||0}}，信息不足 {{(job.coverage.unknown||0)+(job.coverage.insufficient||0)}}，失败 {{job.coverage.failed||0}}</p><p style="white-space:pre-wrap" data-testid="chat-answer">{{streamText||job.answer?.text}}</p><p v-if="job.error_code">执行未完成：{{job.error_code}}。断线或失败不会自动重建任务。</p><el-button v-if="disconnected" @click="stream">连接原任务（不重新提问）</el-button><el-button v-if="['failed','succeeded'].includes(job.state)&&job.run_version<3&&(job.error_code || job.coverage.failed)" @click="retry">重试原任务的可恢复失败</el-button><el-button v-if="job.answer?.confirmation_required && conv?.messages.at(-1)?.job.id===job.id" type="primary" @click="send(true)">确认上述范围与判据</el-button>
<el-collapse><el-collapse-item v-for="e in job.entries" :key="e.id" :title="`${e.name} · 档案v${e.version} · ${states[e.state]||e.state}${e.stale?'（当前资料已变更）':''}`"><p v-if="e.error_code">{{e.error_code}}</p><div v-for="c in e.result?.criteria||[]" :key="c.criterion"><strong>{{c.criterion}}：{{states[c.state]}}</strong><p v-for="r in c.evidence" :key="r.fact_id+r.quote">“{{r.quote}}”<el-button text @click="source(e,r)">核对{{r.source_type==='manual'?'人工事实':'来源记录'}} · v{{r.source_version}}</el-button></p><p v-if="!c.evidence.length" class="muted">没有足够来源支持，不能据此断言具备或不具备。</p></div></el-collapse-item></el-collapse></el-card>
<el-input v-model="question" type="textarea" placeholder="例如：这些人中有多少位本科、3年以上Python经验？或：比较这几位的RAG生产落地经历" :rows="3"/><el-button type="primary" :loading="busy" :disabled="!!job&&['queued','running'].includes(job.state)" @click="send()">发送</el-button>
<el-dialog v-model="showCitation" title="当前权限下核对来源" width="min(800px,95vw)"><template v-if="citation"><h3>{{citation.name}} · 档案版本 {{citation.profile_version}}</h3><p>来源：{{citation.fact.source_type==='manual'?'人工维护事实':'简历来源记录'}} · 来源版本 {{citation.fact.source_version}}</p><p style="white-space:pre-wrap">{{citation.fact.content}}</p><p v-if="citation.file">原文件：{{citation.file.name}} <el-button @click="downloadSource">下载原文件核对</el-button></p><p v-if="citation.fact.locator">原文位置：{{citation.fact.locator}}</p><blockquote>{{citation.reference.quote}}</blockquote></template><p class="muted">人工事实使用事实记录与版本；不会伪造原文件。文件事实可查看来源任务与位置。</p></el-dialog></section></template>
