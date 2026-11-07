<script setup lang="ts">
import {ref,computed,useId,onMounted,onUnmounted} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import type {Api} from './api'
export interface ChatScope {kind:'selected'|'filtered'|'authorized';ids?:string[];filters?:Record<string,string>}
interface Evidence {fact_id:string;quote:string;talent_id:string;source_type:string;source_version:number}
interface AnswerCitation extends Evidence {number:number;entry_id:string;name:string}
interface Entry {id:string;talent_id:string;name:string;version:number;stale:boolean;state:string;error_code:string|null;result:{criteria:{criterion:string;state:string;evidence:Evidence[]}[]}|null}
interface Job {id:string;state:string;run_version:number;error_code:string|null;scope:ChatScope;coverage:Record<string,number>;answer:{text:string;confirmation_required:boolean;citations?:AnswerCitation[]}|null;entries:Entry[]}
interface Message {id:string;question:string;answer:Job['answer'];job:Job;scope:ChatScope}
interface Conversation {id:string;version:number;scope:ChatScope;conditions:Record<string,unknown>;pending:unknown;messages:Message[];created_at:number}
const props=defineProps<{api:Api;token:string;context:ChatScope;embedded?:boolean;scopeLabel?:string;filterLabels?:Record<string,string>}>()
const inputId=useId()
const conv=ref<Conversation|null>(null),history=ref<Conversation[]>([]),question=ref(''),busy=ref(false),job=ref<Job|null>(null),streamText=ref(''),disconnected=ref(false)
const citation=ref<{name:string;profile_version:number;fact:{category:string;content:string;source_type:string;source_version:number;locator?:unknown;source_task_id?:string};reference:Evidence;file:{id:string;name:string}|null}|null>(null),showCitation=ref(false)
// 输入区只在真正可发送时启用主按钮；Enter 发送、Shift+Enter 换行。
const jobRunning=computed(()=>!!job.value&&['queued','running'].includes(job.value.state))
const scopeCount=computed(()=>{const s=conv.value?.scope||props.context;if(s.ids?.length)return s.ids.length+' 人';return s.kind==='authorized'?'全部授权':'新建时固定'})
const canSend=computed(()=>!!question.value.trim()&&!busy.value&&!jobRunning.value&&!(!conv.value&&props.context.kind==='selected'&&!props.context.ids?.length))
const scopeFilterText=()=>{const f=(conv.value?.scope||props.context).filters||{};return Object.entries(f).filter(([,v])=>v).map(([k,v])=>(k==='kind'?'身份':k==='skill'?'技能原文包含':k==='education'?'教育原文包含':k==='requirement_id'?'应聘岗位':k==='minimum_education'?'最低已完成学历':k==='minimum_experience_years'?'最低总工作年限':'经历原文包含')+'：'+(props.filterLabels?.[k]||(k==='kind'?(v==='internal'?'内部员工':'外部候选人'):k==='minimum_experience_years'?v+'年':v))).join('，')}
const conditionText=()=>{const c=conv.value?.conditions;if(!c)return '';const parts:string[]=[];if(c.kind)parts.push(c.kind==='internal'?'内部员工':'外部候选人');if(c.skill)parts.push('技能：'+c.skill);if(c.education)parts.push('最高已完成学历：'+c.education+(c.education_op==='ge'?'及以上':''));if(c.years!=null)parts.push('总工作经验'+(c.years_op==='gt'?'超过':'至少')+c.years+'年');if(c.skill_years && typeof c.skill_years==='object')for(const [skill,years] of Object.entries(c.skill_years))parts.push(skill+'使用经验'+(c.skill_years_op==='gt'?'超过':'至少')+years+'年');if(Array.isArray(c.criteria)&&c.criteria.length)parts.push('语义判据：'+c.criteria.join('；'));return parts.join('，')||'未附加结构化条件'}
const states:Record<string,string>={queued:'待处理',running:'处理中',succeeded:'已完成',failed:'执行失败',supported:'有证据支持',unknown:'信息不足',not_supported:'有相反证据',insufficient:'结构条件信息不足',excluded:'结构条件不符合',not_retrieved:'未列入当前检索结果',pending:'待处理'}
let controller:AbortController|null=null,disposed=false,viewSerial=0,streamSerial=0,streamOffset=0
let pendingSend:{key:string;body:{version:number;question:string;confirm:boolean}}|null=null
function cancelStream(){streamSerial++;controller?.abort()}
function resetView(){const ticket=++viewSerial;cancelStream();job.value=null;streamText.value='';streamOffset=0;disconnected.value=false;pendingSend=null;showCitation.value=false;citation.value=null;return ticket}
async function run(fn:()=>Promise<void>){busy.value=true;try{await fn()}catch(e){ElMessage.error((e as Error).message)}finally{busy.value=false}}
async function loadHistory(){const result=await props.api<{items:Conversation[]}>('/chat/conversations?limit=100');if(!disposed)history.value=result.items}
async function create(scope=props.context){const ticket=resetView();conv.value=null;const result=await props.api<Conversation>('/chat/conversations','POST',scope,crypto.randomUUID());if(disposed||ticket!==viewSerial)return;conv.value=result;if(!props.embedded)await loadHistory()}
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
async function refresh(){await run(async()=>{if(conv.value)await open(conv.value.id);if(!props.embedded)await loadHistory()})}
async function retry(){await run(async()=>{const ticket=viewSerial,id=job.value!.id,version=job.value!.run_version;cancelStream();const result=await props.api<Job>(`/chat/jobs/${id}/retry`,'POST',{version});if(disposed||ticket!==viewSerial||job.value?.id!==id)return;job.value=result;streamText.value='';streamOffset=0;void stream()})}
async function source(e:Entry,r:Evidence){await run(async()=>{const ticket=viewSerial,id=job.value!.id;const result=await props.api<NonNullable<typeof citation.value>>(`/chat/jobs/${id}/entries/${e.id}/citations/${r.fact_id}`);if(disposed||ticket!==viewSerial||job.value?.id!==id)return;citation.value=result;showCitation.value=true})}
async function answerSource(r:AnswerCitation){const e=job.value?.entries.find(e=>e.id===r.entry_id&&e.talent_id===r.talent_id);if(e)await source(e,r)}
async function downloadSource(){await run(async()=>{const file=citation.value?.file;if(!file)return;const ticket=viewSerial;const response=await fetch(`/api/files/${file.id}/download`,{headers:{Authorization:`Bearer ${props.token}`}});if(!response.ok)throw new Error('原文件不可读取或授权已变化');const blob=await response.blob();if(disposed||ticket!==viewSerial)return;const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=file.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)})}
async function all(){try{await ElMessageBox.confirm('新会话将使用当前全部授权人才。确认使用这个范围？','明确范围',{confirmButtonText:'确认范围',cancelButtonText:'取消'})}catch{return}await run(()=>create({kind:'authorized'}))}
onMounted(()=>{if(!props.embedded)void run(loadHistory)});onUnmounted(()=>{disposed=true;viewSerial++;cancelStream()})
</script>
<template><section class="archive-chat" :class="{embedded}"><div class="chat-reading"><div class="title-row"><div><h2 v-if="embedded">档案问答</h2><h1 v-else>问答与历史</h1><p v-if="!embedded" class="muted">在明确范围内找人、比较、统计与追问；回答可核对来源。</p></div><el-button v-if="!embedded" @click="refresh">刷新当前权限与记录</el-button><el-tag v-else type="success" size="small">只读 · 可核对来源</el-tag></div>
<el-card v-if="embedded" class="chat-scope"><p v-if="scopeLabel">当前人才：<strong>{{scopeLabel}}</strong></p><p>问答范围：{{(conv?.scope||context).kind==='selected'?'明确选中':(conv?.scope||context).kind==='filtered'?'筛选快照':'全部授权快照'}} · {{scopeCount}}</p><p v-if="scopeFilterText()">范围筛选条件：{{scopeFilterText()}}</p><p v-if="conv" class="muted">范围已固定，追问沿用；扩大范围需确认。</p><p v-if="conv && Object.keys(conv.conditions).length" style="white-space:pre-wrap">已明确条件：{{conditionText()}}</p></el-card>
<div v-else class="scope-bar"><div class="scope-info"><span class="scope-kind">{{(conv?.scope||context).kind==='selected'?'明确选中':(conv?.scope||context).kind==='filtered'?'筛选快照':'全部授权'}}</span><strong>{{scopeCount}}</strong><span v-if="scopeLabel" class="scope-person">· {{scopeLabel}}</span></div><div class="scope-actions"><el-select placeholder="历史会话" style="width:220px" @change="(id:string)=>run(()=>open(id))"><el-option v-for="h in history" :key="h.id" :value="h.id" :data-conversation-id="h.id" :label="`${new Date(h.created_at*1000).toLocaleString()} · ${h.scope.ids?.length||0}人`"/></el-select><el-button @click="all">全部授权范围</el-button><el-button type="primary" @click="run(()=>create())">新建会话</el-button></div></div>
<p v-if="!embedded&&scopeFilterText()" class="scope-detail">范围筛选条件：{{scopeFilterText()}}</p>
<p v-if="!embedded&&conv" class="scope-detail">范围已固定，追问沿用；扩大范围需确认<template v-if="Object.keys(conv.conditions).length"> · 已明确条件：{{conditionText()}}</template></p>
<div v-if="embedded" class="qa-examples"><el-button v-for="example in ((context.ids?.length||0)===1?['有哪些技能和项目证据？','毕业院校是什么？']:['比较这些人才的项目经历','当前范围有多少人？'])" :key="example" @click="question=example">{{example}}</el-button></div><div class="chat-transcript"><el-empty v-if="!embedded&&!conv&&!job" class="chat-empty" description="从一个明确的范围开始提问；回答只使用你已获授权的档案，证据不足会直接说明" :image-size="56"/><el-empty v-if="embedded&&!conv?.messages.length&&!job" description="基于档案证据提问，证据不足时明确说明" :image-size="48"/>
<article v-for="m in conv?.messages||[]" :key="m.id" :data-job-id="m.job.id" class="chat-round"><div class="question-bubble">{{m.question}}</div><div v-if="m.job.id!==job?.id" class="previous-answer"><p v-if="m.answer" class="pre-line">{{m.answer.text}}</p><el-button text type="primary" @click="run(()=>viewRound(m.job.id))">查看本轮证据与进度</el-button></div></article>
<el-card v-if="job" data-testid="chat-job"><div class="job-status" role="status"><strong>{{states[job.state]}}</strong> · 本轮固定范围 {{job.scope.ids?.length||0}} 人<span v-if="job.coverage.total!==undefined"> · 已处理 {{job.coverage.processed}} / {{job.coverage.total}} · 信息不足 {{(job.coverage.unknown||0)+(job.coverage.insufficient||0)}} · 失败 {{job.coverage.failed||0}}</span></div><details class="chat-diagnostics"><summary>任务进度与执行详情 · {{states[job.state]}}</summary><p>任务 {{job.id}} · {{states[job.state]}} · 执行版本 {{job.run_version}}</p><p v-if="job.coverage.total!==undefined">覆盖进度 {{job.coverage.processed}} / {{job.coverage.total}}；有证据支持 {{job.coverage.supported||0}}，信息不足 {{(job.coverage.unknown||0)+(job.coverage.insufficient||0)}}，失败 {{job.coverage.failed||0}}</p></details><p class="answer-text" style="white-space:pre-wrap" data-testid="chat-answer">{{streamText||job.answer?.text}}</p><div v-if="job.answer?.citations?.length"><el-button v-for="r in job.answer.citations" :key="r.number" text @click="answerSource(r)">［{{r.number}}］{{r.name}} · 核对来源</el-button></div><p v-if="job.error_code">执行未完成：{{job.error_code}}。断线或失败不会自动重建任务。</p><el-button v-if="disconnected" @click="stream">连接原任务（不重新提问）</el-button><el-button v-if="['failed','succeeded'].includes(job.state)&&job.run_version<3&&(job.error_code || job.coverage.failed)" @click="retry">重试原任务的可恢复失败</el-button><el-button v-if="job.answer?.confirmation_required && conv?.messages.at(-1)?.job.id===job.id" type="primary" @click="send(true)">确认上述范围与判据</el-button>
<el-collapse><el-collapse-item v-for="e in job.entries" :key="e.id" :title="`${e.name} · 档案v${e.version} · ${states[e.state]||e.state}${e.stale?'（当前资料已变更）':''}`"><p v-if="e.error_code">{{e.error_code}}</p><div v-for="c in e.result?.criteria||[]" :key="c.criterion"><strong>{{c.criterion}}：{{states[c.state]}}</strong><p v-for="r in c.evidence" :key="r.fact_id+r.quote">“{{r.quote}}”<el-button text @click="source(e,r)">核对{{r.source_type==='manual'?'人工事实':'来源记录'}} · v{{r.source_version}}</el-button></p><p v-if="!c.evidence.length" class="muted">没有足够来源支持，不能据此断言具备或不具备。</p></div></el-collapse-item></el-collapse></el-card>
</div></div><div class="chat-composer"><div class="composer-box"><el-input :id="inputId" v-model="question" aria-label="向当前范围提问" type="textarea" resize="none" :autosize="{minRows:1,maxRows:6}" :placeholder="context.ids?.length===1?'向这份档案提问，如：毕业院校是什么？':'向当前范围提问，如：比较这些人的项目经历'" @keydown.enter.exact.prevent="canSend&&send()"/><div class="composer-bar"><span class="composer-hint" :title="`Enter 发送 · Shift+Enter 换行 · 当前范围 ${scopeCount}`"><span class="hint-keys">Enter 发送</span><span class="hint-sep">·</span><span class="hint-scope">范围 {{scopeCount}}</span></span><el-button class="send-button" type="primary" size="small" :loading="busy" :disabled="!canSend" @click="send()">发送</el-button></div></div><p v-if="!embedded&&!conv&&context.kind==='selected'&&!context.ids?.length" class="muted">请先从人才列表选择范围，或点击“新建全部授权范围会话”。</p></div>
<el-dialog v-model="showCitation" append-to-body title="当前权限下核对来源" width="min(800px,95vw)"><template v-if="citation"><h3>{{citation.name}} · 档案版本 {{citation.profile_version}}</h3><p>来源：{{citation.fact.source_type==='manual'?'人工维护事实':'简历来源记录'}} · 来源版本 {{citation.fact.source_version}}</p><p style="white-space:pre-wrap">{{citation.fact.content}}</p><p v-if="citation.file">原文件：{{citation.file.name}} <el-button @click="downloadSource">下载原文件核对</el-button></p><p v-if="citation.fact.locator">原文位置：{{citation.fact.locator}}</p><blockquote>{{citation.reference.quote}}</blockquote></template><p class="muted">人工事实使用事实记录与版本；不会伪造原文件。文件事实可查看来源任务与位置。</p></el-dialog></section></template>

<style scoped>
.archive-chat{display:grid;grid-template-rows:minmax(0,1fr) auto;height:calc(100dvh - 104px);min-height:320px;overflow:hidden}
.archive-chat>.chat-reading{min-height:0;overflow:auto;padding-right:2px}
.chat-reading>.el-card{margin-bottom:14px}
.chat-scope{background:var(--surface-muted);box-shadow:none;border-color:var(--border)}
.chat-scope p{font-size:12px;color:var(--text-secondary);overflow-wrap:anywhere;margin:4px 0}
.scope-bar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:10px 14px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:6px}
.scope-info{display:flex;align-items:baseline;gap:6px;font-size:13px;color:var(--text-secondary);min-width:0}
.scope-info strong{font-size:15px;font-weight:600;color:var(--text)}
.scope-kind{font-size:12px;color:var(--text-tertiary)}
.scope-person{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:260px;font-size:12px;color:var(--text-secondary)}
.scope-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.scope-actions .el-button{margin:0}
.scope-detail{margin:0 0 6px;font-size:12px;color:var(--text-tertiary);line-height:1.6}
.chat-empty{padding:48px 0 24px}
.chat-composer{margin:14px 0 0;flex-shrink:0;min-width:0}
.composer-box{border:1px solid var(--border-strong);border-radius:10px;background:var(--surface);padding:10px 10px 8px 12px;transition:border-color .15s,box-shadow .15s}
.composer-box:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px #2f5bea14}
.composer-box :deep(.el-textarea__inner){box-shadow:none!important;border:0;background:transparent;padding:0;font-size:13px;line-height:1.7;resize:none;min-height:42px;color:var(--text)}
.composer-box :deep(.el-textarea__inner::placeholder){color:var(--text-tertiary)}
.composer-bar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:6px}
.composer-hint{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--text-tertiary);overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.hint-sep{color:var(--border-strong)}
.hint-scope{overflow:hidden;text-overflow:ellipsis}
.send-button{min-height:28px;height:28px;padding:0 14px;border-radius:6px;font-size:12px;flex-shrink:0}
.chat-composer>p{margin:6px 0 0}
.embedded{display:grid;grid-template-rows:minmax(0,1fr) auto;height:100%;min-height:0;overflow:hidden}
.embedded .chat-reading{min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:0 2px}
.embedded .title-row{display:flex;justify-content:space-between;margin:0 0 10px;align-items:center;gap:10px;flex-shrink:0}
.embedded h2{font-size:14px;margin:0;font-weight:600}
.embedded .el-card{--el-card-padding:12px}
.embedded .chat-scope{flex-shrink:0;border-radius:8px;background:transparent;border-style:dashed}
.embedded .chat-scope p{font-size:11px;margin:3px 0}
.embedded .chat-transcript{min-height:0;overflow:visible;padding:0 2px}
.chat-transcript>.el-card{margin-bottom:12px}
.embedded .chat-composer{min-width:0;margin:10px 0 0;padding:0;border:0;background:transparent;box-shadow:none;position:static}
.job-status{font-size:12px;line-height:1.7;margin-bottom:8px;color:var(--text-secondary)}
.qa-examples{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 10px}
.qa-examples .el-button{margin:0;font-size:11px;height:auto;min-height:28px;white-space:normal;line-height:1.5;padding:6px 10px;border-radius:6px;color:var(--text-secondary)}
.qa-examples .el-button:hover{color:var(--accent);border-color:var(--accent)}
.embedded p{overflow-wrap:anywhere}
.chat-round{display:flex;flex-direction:column;gap:8px;margin:14px 0}
.question-bubble{align-self:flex-end;max-width:88%;background:var(--accent-gradient);color:#fff;border-radius:14px 14px 4px 14px;padding:9px 14px;font-size:13px;line-height:1.65;overflow-wrap:anywhere}
.previous-answer{align-self:flex-start;max-width:94%;background:var(--surface);border:1px solid var(--border);box-shadow:var(--shadow);border-radius:4px 14px 14px 14px;padding:11px 14px;font-size:13px}
.previous-answer p{margin:0 0 6px}
/* 当前轮同样按对话流呈现：答案本身是左侧气泡，状态与证据作为气泡外的辅助信息。 */
.chat-transcript>div[data-testid="chat-job"]{background:transparent;border:0;box-shadow:none;--el-card-padding:0}
.chat-transcript>div[data-testid="chat-job"] :deep(.el-card__body){padding:0}
.answer-text{background:var(--surface);border:1px solid var(--border);border-radius:4px 14px 14px 14px;padding:12px 14px;font-size:13px;line-height:1.85;max-width:min(92%,760px);margin:8px 0}
.chat-diagnostics{font-size:11px;color:var(--text-tertiary);margin:8px 0}
.chat-diagnostics summary{cursor:pointer}
.archive-chat :deep(.el-collapse-item__header){height:auto;min-height:40px;line-height:1.6;overflow-wrap:anywhere;font-size:12px}
.archive-chat :deep(.el-card__body){overflow-wrap:anywhere}
.embedded :deep(.el-empty__description p){font-size:12px;line-height:1.8}
.embedded :deep(.el-empty){padding:28px 8px}
.embedded .title-row .el-tag{font-size:10px}
@media(max-height:650px){.embedded .chat-composer{margin-top:8px}.composer-box :deep(.el-textarea__inner){min-height:36px}}
</style>
