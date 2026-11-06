<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
import CandidateCard from './CandidateCard.vue'
import type {Candidate} from './candidate'
const props = defineProps<{api: Api; canImport: boolean;canRequirements?:boolean;canChat?:boolean;departments?:{id:string;name?:string}[]}>()
const emit = defineEmits<{open: [id: string]; task: [id: string];chat:[scope:{kind:'selected'|'filtered';ids?:string[];filters?:Record<string,string>}]}>()

const checkedIds=ref<string[]>([])
const loadError=ref('')
function toggleChecked(id:string){checkedIds.value=checkedIds.value.includes(id)?checkedIds.value.filter(x=>x!==id):[...checkedIds.value,id]}
function appliedText(){return Object.entries(appliedFilters.value||{}).filter(([k,v])=>v&&k!=='sort').map(([k,v])=>`${({kind:'身份',skill:'技能',education:'教育',experience:'经历',requirement_id:'应聘需求'} as Record<string,string>)[k]}：${k==='kind'?(v==='external'?'外部候选人':'内部员工'):k==='requirement_id'?(requirements.value.find(r=>r.id===v)?.draft.title||v):v}`).join(' · ')}
const filters = ref({kind: 'external', skill: '', education: '', experience: '', sort: 'name_asc',requirement_id:''})
const appliedFilters=ref<typeof filters.value|null>(null)
function chatFiltered(){if(!appliedFilters.value)return;const {sort,...scopeFilters}=appliedFilters.value;emit('chat',{kind:'filtered',filters:scopeFilters})}
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
    const params = new URLSearchParams({...requestedFilters, offset: String((page.value - 1) * 20), limit: '20'})
    const data = await props.api<{items: Candidate[]; total: number}>(`/candidates?${params}`)
    if(request!==listRequest)return
    items.value = data.items; total.value = data.total;appliedFilters.value=requestedFilters
    const history=await props.api<string[]>('/imports')
    if(request===listRequest)batches.value=history
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
onMounted(async()=>{await load();if(props.canRequirements){try{let offset=0;const all:typeof requirements.value=[];while(true){const data=await props.api<{items:typeof requirements.value;total:number}>(`/requirements?offset=${offset}&limit=100`);all.push(...data.items);if(!data.items.length||all.length>=data.total)break;offset+=data.items.length}requirements.value=all}catch(error){ElMessage.error((error as Error).message)}}})
</script>
<template>
  <div class="title-row"><div><p class="eyebrow">TALENT LIBRARY / 人才库</p><h1>候选人筛选</h1><p class="muted">从资料中发现合适的人才，再用证据深入了解。</p></div><a v-if="canImport" class="import-link" href="#resume-import">导入简历 ↗</a></div>
  <el-card class="filter-card"><el-form label-position="top" class="candidate-filters" @submit.prevent="page=1;load()">
    <el-form-item label="人才身份"><el-select v-model="filters.kind"><el-option label="外部候选人" value="external"/><el-option label="内部员工" value="internal"/><el-option label="全部授权人才" value=""/></el-select></el-form-item>
    <el-form-item label="技能"><el-input v-model="filters.skill" placeholder="技能包含" clearable/></el-form-item>
    <el-form-item label="教育"><el-input v-model="filters.education" placeholder="教育原文包含，如本科" clearable/></el-form-item>
    <el-form-item label="经历"><el-input v-model="filters.experience" placeholder="经历原文包含" clearable/></el-form-item>
    <el-form-item label="排序"><el-select v-model="filters.sort"><el-option label="姓名升序" value="name_asc"/><el-option label="姓名降序" value="name_desc"/><el-option label="档案版本降序" value="version_desc"/></el-select></el-form-item>
    <el-form-item label="应用条件"><el-button type="primary" native-type="submit" :loading="loading">筛选</el-button></el-form-item>
  </el-form><el-select v-if="canRequirements" v-model="filters.requirement_id" clearable placeholder="应聘需求（仅显式关联者）" class="requirement-filter" @change="page=1;load()"><el-option v-for="r in requirements" :key="r.id" :label="requirementLabel(r)" :value="r.id"/></el-select></el-card>
  <div class="result-toolbar"><div><strong>共 {{ total }} 人</strong><p class="muted" data-testid="applied-filters">{{appliedText()||'当前授权范围'}} · 每页20人</p></div><div v-if="canChat" class="batch-actions"><el-button :disabled="loading||!checkedIds.length" @click="emit('chat',{kind:'selected',ids:[...checkedIds]})">与勾选人才聊天（{{checkedIds.length}}）</el-button><el-button :disabled="loading||!appliedFilters" @click="chatFiltered">按当前筛选范围聊天</el-button></div></div>
  <p v-if="canChat" class="muted scope-note">聊天沿用上方已应用条件，包含全部 {{total}} 人；编辑条件后请点击筛选。勾选限当前页。</p>
  <el-alert v-if="loadError" :title="loadError" type="error" :closable="false"><el-button @click="load">重新加载</el-button></el-alert>
  <div v-loading="loading" class="candidate-grid" aria-label="候选人列表">
    <CandidateCard v-for="person in items" :key="person.id" :person="person" :selected="checkedIds.includes(person.id)" :can-chat="canChat" @toggle="toggleChecked" @open="emit('open',$event)"/>
  </div><el-empty v-if="!loading&&!loadError&&!items.length" description="没有符合条件的人才，请调整筛选条件或导入简历"/>
  <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="total,prev,pager,next" @current-change="load"/>
  <details id="resume-import" class="import-section"><summary>导入简历与逐文件进度</summary>
  <el-card v-if="canImport" style="margin-top:20px"><h2>导入简历</h2><p>PDF / PNG / JPEG / DOCX；单份10 MiB，PDF最多50页，每批最多20份。图片最多2500万像素，DOCX解压最多50 MiB/1000条目。</p><p class="muted">单文件解析最多12万字符、500个文字片段、100张文档图片。超时或失败会明确提示，最多执行3次。</p><p class="muted">导入先建立“待解析”档案；身份疑似重复时保留核对，不自动合并。</p><input ref="input" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.docx"/><el-button :loading="busy" @click="upload">上传并解析</el-button><el-button :disabled="busy" @click="resetBatch">新建另一批</el-button><p v-for="(item,i) in uploads" :key="i">{{item.name}}：{{item.state}} <el-button v-if="item.id" @click="emit('task',item.id)">进度与结果</el-button></p></el-card>
  <el-card style="margin-top:20px"><h2>导入与解析批次</h2><el-select v-model="selectedBatch" placeholder="选择历史批次（最多50个）" style="width:400px" @change="loadBatch"><el-option v-for="batch in batches" :key="batch" :label="batch" :value="batch"/></el-select><el-button @click="loadBatch">刷新逐文件对账</el-button><p v-for="item in batchTasks" :key="item.id">{{item.name}} · {{item.state}} · {{item.error_code}} <el-button @click="emit('task',item.id)">查看</el-button></p><p v-for="item in batchFailures" :key="item.id">{{item.name}} · 上传失败：{{item.message}}</p></el-card>
</details>
</template>

<style scoped>
.candidate-filters{display:grid;grid-template-columns:repeat(4,minmax(110px,1fr)) 150px auto;gap:12px}.candidate-filters .el-form-item{margin-bottom:12px;min-width:0}.requirement-filter{max-width:380px}.candidate-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;min-height:120px}.result-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:24px}.result-toolbar p{margin:6px 0}.batch-actions{display:flex;flex-wrap:wrap;gap:8px}.batch-actions .el-button{margin:0}.scope-note{margin:0 0 20px}.import-link{color:var(--accent);text-decoration:none;font-size:14px;font-weight:600}.import-section{margin-top:28px}.import-section>summary{padding:20px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);cursor:pointer;font-weight:600}.el-pagination{margin-top:24px}@media(max-width:1250px){.candidate-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.candidate-filters{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:760px){.candidate-grid{grid-template-columns:1fr}.candidate-filters{grid-template-columns:repeat(2,minmax(0,1fr))}.result-toolbar{align-items:flex-start;flex-direction:column}}
</style>
