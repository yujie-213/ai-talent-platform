<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
interface CatalogItem { id:string; name?:string; department_id?:string; position_id?:string }
interface Draft {
  department_position_id:string; title:string; location:string; responsibilities:string; description:string; benefits:string
  salary:{mode:'range'|'negotiable';minimum:number|null;maximum:number|null;currency:string;period:string}|null
  conditions:{required_skills:string[];preferred_skills:string[];minimum_education:string;minimum_experience_years:number|null}|null
  jd_text?:string
}
interface Suggestion {field:string;value:unknown;quote:string;source:'jd'|'proposal'}
interface Requirement {id:string;status:string;version:number;active_version:number|null;draft:Draft;versions?:{number:number;snapshot:Draft;created_at:number}[]}
const props = defineProps<{api:Api;canWrite:boolean;catalog:Record<string,CatalogItem[]>}>()
const items=ref<Requirement[]>([]), selected=ref<Requirement|null>(null), total=ref(0), currentPage=ref(1), busy=ref(false)
const confirmed=ref(false), key=ref(crypto.randomUUID()), department=ref(''), required=ref(''), preferred=ref('')
const draft=ref<Draft>(empty())
const baseline=ref('')
const formState=()=>JSON.stringify([draft.value,required.value,preferred.value])
const dirty=computed(()=>formState()!==baseline.value)
const assistBusy=ref(false), suggestions=ref<Suggestion[]>([]), issues=ref<string[]>([])
let formGeneration=0, pasteTimer:ReturnType<typeof setTimeout>|undefined
const fieldRevisions:Record<string,number>={}
function touch(event:Event) {
  confirmed.value=false
  const target=event.target
  const field=target instanceof Element?target.closest('[data-jd-field]')?.getAttribute('data-jd-field'):null
  if(field)fieldRevisions[field]=(fieldRevisions[field]||0)+1
}
const fieldNames:Record<string,string>={title:'需求名称',location:'工作地点',salary:'薪资',responsibilities:'岗位职责',description:'任职要求',benefits:'福利','conditions.required_skills':'必备技能','conditions.preferred_skills':'加分技能','conditions.minimum_education':'最低学历','conditions.minimum_experience_years':'最低工作年限'}
const states:Record<string,string>={draft:'草稿',active:'有效',disabled:'已停用'}
function empty():Draft {return {department_position_id:'',title:'',location:'',responsibilities:'',description:'',benefits:'',jd_text:'',salary:{mode:'range',minimum:null,maximum:null,currency:'CNY',period:'month'},conditions:{required_skills:[],preferred_skills:[],minimum_education:'不限',minimum_experience_years:null}}}
const positions=computed(()=>(props.catalog.department_positions||[]).filter(p=>p.department_id===department.value))
function positionName(id?:string) {return props.catalog.positions?.find(p=>p.id===id)?.name||id}
async function run(fn:()=>Promise<void>) {busy.value=true;try {await fn()} catch(e) {ElMessage.error((e as Error).message)} finally {busy.value=false}}
async function load() {const data=await props.api<{items:Requirement[];total:number}>(`/requirements?offset=${(currentPage.value-1)*20}&limit=20`);items.value=data.items;total.value=data.total}
function open(item:Requirement) {formGeneration++;suggestions.value=[];issues.value=[];selected.value=item;draft.value=JSON.parse(JSON.stringify(item.draft));draft.value.jd_text ||= ''; const dp=props.catalog.department_positions?.find(p=>p.id===item.draft.department_position_id); department.value=dp?.department_id||'';required.value=draft.value.conditions?.required_skills.join('、')||'';preferred.value=draft.value.conditions?.preferred_skills.join('、')||'';draft.value.salary ||= empty().salary; draft.value.conditions ||= empty().conditions;confirmed.value=false;baseline.value=formState()}
function close() {formGeneration++;selected.value=null;if(pasteTimer)clearTimeout(pasteTimer)}
function newItem() {open({id:'',status:'draft',version:1,active_version:null,draft:empty(),versions:[]});key.value=crypto.randomUUID()}
async function view(item:Requirement) {await run(async()=>open(await props.api<Requirement>(`/requirements/${item.id}`)))}
function body():Draft {const value=JSON.parse(JSON.stringify(draft.value)) as Draft; if(value.conditions) {value.conditions.required_skills=required.value.split(/[、,，\n]/).map(s=>s.trim()).filter(Boolean);value.conditions.preferred_skills=preferred.value.split(/[、,，\n]/).map(s=>s.trim()).filter(Boolean)} if(value.salary?.mode==='negotiable') {value.salary.minimum=null;value.salary.maximum=null} else if(value.salary?.minimum==null&&value.salary?.maximum==null)value.salary=null;return value}
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
async function save() {await run(async()=>{const item=selected.value!;const saved=await props.api<Requirement>(item.id?`/requirements/${item.id}`:'/requirements',item.id?'PUT':'POST',item.id?{...body(),version:item.version}:body(),item.id?undefined:key.value);open(saved);await load();ElMessage.success('草稿已保存')})}
async function transition(activate:boolean) {await run(async()=>{const item=selected.value!;const saved=await props.api<Requirement>(`/requirements/${item.id}/${activate?'activate':'disable'}`,'POST',activate?{version:item.version,confirmed:confirmed.value}:{version:item.version});open(saved);await load()})}
onMounted(()=>void run(load))
onBeforeUnmount(()=>{formGeneration++;if(pasteTimer)clearTimeout(pasteTimer)})
</script>

<template>
  <div class="title-row"><div><p class="eyebrow">RECRUITMENT</p><h1>岗位需求</h1><p class="muted">草稿可暂存；确认生效后保存独立版本。匹配功能正在开发。</p></div><el-button v-if="canWrite" type="primary" @click="newItem">新建需求</el-button></div>
  <el-card v-loading="busy"><el-table :data="items" @row-click="view"><el-table-column label="名称"><template #default="s">{{s.row.draft.title||'未命名草稿'}}</template></el-table-column><el-table-column label="状态"><template #default="s">{{states[s.row.status]}}</template></el-table-column><el-table-column prop="active_version" label="有效版本"/><el-table-column prop="version" label="编辑版本"/></el-table><el-empty v-if="!items.length" description="当前授权范围暂无岗位需求"/><el-pagination v-model:current-page="currentPage" :total="total" :page-size="20" layout="prev,pager,next" @current-change="()=>run(load)"/></el-card>
  <el-dialog :model-value="!!selected" title="岗位需求与版本" width="800px" @close="close" :close-on-click-modal="false">
    <template v-if="selected">
      <el-alert type="info" :closable="false" title="编辑表单后先保存草稿，再确认生效。未生效草稿不会改变原有效版本。"/>
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
        <template v-if="draft.conditions"><el-form-item label="必备技能（顿号或逗号分隔，留空表示无技能限制）"><el-input v-model="required"/></el-form-item><el-form-item label="加分技能（不作为硬性淘汰依据）"><el-input v-model="preferred"/></el-form-item><el-form-item label="最低学历"><el-select v-model="draft.conditions.minimum_education"><el-option v-for="e in ['不限','高中','大专','本科','硕士','博士']" :key="e" :value="e"/></el-select></el-form-item><el-form-item label="最低工作年限（清空表示不限，不从技能出现次数推算）"><el-input-number v-model="draft.conditions.minimum_experience_years" :min="0" :max="60"/></el-form-item></template>
        <el-form-item label="福利（可不填）" data-jd-field="benefits"><el-input v-model="draft.benefits" type="textarea" maxlength="4000"/></el-form-item>
      </el-form>
      <p v-if="dirty" class="muted">表单有未保存修改，请先保存草稿。</p>
      <el-checkbox v-if="canWrite&&selected.id" v-model="confirmed" :disabled="dirty">我已核对已保存草稿，确认正文与必备/加分、学历及年限条件一致</el-checkbox>
      <div class="title-row"><el-button v-if="canWrite" :loading="busy" @click="save">保存草稿</el-button><el-button v-if="canWrite&&selected.id" type="primary" :disabled="!confirmed||busy||dirty" @click="transition(true)">确认生效为新版本</el-button><el-button v-if="canWrite&&selected.status==='active'" :disabled="busy||dirty" @click="transition(false)">停用需求</el-button><el-button v-if="selected.id" @click="view(selected)">刷新已保存内容</el-button></div>
      <h3>有效版本历史</h3><el-empty v-if="!selected.versions?.length" description="尚无有效版本"/><el-collapse><el-collapse-item v-for="v in selected.versions" :key="v.number" :title="`版本 ${v.number} · ${new Date(v.created_at*1000).toLocaleString()}`"><p>{{v.snapshot.title}} · {{v.snapshot.location}}</p><p>{{v.snapshot.responsibilities}}</p><p>{{v.snapshot.description}}</p><pre>{{JSON.stringify(v.snapshot,null,2)}}</pre></el-collapse-item></el-collapse>
    </template>
  </el-dialog>
</template>

<style scoped>small {display:block;margin-top:6px;color:#667085} pre {white-space:pre-wrap;word-break:break-word} .el-select {min-width:130px; margin-right:8px} .el-input-number {margin-right:8px}</style>
