<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
import CandidateTable from './CandidateTable.vue'
import type {Candidate} from './candidate'
const props = defineProps<{api: Api; canImport: boolean;profileMode?:boolean;selfView?:boolean;title?:string;reloadToken?:number;canRequirements?:boolean;canChat?:boolean;departments?:{id:string;name?:string}[]}>()
const emit = defineEmits<{open: [id: string]; task: [id: string];chat:[scope:{kind:'selected'|'filtered';ids?:string[];filters?:Record<string,string>},labels?:Record<string,string>]}>()

const activeTab=ref('candidates')
const checkedIds=ref<string[]>([])
const loadError=ref('')
function toggleChecked(id:string){checkedIds.value=checkedIds.value.includes(id)?checkedIds.value.filter(x=>x!==id):[...checkedIds.value,id]}
function appliedText(){return Object.entries(appliedFilters.value||{}).filter(([k,v])=>v&&k!=='sort').map(([k,v])=>`${({kind:'身份',skill:'技能',education:'教育',experience:'经历',requirement_id:'应聘需求',minimum_education:'最低学历',minimum_experience_years:'最低总工作年限'} as Record<string,string>)[k]}：${k==='kind'?(v==='external'?'外部候选人':'内部员工'):k==='requirement_id'?(requirements.value.find(r=>r.id===v)?.draft.title||v):v}`).join(' · ')}
const filters = ref({kind: props.profileMode?'':'external', skill: '', education: '', experience: '', sort: 'name_asc',requirement_id:'',minimum_education:'',minimum_experience_years:''})
const appliedFilters=ref<typeof filters.value|null>(null)
function chatFiltered(){if(!appliedFilters.value)return;const {sort,...scopeFilters}=appliedFilters.value;emit('chat',{kind:'filtered',filters:scopeFilters},{requirement_id:requirements.value.find(r=>r.id===scopeFilters.requirement_id)?requirementLabel(requirements.value.find(r=>r.id===scopeFilters.requirement_id)!):''})}
const requirements=ref<{id:string;department_id?:string;draft:{title:string}}[]>([])
function requirementLabel(r:typeof requirements.value[number]){const department=props.departments?.find(d=>d.id===r.department_id)?.name;return (department?department+' · ':'')+(r.draft.title||'未命名需求')}

const items = ref<Candidate[]>([]), total = ref(0), page = ref(1), busy = ref(false)
const loading=ref(false)
let listRequest=0
const input = ref<HTMLInputElement | null>(null)
const uploads = ref<{name: string; state: string; id?: string}[]>([])
const batches = ref<string[]>([]), selectedBatch = ref('')
const batchTasks = ref<{id:string;name:string;state:string;error_code:string|null}[]>([])
const batchFailures = ref<{id:string;name:string;message:string}[]>([])
let pendingUpload: {signature:string; batch:string; keys:string[]} | null = null
function resetBatch() {
  pendingUpload=null; uploads.value=[]
  if (input.value) input.value.value=''
}
async function loadBatch() {
  if (!selectedBatch.value) return
  try {
    const result = await props.api<{tasks:typeof batchTasks.value; failures:typeof batchFailures.value}>(`/imports/${selectedBatch.value}`)
    batchTasks.value=result.tasks; batchFailures.value=result.failures
  } catch (error) { ElMessage.error((error as Error).message) }
}
async function load() {
  const request=++listRequest
  loading.value=true;loadError.value=''
  checkedIds.value=[]
  try {
    const requestedFilters={...filters.value}
    const params = new URLSearchParams({...Object.fromEntries(Object.entries(requestedFilters).filter(([,v])=>v!=='')), offset: String((page.value - 1) * 20), limit: '20'})
    const data = await props.api<{items: Candidate[]; total: number}>(`/candidates?${params}`)
    if(request!==listRequest)return
    items.value = data.items; total.value = data.total;appliedFilters.value=requestedFilters
    if(!props.profileMode){const history=await props.api<string[]>('/imports');if(request===listRequest)batches.value=history}
  } catch (error) { if(request===listRequest){loadError.value=(error as Error).message;ElMessage.error(loadError.value)} }
  finally {if(request===listRequest)loading.value=false}
}
async function upload() {
  const files = Array.from(input.value?.files || [])
  if (!files.length || files.length > 20) { ElMessage.error('请选择1至20份简历'); return }
  busy.value = true
  const signature=JSON.stringify(files.map(file => [file.name,file.size,file.lastModified]))
  if (!pendingUpload || pendingUpload.signature!==signature) pendingUpload={signature,batch:crypto.randomUUID(),keys:files.map(()=>crypto.randomUUID())}
  const batch = pendingUpload.batch, keys=pendingUpload.keys
  uploads.value = files.map(file => ({name: file.name, state: '等待上传'}))
  for (const [i, file] of files.entries()) {
    try {
      const form = new FormData(); form.append('file', file)
      const task = await props.api<{id: string}>(`/imports/${batch}`, 'POST', form, keys[i])
      uploads.value[i] = {name: file.name, state: '已接受，查看解析进度', id: task.id}
    } catch (error) { uploads.value[i]!.state = (error as Error).message }
  }
  busy.value = false; selectedBatch.value=batch; await load(); await loadBatch()
}
watch(()=>props.reloadToken,()=>void load())
onMounted(async()=>{await load();if(props.canRequirements){try{let offset=0;const all:typeof requirements.value=[];while(true){const data=await props.api<{items:typeof requirements.value;total:number}>(`/requirements?offset=${offset}&limit=100`);all.push(...data.items);if(!data.items.length||all.length>=data.total)break;offset+=data.items.length}requirements.value=all}catch(error){ElMessage.error((error as Error).message)}}})
</script>
<template>
  <div class="title-row"><div><h1>{{title||'简历筛选'}}</h1></div><div class="batch-actions"><slot name="actions"/><el-button v-if="canImport" type="primary" @click="activeTab='imports'">＋ 上传简历</el-button></div></div>
  <el-tabs v-if="!profileMode" v-model="activeTab" class="resume-tabs"><el-tab-pane label="候选人筛选" name="candidates"/><el-tab-pane label="导入与解析记录" name="imports"/></el-tabs>
  <div v-show="activeTab==='candidates'" class="candidate-list-page">
  <el-card v-if="!selfView" class="filter-card"><el-form label-position="top" class="candidate-filters" @submit.prevent="page=1;load()">
    <el-form-item label="人才身份"><el-select v-model="filters.kind"><el-option label="外部候选人" value="external"/><el-option label="内部员工" value="internal"/><el-option label="全部授权人才" value=""/></el-select></el-form-item>
    <el-form-item label="技能"><el-input v-model="filters.skill" placeholder="技能包含" clearable/></el-form-item>
    <el-form-item label="最低学历"><el-select v-model="filters.minimum_education" clearable placeholder="学历不限"><el-option label="不限" value=""/><el-option v-for="degree in ['高中','大专','本科','硕士','博士']" :key="degree" :label="degree+'及以上'" :value="degree"/></el-select></el-form-item><el-form-item label="总工作经验"><el-select v-model="filters.minimum_experience_years" clearable placeholder="年限不限"><el-option label="不限" value=""/><el-option v-for="years in [1,3,5,8,10]" :key="years" :label="years+' 年及以上'" :value="String(years)"/></el-select></el-form-item>    <el-form-item label="排序"><el-select v-model="filters.sort"><el-option label="姓名升序" value="name_asc"/><el-option label="姓名降序" value="name_desc"/><el-option label="档案版本降序" value="version_desc"/></el-select></el-form-item><el-form-item v-if="canRequirements" label="应聘岗位（已关联）" class="linked-job-filter"><el-select v-if="canRequirements" v-model="filters.requirement_id" clearable placeholder="应聘需求（仅显式关联者）" @change="page=1;load()"><el-option v-for="r in requirements" :key="r.id" :label="requirementLabel(r)" :value="r.id"/></el-select></el-form-item><el-form-item label="教育原文"><el-input v-model="filters.education" placeholder="教育原文包含，如本科" clearable/></el-form-item>
    <el-form-item label="经历原文"><el-input v-model="filters.experience" placeholder="经历原文包含" clearable/></el-form-item>

    <el-form-item label="操作"><el-button type="primary" native-type="submit" :loading="loading">筛选</el-button></el-form-item>
  </el-form></el-card>
  <div class="result-toolbar"><div><strong>共 {{ total }} 人</strong><p class="muted" data-testid="applied-filters">{{appliedText()||'当前授权范围'}} · 每页20人</p></div><div v-if="canChat" class="batch-actions"><el-button :disabled="loading||!checkedIds.length" @click="emit('chat',{kind:'selected',ids:[...checkedIds]})">比较 / 问答（{{checkedIds.length}}）</el-button><el-button :disabled="loading||!appliedFilters" @click="chatFiltered">按筛选范围问答</el-button></div></div>
  <p v-if="canChat" class="muted scope-note">范围问答使用已应用条件下全部 {{total}} 人；勾选限本页。学历和总工作年限仅包含有明确依据的满足者，资料未知不计为满足。</p>
  <el-alert v-if="loadError" :title="loadError" type="error" :closable="false"><el-button @click="load">重新加载</el-button></el-alert>
  <div v-loading="loading" class="candidate-results">
    <CandidateTable :items="items" :selected="checkedIds" :can-chat="canChat" @toggle="toggleChecked" @open="emit('open',$event)" @select-page="checkedIds=$event?items.map(p=>p.id):[]"/>
  </div><el-empty v-if="!loading&&!loadError&&!items.length" description="没有符合条件的人才，请调整筛选条件或导入简历"/>
  <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="total,prev,pager,next" @current-change="load"/>
  </div><details v-show="activeTab==='imports'" id="resume-import" class="import-section" open><summary>导入简历与逐文件进度</summary>
  <el-card v-if="canImport" style="margin-top:20px"><h2>导入简历</h2><p>PDF / PNG / JPEG / DOCX；单份10 MiB，PDF最多50页，每批最多20份。图片最多2500万像素，DOCX解压最多50 MiB/1000条目。</p><p class="muted">单文件解析最多12万字符、500个文字片段、100张文档图片。超时或失败会明确提示，最多执行3次。</p><p class="muted">导入先建立“待解析”档案；身份疑似重复时保留核对，不自动合并。</p><input ref="input" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.docx"/><el-button :loading="busy" @click="upload">上传并解析</el-button><el-button :disabled="busy" @click="resetBatch">新建另一批</el-button><p v-for="(item,i) in uploads" :key="i">{{item.name}}：{{item.state}} <el-button v-if="item.id" @click="emit('task',item.id)">进度与结果</el-button></p></el-card>
  <el-card style="margin-top:20px"><h2>导入与解析批次</h2><el-select v-model="selectedBatch" placeholder="选择历史批次（最多50个）" style="width:400px" @change="loadBatch"><el-option v-for="batch in batches" :key="batch" :label="`导入批次 ${batches.length-batches.indexOf(batch)} · ${batch.slice(0,8)}`" :value="batch"/></el-select><el-button @click="loadBatch">刷新逐文件对账</el-button><p v-for="item in batchTasks" :key="item.id">{{item.name}} · {{item.state}} · {{item.error_code}} <el-button @click="emit('task',item.id)">查看</el-button></p><p v-for="item in batchFailures" :key="item.id">{{item.name}} · 上传失败：{{item.message}}</p></el-card>
</details>
</template>

<style scoped>
.candidate-filters{display:grid;grid-template-columns:repeat(5,minmax(100px,1fr));gap:6px 10px}.candidate-filters .el-form-item{margin-bottom:4px;min-width:0}.linked-job-filter{grid-column:span 2}.filter-card{--el-card-padding:14px}.candidate-filters :deep(.el-form-item__label){margin-bottom:4px;line-height:20px;font-size:12px}.requirement-filter-label{font-size:12px;color:var(--text-secondary);margin-right:10px}.result-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:14px 0 6px}.result-toolbar p{margin:3px 0}.batch-actions{display:flex;flex-wrap:wrap;gap:8px}.batch-actions .el-button{margin:0}.scope-note{margin:4px 0 10px}.candidate-results{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}.candidate-results :deep(.el-table){margin:0}.import-section{margin-top:16px}.import-section>summary{font-weight:600;cursor:pointer}.resume-tabs{margin-bottom:12px}@media(max-width:1150px){.candidate-filters{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:760px){.candidate-filters{grid-template-columns:repeat(2,minmax(0,1fr))}.result-toolbar{align-items:flex-start;flex-direction:column}.requirement-filter-label{display:block;margin:0 0 6px}}
</style>
