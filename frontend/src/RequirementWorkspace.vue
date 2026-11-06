<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
interface CatalogItem { id:string; name?:string; department_id?:string; position_id?:string }
interface Draft {
  department_position_id:string; title:string; location:string; responsibilities:string; description:string; benefits:string
  salary:{mode:'range'|'negotiable';minimum:number|null;maximum:number|null;currency:string;period:string}|null
  conditions:{required_skills:string[];preferred_skills:string[];minimum_education:string;minimum_experience_years:number|null}|null
}
interface Requirement {id:string;status:string;version:number;active_version:number|null;draft:Draft;versions?:{number:number;snapshot:Draft;created_at:number}[]}
const props = defineProps<{api:Api;canWrite:boolean;catalog:Record<string,CatalogItem[]>}>()
const items=ref<Requirement[]>([]), selected=ref<Requirement|null>(null), total=ref(0), currentPage=ref(1), busy=ref(false)
const confirmed=ref(false), key=ref(crypto.randomUUID()), department=ref(''), required=ref(''), preferred=ref('')
const draft=ref<Draft>(empty())
const baseline=ref('')
const formState=()=>JSON.stringify([draft.value,required.value,preferred.value])
const dirty=computed(()=>formState()!==baseline.value)
const states:Record<string,string>={draft:'草稿',active:'有效',disabled:'已停用'}
function empty():Draft {return {department_position_id:'',title:'',location:'',responsibilities:'',description:'',benefits:'',salary:{mode:'range',minimum:null,maximum:null,currency:'CNY',period:'month'},conditions:{required_skills:[],preferred_skills:[],minimum_education:'不限',minimum_experience_years:null}}}
const positions=computed(()=>(props.catalog.department_positions||[]).filter(p=>p.department_id===department.value))
function positionName(id?:string) {return props.catalog.positions?.find(p=>p.id===id)?.name||id}
async function run(fn:()=>Promise<void>) {busy.value=true;try {await fn()} catch(e) {ElMessage.error((e as Error).message)} finally {busy.value=false}}
async function load() {const data=await props.api<{items:Requirement[];total:number}>(`/requirements?offset=${(currentPage.value-1)*20}&limit=20`);items.value=data.items;total.value=data.total}
function open(item:Requirement) {selected.value=item;draft.value=JSON.parse(JSON.stringify(item.draft)); const dp=props.catalog.department_positions?.find(p=>p.id===item.draft.department_position_id); department.value=dp?.department_id||'';required.value=draft.value.conditions?.required_skills.join('、')||'';preferred.value=draft.value.conditions?.preferred_skills.join('、')||'';draft.value.salary ||= empty().salary; draft.value.conditions ||= empty().conditions;confirmed.value=false;baseline.value=formState()}
function newItem() {open({id:'',status:'draft',version:1,active_version:null,draft:empty(),versions:[]});key.value=crypto.randomUUID()}
async function view(item:Requirement) {await run(async()=>open(await props.api<Requirement>(`/requirements/${item.id}`)))}
function body():Draft {const value=JSON.parse(JSON.stringify(draft.value)) as Draft; if(value.conditions) {value.conditions.required_skills=required.value.split(/[、,，\n]/).map(s=>s.trim()).filter(Boolean);value.conditions.preferred_skills=preferred.value.split(/[、,，\n]/).map(s=>s.trim()).filter(Boolean)} if(value.salary?.mode==='negotiable') {value.salary.minimum=null;value.salary.maximum=null}return value}
async function save() {await run(async()=>{const item=selected.value!;const saved=await props.api<Requirement>(item.id?`/requirements/${item.id}`:'/requirements',item.id?'PUT':'POST',item.id?{...body(),version:item.version}:body(),item.id?undefined:key.value);open(saved);await load();ElMessage.success('草稿已保存')})}
async function transition(activate:boolean) {await run(async()=>{const item=selected.value!;const saved=await props.api<Requirement>(`/requirements/${item.id}/${activate?'activate':'disable'}`,'POST',activate?{version:item.version,confirmed:confirmed.value}:{version:item.version});open(saved);await load()})}
onMounted(()=>void run(load))
</script>

<template>
  <div class="title-row"><div><p class="eyebrow">RECRUITMENT</p><h1>岗位需求</h1><p class="muted">草稿可暂存；确认生效后保存独立版本。匹配功能正在开发。</p></div><el-button v-if="canWrite" type="primary" @click="newItem">新建需求</el-button></div>
  <el-card v-loading="busy"><el-table :data="items" @row-click="view"><el-table-column label="名称"><template #default="s">{{s.row.draft.title||'未命名草稿'}}</template></el-table-column><el-table-column label="状态"><template #default="s">{{states[s.row.status]}}</template></el-table-column><el-table-column prop="active_version" label="有效版本"/><el-table-column prop="version" label="编辑版本"/></el-table><el-empty v-if="!items.length" description="当前授权范围暂无岗位需求"/><el-pagination v-model:current-page="currentPage" :total="total" :page-size="20" layout="prev,pager,next" @current-change="()=>run(load)"/></el-card>
  <el-dialog :model-value="!!selected" title="岗位需求与版本" width="800px" @close="selected=null" :close-on-click-modal="false">
    <template v-if="selected">
      <el-alert type="info" :closable="false" title="编辑表单后先保存草稿，再确认生效。未生效草稿不会改变原有效版本。"/>
      <el-form label-position="top" :disabled="!canWrite||busy" @input="confirmed=false" @change="confirmed=false">
        <el-form-item label="部门"><el-select v-model="department" :disabled="!!selected.id" @change="draft.department_position_id='' "><el-option v-for="d in catalog.departments" :key="d.id" :label="d.name" :value="d.id"/></el-select></el-form-item>
        <el-form-item label="部门岗位"><el-select v-model="draft.department_position_id" :disabled="!!selected.id"><el-option v-for="p in positions" :key="p.id" :label="positionName(p.position_id)" :value="p.id"/></el-select><small>没有所需岗位时，由获授权人员在基础资料中维护。</small></el-form-item>
        <el-form-item label="需求名称"><el-input v-model="draft.title" maxlength="100"/></el-form-item>
        <el-form-item label="工作地点 / 远程安排"><el-input v-model="draft.location" maxlength="300"/></el-form-item>
        <template v-if="draft.salary"><el-form-item label="薪资"><el-select v-model="draft.salary.mode"><el-option label="明确区间" value="range"/><el-option label="面议" value="negotiable"/></el-select><template v-if="draft.salary.mode==='range'"><el-input-number v-model="draft.salary.minimum" :min="0" placeholder="下限"/><el-input-number v-model="draft.salary.maximum" :min="0" placeholder="上限"/><el-select v-model="draft.salary.currency"><el-option v-for="c in ['CNY','USD','EUR']" :key="c" :value="c"/></el-select><el-select v-model="draft.salary.period"><el-option label="月薪" value="month"/><el-option label="年薪" value="year"/><el-option label="时薪" value="hour"/></el-select></template></el-form-item></template>
        <el-form-item label="岗位职责"><el-input v-model="draft.responsibilities" type="textarea" :rows="3" maxlength="12000"/></el-form-item>
        <el-form-item label="任职要求正文"><el-input v-model="draft.description" type="textarea" :rows="3" maxlength="12000"/></el-form-item>
        <template v-if="draft.conditions"><el-form-item label="必备技能（顿号或逗号分隔，留空表示无技能限制）"><el-input v-model="required"/></el-form-item><el-form-item label="加分技能（不作为硬性淘汰依据）"><el-input v-model="preferred"/></el-form-item><el-form-item label="最低学历"><el-select v-model="draft.conditions.minimum_education"><el-option v-for="e in ['不限','高中','大专','本科','硕士','博士']" :key="e" :value="e"/></el-select></el-form-item><el-form-item label="最低工作年限（清空表示不限，不从技能出现次数推算）"><el-input-number v-model="draft.conditions.minimum_experience_years" :min="0" :max="60"/></el-form-item></template>
        <el-form-item label="福利（可不填）"><el-input v-model="draft.benefits" type="textarea" maxlength="4000"/></el-form-item>
      </el-form>
      <p v-if="dirty" class="muted">表单有未保存修改，请先保存草稿。</p>
      <el-checkbox v-if="canWrite&&selected.id" v-model="confirmed" :disabled="dirty">我已核对已保存草稿，确认正文与必备/加分、学历及年限条件一致</el-checkbox>
      <div class="title-row"><el-button v-if="canWrite" :loading="busy" @click="save">保存草稿</el-button><el-button v-if="canWrite&&selected.id" type="primary" :disabled="!confirmed||busy||dirty" @click="transition(true)">确认生效为新版本</el-button><el-button v-if="canWrite&&selected.status==='active'" :disabled="busy||dirty" @click="transition(false)">停用需求</el-button><el-button v-if="selected.id" @click="view(selected)">刷新已保存内容</el-button></div>
      <h3>有效版本历史</h3><el-empty v-if="!selected.versions?.length" description="尚无有效版本"/><el-collapse><el-collapse-item v-for="v in selected.versions" :key="v.number" :title="`版本 ${v.number} · ${new Date(v.created_at*1000).toLocaleString()}`"><p>{{v.snapshot.title}} · {{v.snapshot.location}}</p><p>{{v.snapshot.responsibilities}}</p><p>{{v.snapshot.description}}</p><pre>{{JSON.stringify(v.snapshot,null,2)}}</pre></el-collapse-item></el-collapse>
    </template>
  </el-dialog>
</template>

<style scoped>small {display:block;margin-top:6px;color:#667085} pre {white-space:pre-wrap;word-break:break-word} .el-select {min-width:130px; margin-right:8px} .el-input-number {margin-right:8px}</style>
