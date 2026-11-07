<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
import CandidateTable from './CandidateTable.vue'
import AppIcon from './AppIcon.vue'
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
const moreOpen=ref(false)
const chipNames:Record<string,string>={kind:'身份',skill:'技能',education:'教育原文',experience:'经历原文',requirement_id:'应聘岗位',minimum_education:'最低学历',minimum_experience_years:'工作年限'}
function chipText(key:string,value:string){
  if(key==='kind')return value==='external'?'外部候选人':'内部员工'
  if(key==='requirement_id'){const r=requirements.value.find(r=>r.id===value);return r?requirementLabel(r):'指定岗位'}
  if(key==='minimum_education')return value+'及以上'
  if(key==='minimum_experience_years')return value+' 年及以上'
  if(key==='skill'||key==='education'||key==='experience')return `${chipNames[key]}含“${value}”`
  return `${chipNames[key]}：${value}`
}
const chips=computed(()=>Object.entries(appliedFilters.value||{}).filter(([k,v])=>v&&k!=='sort').map(([k,v])=>({key:k,text:chipText(k,v as string)})))
const moreCount=computed(()=>[filters.value.requirement_id,filters.value.education,filters.value.experience].filter(Boolean).length)
function apply(){page.value=1;void load()}
function clearChip(key:string){(filters.value as Record<string,string>)[key]='';apply()}
function clearAll(){filters.value={kind:props.profileMode?'':'external',skill:'',education:'',experience:'',sort:filters.value.sort,requirement_id:'',minimum_education:'',minimum_experience_years:''};apply()}
function chatFiltered(){if(!appliedFilters.value)return;const {sort,...scopeFilters}=appliedFilters.value;emit('chat',{kind:'filtered',filters:scopeFilters},{requirement_id:requirements.value.find(r=>r.id===scopeFilters.requirement_id)?requirementLabel(requirements.value.find(r=>r.id===scopeFilters.requirement_id)!):''})}
// 快捷切片只表达后端真实支持的筛选口径：身份、学历、年限。没有数据口径的条件不做成切片。
const slices=[
  {key:'all',label:'全部人才'},
  {key:'external',label:'外部候选人'},
  {key:'internal',label:'内部员工'},
  {key:'master',label:'硕士及以上'},
  {key:'exp5',label:'5 年以上经验'},
] as const
function sliceActive(key:string){
  const f=filters.value
  if(key==='all')return !f.kind&&!f.minimum_education&&!f.minimum_experience_years
  if(key==='external')return f.kind==='external'&&!f.minimum_education&&!f.minimum_experience_years
  if(key==='internal')return f.kind==='internal'
  if(key==='master')return f.minimum_education==='硕士'
  if(key==='exp5')return f.minimum_experience_years==='5'
  return false
}
function applySlice(key:string){
  // 「全部人才」= 清空身份与学历年限限制；简历筛选页默认只显示外部候选人，因此这里必须设为空而不是重置回 external。
  if(key==='all'){filters.value.kind='';filters.value.minimum_education='';filters.value.minimum_experience_years=''}
  if(key==='external'){filters.value.kind='external';filters.value.minimum_education='';filters.value.minimum_experience_years=''}
  if(key==='internal'){filters.value.kind='internal';filters.value.minimum_education='';filters.value.minimum_experience_years=''}
  if(key==='master')filters.value.minimum_education='硕士'
  if(key==='exp5')filters.value.minimum_experience_years='5'
  apply()
}
// 概览条只展示真实统计：授权人才与解析任务状态；取不到时静默隐藏，不展示占位假数据。
interface WorkbenchSummary {people?:Record<string,number>;parse_tasks?:Record<string,number>}
const overview=ref<WorkbenchSummary|null>(null)
async function loadOverview(){if(props.selfView||props.profileMode)return;try{overview.value=await props.api<WorkbenchSummary>('/workbench')}catch{overview.value=null}}

const requirements=ref<{id:string;department_id?:string;draft:{title:string}}[]>([])
function requirementLabel(r:typeof requirements.value[number]){const department=props.departments?.find(d=>d.id===r.department_id)?.name;return (department?department+' · ':'')+(r.draft.title||'未命名需求')}

const items = ref<Candidate[]>([]), total = ref(0), page = ref(1), busy = ref(false)
const loading=ref(false)
let listRequest=0
const input = ref<HTMLInputElement | null>(null)
const uploads = ref<{name: string; state: string; id?: string}[]>([])
// 选中的文件先进入暂存列表，用户确认后再统一上传；拖拽和文件选择框写同一个列表。
const pickedFiles = ref<File[]>([])
const dragging = ref(false)
function setPicked(files: File[]) { pickedFiles.value = files.slice(0, 20) }
function onPicked(event: Event) { setPicked(Array.from((event.target as HTMLInputElement).files || [])) }
function pick() { input.value?.click() }
function onDrop(event: DragEvent) { dragging.value = false; setPicked(Array.from(event.dataTransfer?.files || [])) }
function removePicked(file: File) { pickedFiles.value = pickedFiles.value.filter(f => f !== file) }
function clearPicked() { pickedFiles.value = []; if (input.value) input.value.value = '' }
const sizeText = (bytes: number) => bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
const batches = ref<string[]>([]), selectedBatch = ref('')
const batchTasks = ref<{id:string;name:string;state:string;error_code:string|null}[]>([])
const batchFailures = ref<{id:string;name:string;message:string}[]>([])
let pendingUpload: {signature:string; batch:string; keys:string[]} | null = null
function resetBatch() {
  pendingUpload=null; uploads.value=[]
  clearPicked()
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
  const files = [...pickedFiles.value]
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
  busy.value = false; clearPicked(); selectedBatch.value=batch; await load(); await loadBatch()
}
watch(()=>props.reloadToken,()=>void load())
onMounted(async()=>{void loadOverview();await load();if(props.canRequirements){try{let offset=0;const all:typeof requirements.value=[];while(true){const data=await props.api<{items:typeof requirements.value;total:number}>(`/requirements?offset=${offset}&limit=100`);all.push(...data.items);if(!data.items.length||all.length>=data.total)break;offset+=data.items.length}requirements.value=all}catch(error){ElMessage.error((error as Error).message)}}})
</script>
<template>
  <div class="title-row"><div><h1>{{title||'简历筛选'}}</h1></div><div class="batch-actions"><slot name="actions"/><el-button v-if="canImport&&activeTab!=='imports'" type="primary" @click="activeTab='imports'">＋ 上传简历</el-button></div></div>
  <div v-if="overview" class="overview-strip" aria-label="授权范围概览">
    <div class="overview-stat"><span class="stat-label">授权人才</span><strong>{{(overview.people?.external||0)+(overview.people?.internal||0)}}</strong><span class="stat-note">外部 {{overview.people?.external||0}} · 内部 {{overview.people?.internal||0}}</span></div>
    <div class="overview-stat"><span class="stat-label">解析进行中</span><strong>{{(overview.parse_tasks?.queued||0)+(overview.parse_tasks?.running||0)}}</strong><span class="stat-note">排队 {{overview.parse_tasks?.queued||0}} · 执行 {{overview.parse_tasks?.running||0}}</span></div>
    <div class="overview-stat" :class="{attention:(overview.parse_tasks?.failed||0)>0}"><span class="stat-label">失败任务</span><strong>{{overview.parse_tasks?.failed||0}}</strong><span class="stat-note">{{(overview.parse_tasks?.failed||0)>0?'需要在任务记录中处理':'当前没有积压'}}</span></div>
  </div>
  <el-tabs v-if="!profileMode" v-model="activeTab" class="resume-tabs"><el-tab-pane label="候选人筛选" name="candidates"/><el-tab-pane label="导入与解析记录" name="imports"/></el-tabs>
  <div v-show="activeTab==='candidates'" class="candidate-list-page">
  <form v-if="!selfView" class="filter-bar" @submit.prevent="apply">
    <div class="slice-row" role="group" aria-label="快捷筛选">
      <button v-for="s in slices" :key="s.key" type="button" class="slice-chip" :class="{active:sliceActive(s.key)}" @click="applySlice(s.key)">{{s.label}}</button>
    </div>
    <div class="filter-row">
      <el-input v-model="filters.skill" class="filter-search" placeholder="搜索技能关键词，如 Python" clearable aria-label="技能关键词"/>
      <el-select v-model="filters.kind" class="filter-item" aria-label="人才身份"><el-option label="外部候选人" value="external"/><el-option label="内部员工" value="internal"/><el-option label="全部授权人才" value=""/></el-select>
      <el-select v-model="filters.minimum_education" class="filter-item" clearable placeholder="最低学历" aria-label="最低学历"><el-option label="不限学历" value=""/><el-option v-for="degree in ['高中','大专','本科','硕士','博士']" :key="degree" :label="degree+'及以上'" :value="degree"/></el-select>
      <el-select v-model="filters.minimum_experience_years" class="filter-item" clearable placeholder="工作年限" aria-label="总工作经验"><el-option label="不限年限" value=""/><el-option v-for="years in [1,3,5,8,10]" :key="years" :label="years+' 年及以上'" :value="String(years)"/></el-select>
      <el-button type="primary" native-type="submit" :loading="loading">查询</el-button>
      <button type="button" class="filter-toggle" :aria-expanded="moreOpen" @click="moreOpen=!moreOpen">更多筛选<span v-if="moreCount" class="filter-badge">{{moreCount}}</span><span class="chevron" :class="{open:moreOpen}" aria-hidden="true"></span></button>
    </div>
    <div v-show="moreOpen" class="filter-more">
      <el-select v-if="canRequirements" v-model="filters.requirement_id" clearable placeholder="应聘岗位（仅显式关联者）" aria-label="应聘岗位"><el-option v-for="r in requirements" :key="r.id" :label="requirementLabel(r)" :value="r.id"/></el-select>
      <el-input v-model="filters.education" clearable placeholder="教育原文包含，如本科" aria-label="教育原文"/>
      <el-input v-model="filters.experience" clearable placeholder="经历原文包含" aria-label="经历原文"/>
    </div>
    <div v-if="chips.length" class="filter-chips">
      <span class="chips-label">已选条件</span>
      <el-tag v-for="chip in chips" :key="chip.key" closable @close="clearChip(chip.key)">{{chip.text}}</el-tag>
      <button type="button" class="chip-clear" @click="clearAll">清除全部</button>
    </div>
  </form>
  <div class="result-toolbar">
    <div class="result-count"><strong>{{total}}</strong><span> 人</span><p class="muted" data-testid="applied-filters">{{appliedText()||'当前授权范围'}} · 每页 20 人</p></div>
    <div class="result-actions">
      <el-select v-model="filters.sort" class="sort-select" aria-label="排序方式" @change="apply"><el-option label="姓名升序" value="name_asc"/><el-option label="姓名降序" value="name_desc"/><el-option label="档案版本降序" value="version_desc"/></el-select>
      <template v-if="canChat"><el-button :disabled="loading||!checkedIds.length" @click="emit('chat',{kind:'selected',ids:[...checkedIds]})">比较 / 问答（{{checkedIds.length}}）</el-button><el-button :disabled="loading||!appliedFilters" @click="chatFiltered">按筛选范围问答</el-button></template>
    </div>
  </div>
  <p v-if="canChat" class="muted scope-note">范围问答使用已应用条件下全部 {{total}} 人；勾选限本页。学历和总工作年限仅包含有明确依据的满足者，资料未知不计为满足。</p>
  <el-alert v-if="loadError" :title="loadError" type="error" :closable="false"><el-button @click="load">重新加载</el-button></el-alert>
  <div v-loading="loading" class="candidate-results">
    <CandidateTable :items="items" :selected="checkedIds" :can-chat="canChat" @toggle="toggleChecked" @open="emit('open',$event)" @select-page="checkedIds=$event?items.map(p=>p.id):[]"/>
  </div><el-empty v-if="!loading&&!loadError&&!items.length" description="没有符合条件的人才，请调整筛选条件或导入简历"/>
  <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="total,prev,pager,next" @current-change="load"/>
  </div><details v-show="activeTab==='imports'" id="resume-import" class="import-section" open><summary>导入简历与逐文件进度</summary>
  <div v-if="canImport" class="upload-card">
    <div class="upload-zone" :class="{dragging}" role="button" tabindex="0" aria-label="上传简历" @click="pick" @keydown.enter.prevent="pick" @dragover.prevent="dragging=true" @dragleave.prevent="dragging=false" @drop.prevent="onDrop">
      <span class="upload-icon"><AppIcon name="file"/></span>
      <p class="upload-title">拖拽简历到这里，或<em>点击选择文件</em></p>
      <p class="upload-hint">PDF · PNG · JPEG · DOCX<span class="sep">·</span>单份 ≤ 10 MiB<span class="sep">·</span>每批 ≤ 20 份</p>
      <input ref="input" class="upload-input" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.docx" aria-label="选择简历文件" @change="onPicked"/>
    </div>

    <div v-if="pickedFiles.length" class="picked">
      <div class="picked-head"><strong>已选 {{pickedFiles.length}} 份</strong><button type="button" class="link-btn" @click.stop="clearPicked">清空</button></div>
      <div v-for="(file,i) in pickedFiles" :key="i" class="picked-row">
        <span class="picked-badge"><AppIcon name="file"/></span>
        <span class="picked-name">{{file.name}}</span>
        <span class="picked-size">{{sizeText(file.size)}}</span>
        <button type="button" class="picked-remove" :aria-label="'移除 '+file.name" @click.stop="removePicked(file)">×</button>
      </div>
    </div>

    <div class="upload-actions">
      <el-button type="primary" :loading="busy" :disabled="!pickedFiles.length" @click="upload">上传并解析</el-button>
      <el-button :disabled="busy" @click="resetBatch">新建另一批</el-button>
      <span class="upload-count">{{pickedFiles.length?`待解析 ${pickedFiles.length} 份`:'尚未选择文件'}}</span>
    </div>

    <div v-if="uploads.length" class="upload-results">
      <div v-for="(item,i) in uploads" :key="i" class="result-row">
        <span class="state-dot" :class="item.id?'ok':item.state.includes('等待')?'wait':'err'"/>
        <span class="result-name">{{item.name}}</span>
        <span class="result-state">{{item.state}}</span>
        <el-button v-if="item.id" link type="primary" @click="emit('task',item.id)">进度与结果</el-button>
      </div>
    </div>

    <details class="upload-rules"><summary>导入规则与限制</summary><ul><li>单份文件 ≤ 10 MiB，PDF 最多 50 页，每批最多 20 份</li><li>图片最多 2500 万像素；DOCX 解压后 ≤ 50 MiB 且 ≤ 1000 个条目</li><li>单文件解析最多 12 万字符、500 个文字片段、100 张文档图片</li><li>超时或失败会明确提示，单文件最多执行 3 次</li><li>导入先建立「待解析」档案；身份疑似重复时保留核对，不自动合并</li></ul></details>
  </div>

  <el-card class="batch-card">
    <template #header><div class="batch-head"><h2>导入与解析批次</h2><el-button link type="primary" @click="loadBatch">刷新逐文件对账</el-button></div></template>
    <el-select v-model="selectedBatch" placeholder="选择历史批次（最多 50 个）" class="batch-select" @change="loadBatch"><el-option v-for="batch in batches" :key="batch" :label="`导入批次 ${batches.length-batches.indexOf(batch)} · ${batch.slice(0,8)}`" :value="batch"/></el-select>
    <div v-for="item in batchTasks" :key="item.id" class="result-row"><span class="state-dot" :class="item.state==='succeeded'?'ok':item.state==='failed'?'err':'wait'"/><span class="result-name">{{item.name}}</span><span class="result-state">{{item.state}}<template v-if="item.error_code"> · {{item.error_code}}</template></span><el-button link type="primary" @click="emit('task',item.id)">查看</el-button></div>
    <p v-for="item in batchFailures" :key="item.id" class="fail-line">{{item.name}} · 上传失败：{{item.message}}</p>
    <p v-if="!selectedBatch&&!batchTasks.length&&!batchFailures.length" class="batch-hint">选择历史批次后，这里显示逐文件解析结果与失败原因。</p>
  </el-card>
</details>
</template>

<style scoped>
.candidate-list-page{display:flex;flex-direction:column}
.overview-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 14px}
.overview-stat{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:12px 16px;display:flex;flex-direction:column;gap:2px}
.overview-stat strong{font-size:22px;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.25}
.stat-label{font-size:12px;color:var(--text-secondary)}
.stat-note{font-size:11px;color:var(--text-tertiary)}
.overview-stat.attention strong{color:#b4231f}
.slice-row{display:flex;gap:8px;flex-wrap:wrap;padding-bottom:10px;margin-bottom:10px;border-bottom:1px solid var(--border)}
.slice-chip{border:1px solid var(--border);background:var(--surface);color:var(--text-secondary);border-radius:999px;padding:5px 13px;font-size:12px;cursor:pointer;line-height:1.4;transition:all .15s}
.slice-chip:hover{border-color:var(--accent);color:var(--accent)}
.slice-chip.active{background:var(--accent-soft);border-color:var(--accent);color:var(--accent);font-weight:500}
.filter-bar{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:12px 14px;margin:0 0 16px}
.filter-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.filter-search{flex:1 1 260px;min-width:200px}
.filter-item{width:150px}
.filter-toggle{display:inline-flex;align-items:center;gap:4px;background:transparent;border:0;color:var(--text-secondary);font-size:13px;cursor:pointer;padding:6px 2px}
.filter-toggle:hover{color:var(--accent)}
.filter-badge{display:inline-grid;place-items:center;min-width:16px;height:16px;padding:0 4px;border-radius:8px;background:var(--accent-soft);color:var(--accent);font-size:10px;line-height:1}
.chevron{width:0;height:0;margin-top:2px;border-left:4px solid transparent;border-right:4px solid transparent;border-top:5px solid var(--text-tertiary);transition:transform .15s}
.chevron.open{transform:rotate(180deg)}
.filter-more{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;padding-top:10px;border-top:1px dashed var(--border)}
.filter-more .el-select{width:230px}
.filter-more .el-input{width:210px}
.filter-chips{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:10px}
.chips-label{font-size:12px;color:var(--text-tertiary)}
.chip-clear{border:0;background:transparent;color:var(--text-secondary);font-size:12px;cursor:pointer;padding:2px 2px;text-decoration:underline;text-underline-offset:3px}
.chip-clear:hover{color:var(--accent)}
.result-toolbar{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin:0 0 12px}
.result-count{display:flex;align-items:baseline;gap:4px;flex-wrap:wrap;min-width:0}
.result-count strong{font-size:17px;font-weight:600;font-variant-numeric:tabular-nums}
.result-count>span{font-size:13px;color:var(--text-secondary)}
.result-count p{flex-basis:100%;margin:2px 0 0;font-size:12px}
.result-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.result-actions .el-button{margin:0}
.sort-select{width:136px}
.batch-actions{display:flex;flex-wrap:wrap;gap:8px}
.batch-actions .el-button{margin:0}
.scope-note{margin:0 0 10px;font-size:12px}
.candidate-results{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
.candidate-results :deep(.el-table){margin:0}
.import-section{margin-top:16px}
.import-section>summary{font-weight:600}
/* ---------- 导入区：一个主操作 + 拖拽区，限制条款收进折叠 ---------- */
.upload-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:16px;margin-top:16px}
.upload-zone{display:flex;flex-direction:column;align-items:center;gap:8px;padding:26px 16px;border:1.5px dashed #c3cad8;border-radius:12px;background:var(--surface);cursor:pointer;text-align:center;transition:border-color .15s,background .15s}
.upload-zone:hover,.upload-zone.dragging{border-color:var(--accent);background:var(--accent-soft)}
.upload-zone.dragging{border-style:solid}
.upload-icon{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;background:var(--surface);color:var(--accent);box-shadow:var(--shadow)}
.upload-icon :deep(svg){width:20px;height:20px}
.upload-title{margin:0;font-size:14px;font-weight:550;color:var(--text)}
.upload-title em{font-style:normal;color:var(--accent);font-weight:600}
.upload-hint{margin:0;font-size:12px;color:var(--text-tertiary)}
.upload-hint .sep{margin:0 6px;color:var(--border-strong)}
.upload-input{display:none}
.picked{margin-top:14px;border:1px solid var(--border);border-radius:10px;overflow:hidden}
.picked-head{display:flex;align-items:center;justify-content:space-between;padding:9px 12px;background:var(--surface-muted);font-size:12px}
.picked-head strong{font-weight:600;color:var(--text)}
.link-btn{border:0;background:transparent;color:var(--accent);font-size:12px;cursor:pointer;padding:0}
.picked-row{display:flex;align-items:center;gap:9px;padding:8px 12px;border-top:1px solid var(--border);font-size:13px}
.picked-badge{width:24px;height:24px;border-radius:6px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent);flex-shrink:0}
.picked-badge :deep(svg){width:14px;height:14px}
.picked-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.picked-size{font-size:12px;color:var(--text-tertiary);flex-shrink:0}
.picked-remove{border:0;background:transparent;color:var(--text-tertiary);font-size:16px;line-height:1;cursor:pointer;padding:0 2px;border-radius:4px}
.picked-remove:hover{color:var(--el-color-danger)}
.upload-actions{display:flex;align-items:center;gap:10px;margin-top:14px}
.upload-count{font-size:12px;color:var(--text-tertiary)}
.upload-results{margin-top:12px;border-top:1px solid var(--border);padding-top:10px}
.result-row{display:flex;align-items:center;gap:9px;padding:6px 0;font-size:13px}
.result-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.result-state{font-size:12px;color:var(--text-secondary);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.state-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;background:var(--border-strong)}
.state-dot.ok{background:#1a9e6f}
.state-dot.wait{background:#d99426}
.state-dot.err{background:#c0393f}
.upload-rules{margin-top:12px;font-size:12px;color:var(--text-secondary)}
.upload-rules>summary{cursor:pointer;color:var(--text-tertiary);font-size:12px;width:fit-content}
.upload-rules>summary:hover{color:var(--accent)}
.upload-rules ul{margin:8px 0 0;padding-left:18px}
.upload-rules li{line-height:1.9}
.batch-card{margin-top:14px}
.batch-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.batch-head h2{margin:0;font-size:14px}
.batch-select{width:400px;max-width:100%}
.fail-line{margin:6px 0 0;font-size:12px;color:var(--el-color-danger)}
.batch-hint{margin:10px 0 0;font-size:12px;color:var(--text-tertiary)}
.resume-tabs{margin-bottom:4px}
@media(max-width:1150px){.filter-search{flex-basis:100%;max-width:none}.filter-item{width:calc(50% - 4px)}.candidate-results{overflow-x:auto}.overview-strip{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:900px){.overview-strip{grid-template-columns:1fr 1fr}.overview-stat:last-child{grid-column:1/-1}}
@media(max-width:760px){.filter-item{width:100%}.result-toolbar{flex-direction:column;gap:10px}.result-actions{width:100%}.sort-select{width:100%}.filter-more .el-select,.filter-more .el-input{width:100%}}
</style>
