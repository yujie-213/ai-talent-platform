<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Api } from './api'
import MatchWorkspace from './MatchWorkspace.vue'
interface CatalogItem { id:string; name?:string; department_id?:string; position_id?:string }
interface Draft {
  department_position_id:string; title:string; location:string; responsibilities:string; description:string; benefits:string
  salary:{mode:'range'|'negotiable';minimum:number|null;maximum:number|null;currency:string;period:string}|null
  conditions:{required_skills:string[];preferred_skills:string[];minimum_education:string;minimum_experience_years:number|null;skill_experience_years?:Record<string,number|undefined>}|null
  jd_text?:string
}
interface Suggestion {field:string;value:unknown;quote:string;source:'jd'|'proposal'}
interface Requirement {id:string;status:string;version:number;active_version:number|null;draft:Draft;versions?:{number:number;snapshot:Draft;created_at:number}[]}
const props = defineProps<{api:Api;canWrite:boolean;canTalentWrite?:boolean;entry?:{id:string;runId?:string;serial:number};catalog:Record<string,CatalogItem[]>}>()
const emit=defineEmits<{open:[id:string];task:[id:string]}>()
const items=ref<Requirement[]>([]), selected=ref<Requirement|null>(null), total=ref(0), currentPage=ref(1), busy=ref(false)
const panel=ref('overview')
const overview=computed(()=>selected.value?.versions?.find(v=>v.number===selected.value?.active_version)?.snapshot||selected.value?.draft)
const confirmed=ref(false), key=ref(crypto.randomUUID()), department=ref(''), required=ref(''), preferred=ref('')
const draft=ref<Draft>(empty())
const baseline=ref('')
const formState=()=>JSON.stringify([draft.value,required.value,preferred.value])
const dirty=computed(()=>formState()!==baseline.value)
const assistBusy=ref(false), suggestions=ref<Suggestion[]>([]), issues=ref<string[]>([])
let viewRequest=0
let formGeneration=0, pasteTimer:ReturnType<typeof setTimeout>|undefined
const fieldRevisions:Record<string,number>={}
function touch(event:Event) {
  confirmed.value=false
  const target=event.target
  const field=target instanceof Element?target.closest('[data-jd-field]')?.getAttribute('data-jd-field'):null
  if(field)fieldRevisions[field]=(fieldRevisions[field]||0)+1
}
const fieldNames:Record<string,string>={title:'需求名称',location:'工作地点',salary:'薪资',responsibilities:'岗位职责',description:'任职要求',benefits:'福利','conditions.required_skills':'必备技能','conditions.preferred_skills':'加分技能','conditions.minimum_education':'最低学历','conditions.minimum_experience_years':'最低工作年限','conditions.skill_experience_years':'技能最低年限'}
const states:Record<string,string>={draft:'草稿',active:'有效',disabled:'已停用'}
function empty():Draft {return {department_position_id:'',title:'',location:'',responsibilities:'',description:'',benefits:'',jd_text:'',salary:{mode:'range',minimum:null,maximum:null,currency:'CNY',period:'month'},conditions:{required_skills:[],preferred_skills:[],minimum_education:'不限',minimum_experience_years:null,skill_experience_years:{}}}}
const positions=computed(()=>(props.catalog.department_positions||[]).filter(p=>p.department_id===department.value))
function positionName(id?:string) {return props.catalog.positions?.find(p=>p.id===id)?.name||id}
async function run(fn:()=>Promise<void>) {busy.value=true;try {await fn()} catch(e) {ElMessage.error((e as Error).message)} finally {busy.value=false}}
async function load() {const data=await props.api<{items:Requirement[];total:number}>(`/requirements?offset=${(currentPage.value-1)*20}&limit=20`);items.value=data.items;total.value=data.total}
function open(item:Requirement) {formGeneration++;suggestions.value=[];issues.value=[];selected.value=item;draft.value=JSON.parse(JSON.stringify(item.draft));draft.value.jd_text ||= ''; const dp=props.catalog.department_positions?.find(p=>p.id===item.draft.department_position_id); department.value=dp?.department_id||'';required.value=draft.value.conditions?.required_skills.join('、')||'';preferred.value=draft.value.conditions?.preferred_skills.join('、')||'';draft.value.salary ||= empty().salary; draft.value.conditions ||= empty().conditions;draft.value.conditions!.skill_experience_years ||= {};confirmed.value=false;baseline.value=formState()}
async function close() {if(dirty.value&&canEdit()){try{await ElMessageBox.confirm('表单有未保存修改，返回将放弃这些修改。','离开岗位编辑',{confirmButtonText:'放弃修改并返回',cancelButtonText:'继续编辑',type:'warning'})}catch{return}}formGeneration++;viewRequest++;selected.value=null;if(pasteTimer)clearTimeout(pasteTimer)}
function canEdit(){return props.canWrite&&panel.value==='edit'}
function newItem() {open({id:'',status:'draft',version:1,active_version:null,draft:empty(),versions:[]});key.value=crypto.randomUUID();panel.value='edit'}
async function view(item:Requirement) {const ticket=++viewRequest;await run(async()=>{const data=await props.api<Requirement>(`/requirements/${item.id}`);if(ticket!==viewRequest)return;open(data);panel.value='overview'})}
function body():Draft {const value=JSON.parse(JSON.stringify(draft.value)) as Draft; if(value.conditions) {value.conditions.required_skills=required.value.split(/[、,，\n]/).map(s=>s.trim()).filter(Boolean);value.conditions.preferred_skills=preferred.value.split(/[、,，\n]/).map(s=>s.trim()).filter(Boolean);value.conditions.skill_experience_years=Object.fromEntries(Object.entries(value.conditions.skill_experience_years||{}).filter(([k,v])=>value.conditions!.required_skills.includes(k)&&v!=null))} if(value.salary?.mode==='negotiable') {value.salary.minimum=null;value.salary.maximum=null} else if(value.salary?.minimum==null&&value.salary?.maximum==null)value.salary=null;return value}
function fieldValue(value:Draft, field:string):unknown {if(field.startsWith('conditions.'))return value.conditions?.[field.split('.')[1] as keyof NonNullable<Draft['conditions']>];return value[field as keyof Draft]}
function display(value:unknown) {if(value==null)return '未填写';if(Array.isArray(value))return value.join('、');if(typeof value==='object')return JSON.stringify(value);return String(value)}
function apply(s:Suggestion) {
  if(s.field==='conditions.required_skills')required.value=(s.value as string[]).join('、')
  else if(s.field==='conditions.preferred_skills')preferred.value=(s.value as string[]).join('、')
  else if(s.field.startsWith('conditions.')&&draft.value.conditions)Object.assign(draft.value.conditions,{[s.field.split('.')[1]!]:s.value})
  else Object.assign(draft.value,{[s.field]:s.value})
  confirmed.value=false
  suggestions.value=suggestions.value.filter(item=>item!==s)
}
async function assist(mode:'extract'|'improve') {
  if(!selected.value||assistBusy.value)return
  if(!draft.value.department_position_id) {ElMessage.info('请先选择部门岗位，JD原文已保留');return}
  const generation=formGeneration, before=body(), item=selected.value, revisions={...fieldRevisions}
  assistBusy.value=true
  try {
    const result=await props.api<{suggestions:Suggestion[];issues:string[]}>('/requirements/assist','POST',{
      mode,draft:before,...(item.id?{requirement_id:item.id,version:item.version}:{})})
    if(generation!==formGeneration||!selected.value)return
    if(before.jd_text!==draft.value.jd_text||before.department_position_id!==draft.value.department_position_id) {ElMessage.info('JD或部门岗位已变更，请重新提取');return}
    suggestions.value=[];issues.value=result.issues
    for(const suggestion of result.suggestions) {
      const previous=fieldValue(before,suggestion.field), current=fieldValue(body(),suggestion.field)
      // 自动回填只针对提取时为空、返回时仍为空的事实；条件始终显式核对。
      if(mode==='extract'&&suggestion.source==='jd'&&!suggestion.field.startsWith('conditions.')
         &&(fieldRevisions[suggestion.field]||0)===(revisions[suggestion.field]||0)
         &&(previous==null||previous==='')&&JSON.stringify(current)===JSON.stringify(previous))apply(suggestion)
      else if(JSON.stringify(current)!==JSON.stringify(suggestion.value))suggestions.value.push(suggestion)
    }
    ElMessage.success('JD建议已返回，请核对差异并保存草稿')
  } catch(e) {if(generation===formGeneration)ElMessage.error((e as Error).message)}
  finally {assistBusy.value=false}
}
function queueExtract() {if(pasteTimer)clearTimeout(pasteTimer);pasteTimer=setTimeout(()=>void assist('extract'),500)}
async function save() {await run(async()=>{const item=selected.value!,generation=formGeneration;const saved=await props.api<Requirement>(item.id?`/requirements/${item.id}`:'/requirements',item.id?'PUT':'POST',item.id?{...body(),version:item.version}:body(),item.id?undefined:key.value);if(generation===formGeneration&&selected.value?.id===item.id)open(saved);await load();ElMessage.success('草稿已保存')})}
async function transition(activate:boolean) {if(!activate){try{await ElMessageBox.confirm('停用后不能发起新匹配，已有版本与结果保留。','停用岗位需求',{confirmButtonText:'确认停用',cancelButtonText:'取消',type:'warning'})}catch{return}}await run(async()=>{const item=selected.value!,generation=formGeneration;const saved=await props.api<Requirement>(`/requirements/${item.id}/${activate?'activate':'disable'}`,'POST',activate?{version:item.version,confirmed:confirmed.value}:{version:item.version});if(generation===formGeneration&&selected.value?.id===item.id)open(saved);await load()})}
async function openEntry(){const entry=props.entry;if(!entry)return;const ticket=++viewRequest;const data=await props.api<Requirement>(`/requirements/${entry.id}`);if(ticket!==viewRequest||props.entry?.serial!==entry.serial)return;open(data);panel.value=entry.runId?'matches':'overview'}
watch(()=>props.entry?.serial,()=>void run(openEntry))
onMounted(()=>void run(async()=>{await load();await openEntry()}))
onBeforeUnmount(()=>{formGeneration++;viewRequest++;if(pasteTimer)clearTimeout(pasteTimer)})
</script>

<template>
  <section class="jobs-workspace">
  <template v-if="!selected"><div class="title-row"><h1>岗位与匹配</h1><el-button v-if="canWrite" type="primary" @click="newItem">新建需求</el-button></div>
  <el-card v-loading="busy"><el-table :data="items" @row-click="view"><el-table-column label="名称"><template #default="s">{{s.row.draft.title||'未命名草稿'}}</template></el-table-column><el-table-column label="部门"><template #default="s">{{catalog.departments.find(d=>d.id===s.row.department_id)?.name||'—'}}</template></el-table-column><el-table-column label="公司岗位"><template #default="s">{{positionName(catalog.department_positions.find(p=>p.id===s.row.draft.department_position_id)?.position_id)}}</template></el-table-column><el-table-column label="状态"><template #default="s">{{states[s.row.status]}}</template></el-table-column><el-table-column prop="active_version" label="有效版本"/><el-table-column prop="version" label="编辑版本"/></el-table><el-empty v-if="!items.length" description="当前授权范围暂无岗位需求"/><el-pagination v-model:current-page="currentPage" :total="total" :page-size="20" layout="prev,pager,next" @current-change="()=>run(load)"/></el-card>
  </template>
  <section v-else class="job-workspace-detail">
    <div class="object-heading"><el-button @click="close">← 返回岗位列表</el-button><div class="object-title"><h1>{{selected.draft.title||'新建岗位需求'}}</h1><span class="muted">{{states[selected.status]}} · 有效版本 {{selected.active_version??'尚无'}} · 草稿 v{{selected.version}}</span></div><el-button v-if="canWrite&&selected.id&&panel!=='edit'" @click="panel='edit'">编辑岗位 / JD</el-button></div>
    <el-tabs v-model="panel" class="workspace-tabs"><el-tab-pane label="岗位概览" name="overview" :disabled="!selected.id"/><el-tab-pane label="匹配结果" name="matches" :disabled="!selected.id"/><el-tab-pane label="版本历史" name="history" :disabled="!selected.id"/><el-tab-pane v-if="canWrite" label="编辑 / JD 辅助" name="edit"/></el-tabs>
    <section v-if="panel==='overview'&&overview" class="job-overview">
      <el-alert v-if="selected.status!=='active'" type="warning" :closable="false" title="当前岗位未生效或已停用，可以查看历史；发起匹配前须确认有效版本。"/>
      <div class="overview-facts"><div><span>工作地点</span><strong>{{overview.location||'未填写'}}</strong></div><div><span>薪资</span><strong>{{overview.salary?.mode==='negotiable'?'面议':overview.salary?`${overview.salary.minimum??'—'} – ${overview.salary.maximum??'—'} ${overview.salary.currency} / ${{month:'月',year:'年',hour:'小时'}[overview.salary.period]||overview.salary.period}`:'未填写'}}</strong></div><div><span>最低学历 / 总工作年限</span><strong>{{overview.conditions?.minimum_education||'不限'}} · {{overview.conditions?.minimum_experience_years==null?'年限不限':overview.conditions.minimum_experience_years+' 年及以上'}}</strong></div></div>
      <div class="two-col"><el-card><h2>岗位职责</h2><p class="pre-line">{{overview.responsibilities||'未填写'}}</p><h3>任职要求</h3><p class="pre-line">{{overview.description||'未填写'}}</p></el-card><el-card><h2>匹配条件</h2><h3>必备技能</h3><div class="tag-list"><el-tag v-for="skill in overview.conditions?.required_skills||[]" :key="skill">{{skill}}<template v-if="overview.conditions?.skill_experience_years?.[skill]!=null"> · {{overview.conditions.skill_experience_years[skill]}} 年</template></el-tag><span v-if="!overview.conditions?.required_skills?.length" class="muted">不限</span></div><h3>加分技能</h3><div class="tag-list"><el-tag v-for="skill in overview.conditions?.preferred_skills||[]" :key="skill" type="info">{{skill}}</el-tag><span v-if="!overview.conditions?.preferred_skills?.length" class="muted">未设置</span></div><h3>福利</h3><p class="pre-line">{{overview.benefits||'未填写'}}</p></el-card></div>
    </section>
    <section v-show="panel==='edit'" class="job-editor">
      <el-alert type="info" :closable="false" title="保存草稿后核对并确认生效；未生效修改不会改变原有效版本和匹配历史。"/>
      <el-form label-position="top" :disabled="!canWrite||busy" @input="touch" @change="touch">
        <el-form-item label="部门"><el-select v-model="department" :disabled="!!selected.id" @change="draft.department_position_id='' "><el-option v-for="d in catalog.departments" :key="d.id" :label="d.name" :value="d.id"/></el-select></el-form-item>
        <el-form-item label="部门岗位"><el-select v-model="draft.department_position_id" :disabled="!!selected.id"><el-option v-for="p in positions" :key="p.id" :label="positionName(p.position_id)" :value="p.id"/></el-select><small>没有所需岗位时，由获授权人员在基础资料中维护。</small></el-form-item>
        <el-form-item label="JD原文或零散需求（粘贴后自动提取，原文随草稿保存）"><el-input v-model="draft.jd_text" type="textarea" :rows="5" maxlength="20000" data-testid="jd-source" @paste="queueExtract"/></el-form-item>
        <div v-if="canWrite"><el-button :loading="assistBusy" :disabled="assistBusy||!draft.jd_text?.trim()" @click="assist('extract')">提取JD / 重试</el-button><el-button :disabled="assistBusy" @click="assist('improve')">AI辅助完善</el-button><small>空字段可自动回填；冲突和条件建议由你采纳。辅助失败不影响手工填写。</small></div>
        <el-alert v-for="issue in issues" :key="issue" :title="issue" type="warning" :closable="false"/>
        <el-card v-for="s in suggestions" :key="s.field" data-testid="jd-suggestion"><strong>{{fieldNames[s.field]}} · {{s.source==='jd'?'原文提取差异':'AI提议，需确认'}}</strong><p>当前：{{display(fieldValue(body(),s.field))}}</p><p>建议：{{display(s.value)}}</p><blockquote v-if="s.quote">{{s.quote}}</blockquote><el-button @click="apply(s)">采纳此项</el-button><el-button @click="suggestions=suggestions.filter(item=>item!==s)">保留当前</el-button></el-card>
        <el-form-item label="需求名称" data-jd-field="title"><el-input v-model="draft.title" maxlength="100"/></el-form-item>
        <el-form-item label="工作地点 / 远程安排" data-jd-field="location"><el-input v-model="draft.location" maxlength="300"/></el-form-item>
        <template v-if="draft.salary"><el-form-item label="薪资" data-jd-field="salary"><el-select v-model="draft.salary.mode"><el-option label="明确区间" value="range"/><el-option label="面议" value="negotiable"/></el-select><template v-if="draft.salary.mode==='range'"><el-input-number v-model="draft.salary.minimum" :min="0" placeholder="下限"/><el-input-number v-model="draft.salary.maximum" :min="0" placeholder="上限"/><el-select v-model="draft.salary.currency"><el-option v-for="c in ['CNY','USD','EUR']" :key="c" :value="c"/></el-select><el-select v-model="draft.salary.period"><el-option label="月薪" value="month"/><el-option label="年薪" value="year"/><el-option label="时薪" value="hour"/></el-select></template></el-form-item></template>
        <el-form-item label="岗位职责" data-jd-field="responsibilities"><el-input v-model="draft.responsibilities" type="textarea" :rows="3" maxlength="12000"/></el-form-item>
        <el-form-item label="任职要求正文" data-jd-field="description"><el-input v-model="draft.description" type="textarea" :rows="3" maxlength="12000"/></el-form-item>
        <template v-if="draft.conditions"><el-form-item label="必备技能（顿号或逗号分隔，留空表示无技能限制）"><el-input v-model="required"/></el-form-item><el-form-item label="加分技能（不作为硬性淘汰依据）"><el-input v-model="preferred"/></el-form-item><template v-if="draft.conditions.skill_experience_years"><el-form-item v-for="s in required.split(/[、,，\n]/).map(v=>v.trim()).filter(Boolean)" :key="s" :label="`${s}最低经验年限（清空表示不限定，不等同总工作年限）`"><el-input-number v-model="draft.conditions.skill_experience_years[s]" :min="0" :max="60"/></el-form-item></template><el-form-item label="最低学历"><el-select v-model="draft.conditions.minimum_education"><el-option v-for="e in ['不限','高中','大专','本科','硕士','博士']" :key="e" :value="e"/></el-select></el-form-item><el-form-item label="最低工作年限（清空表示不限，不从技能出现次数推算）"><el-input-number v-model="draft.conditions.minimum_experience_years" :min="0" :max="60"/></el-form-item></template>
        <el-form-item label="福利（可不填）" data-jd-field="benefits"><el-input v-model="draft.benefits" type="textarea" maxlength="4000"/></el-form-item>
      </el-form>
      <p v-if="dirty" class="muted">表单有未保存修改，请先保存草稿。</p>
      <el-checkbox v-if="canWrite&&selected.id" v-model="confirmed" :disabled="dirty">我已核对已保存草稿，确认正文与必备/加分、学历及年限条件一致</el-checkbox>
      <div class="title-row"><el-button v-if="canWrite" :loading="busy" @click="save">保存草稿</el-button><el-button v-if="canWrite&&selected.id" type="primary" :disabled="!confirmed||busy||dirty" @click="transition(true)">确认生效为新版本</el-button><el-button v-if="canWrite&&selected.status==='active'" :disabled="busy||dirty" @click="transition(false)">停用需求</el-button><el-button v-if="selected.id" @click="view(selected)">刷新已保存内容</el-button></div>
    </section>
      <MatchWorkspace v-if="selected.id" v-show="panel==='matches'" :key="selected.id" :api="api" :requirement-id="selected.id" :initial-run-id="entry?.id===selected.id?entry.runId:undefined" :version="selected.version" :active-version="selected.active_version" :status="selected.status" :can-run="canWrite" :can-associate="canWrite && !!canTalentWrite" @open="id=>emit('open',id)" @task="id=>emit('task',id)"/>
      <section v-if="panel==='history'" class="job-history">
      <h3>有效版本历史</h3><el-empty v-if="!selected.versions?.length" description="尚无有效版本"/><el-collapse><el-collapse-item v-for="v in selected.versions" :key="v.number" :title="`版本 ${v.number} · ${new Date(v.created_at*1000).toLocaleString()}`"><p>{{v.snapshot.title}} · {{v.snapshot.location}}</p><p>{{v.snapshot.responsibilities}}</p><p>{{v.snapshot.description}}</p><pre>{{JSON.stringify(v.snapshot,null,2)}}</pre></el-collapse-item></el-collapse>
      </section>
  </section>
  </section>
</template>

<style scoped>
small{display:block;margin-top:6px;color:var(--text-secondary)}.pre-line{white-space:pre-wrap}.el-select{min-width:130px;margin-right:8px}.el-input-number{margin-right:8px}.job-editor{max-width:1000px;background:var(--surface);border:1px solid var(--border);padding:20px;border-radius:var(--radius)}.job-editor>.el-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px}.job-editor>.el-form>div:not(.el-form-item),.job-editor>.el-form>.el-card,.job-editor>.el-form>.el-alert,.job-editor>.el-form>.el-form-item:has(textarea){grid-column:1/-1}.overview-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;padding:18px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:16px}.overview-facts span{display:block;color:var(--text-secondary);font-size:12px;margin-bottom:8px}.overview-facts strong{font-size:14px;font-weight:550}.tag-list{display:flex;flex-wrap:wrap;gap:8px}.job-history pre{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:760px){.job-editor>.el-form,.overview-facts{grid-template-columns:1fr}.job-editor{padding:14px}}
</style>
