<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
import CandidateTable from './CandidateTable.vue'
import AppIcon from './AppIcon.vue'
import PageHeader from './PageHeader.vue'
import StatusTag from './StatusTag.vue'
import EmptyState from './EmptyState.vue'
import UuidShort from './UuidShort.vue'
import type {Candidate} from './candidate'
const props = defineProps<{api: Api; canImport: boolean;profileMode?:boolean;selfView?:boolean;title?:string;reloadToken?:number;canRequirements?:boolean;canChat?:boolean;departments?:{id:string;name?:string}[]}>()
const emit = defineEmits<{open: [id: string]; task: [id: string];chat:[scope:{kind:'selected'|'filtered';ids?:string[];filters?:Record<string,string>},labels?:Record<string,string>]}>()

const activeTab=ref('candidates')
const checkedIds=ref<string[]>([])
const loadError=ref('')
function toggleChecked(id:string){checkedIds.value=checkedIds.value.includes(id)?checkedIds.value.filter(x=>x!==id):[...checkedIds.value,id]}

const filters = ref({name:'',kind: '', skill: '', education: '', experience: '', sort: 'name_asc',requirement_id:'',minimum_education:'',minimum_experience_years:''})
const appliedFilters=ref<typeof filters.value|null>(null)
const moreOpen=ref(false)
// 已选条件按“常用在前”的固定顺序展示，避免输入顺序不同导致条件位置跳动。
const chipOrder=['name','kind','skill','minimum_education','minimum_experience_years','requirement_id','education','experience']
function filterEntries(source:Record<string,string>|null){
  if(!source)return []
  return chipOrder.filter(key=>source[key]).map(key=>[key,source[key]] as [string,string])
}
function chipText(key:string,value:string){
  if(key==='name')return `姓名含“${value}”`
  if(key==='kind')return value==='external'?'外部候选人':'内部员工'
  if(key==='requirement_id'){const r=requirements.value.find(r=>r.id===value);return r?requirementLabel(r):'指定岗位'}
  if(key==='minimum_education')return value+'及以上'
  if(key==='minimum_experience_years')return value+' 年及以上'
  if(key==='skill')return `技能含“${value}”`
  if(key==='education')return `教育原文含“${value}”`
  if(key==='experience')return `经历原文含“${value}”`
  return `${key}：${value}`
}
const chips=computed(()=>filterEntries(appliedFilters.value as unknown as Record<string,string>).map(([key,value])=>({key,text:chipText(key,value)})))
const appliedText=computed(()=>chips.value.length?chips.value.map(c=>c.text).join(' · '):'')
const moreCount=computed(()=>[filters.value.requirement_id,filters.value.education,filters.value.experience].filter(Boolean).length)
let searchTimer: ReturnType<typeof setTimeout> | undefined
let composing=false
function apply(){clearTimeout(searchTimer);page.value=1;void load()}
function scheduleSearch(){clearTimeout(searchTimer);++listRequest;loading.value=false;if(!composing)searchTimer=setTimeout(apply,300)}
function compositionStart(){composing=true;clearTimeout(searchTimer);++listRequest}
function compositionEnd(){composing=false;scheduleSearch()}
onBeforeUnmount(()=>{clearTimeout(searchTimer);++listRequest})
function clearChip(key:string){(filters.value as Record<string,string>)[key]='';apply()}
function clearAll(){filters.value={name:'',kind:'',skill:'',education:'',experience:'',sort:filters.value.sort,requirement_id:'',minimum_education:'',minimum_experience_years:''};apply()}
function chatFiltered(){if(!appliedFilters.value)return;const {sort,...scopeFilters}=appliedFilters.value;const filters:Record<string,string>={};for(const [key,value] of Object.entries(scopeFilters))if(value)filters[key]=value;emit('chat',{kind:'filtered',filters},{requirement_id:requirements.value.find(r=>r.id===scopeFilters.requirement_id)?requirementLabel(requirements.value.find(r=>r.id===scopeFilters.requirement_id)!):''})}

const kindOptions=[{label:'全部人才',value:''},{label:'外部候选人',value:'external'},{label:'内部员工',value:'internal'}]
// 快捷条件只表达后端真实支持的筛选口径；身份由左侧分段控件承担，这里不再重复。
const slices=[
  {key:'master',label:'硕士及以上',patch:{minimum_education:'硕士'}},
  {key:'bachelor',label:'本科及以上',patch:{minimum_education:'本科'}},
  {key:'exp3',label:'3 年以上经验',patch:{minimum_experience_years:'3'}},
  {key:'exp5',label:'5 年以上经验',patch:{minimum_experience_years:'5'}},
] as const
function sliceActive(patch:Record<string,string>){return Object.entries(patch).every(([key,value])=>(filters.value as Record<string,string>)[key]===value)}
function applySlice(patch:Record<string,string>){
  // 再次点击同一条件即取消，避免用户找不到“取消”的入口。
  const active=sliceActive(patch)
  for(const key of Object.keys(patch))(filters.value as Record<string,string>)[key]=''
  if(!active)for(const [key,value] of Object.entries(patch))(filters.value as Record<string,string>)[key]=value
  apply()
}

// 概览只展示真实统计：授权人才与解析任务状态；取不到时整块隐藏，不展示占位假数据。
interface WorkbenchSummary {people?:Record<string,number>;parse_tasks?:Record<string,number>}
const overview=ref<WorkbenchSummary|null>(null)
async function loadOverview(){if(props.selfView||props.profileMode)return;try{overview.value=await props.api<WorkbenchSummary>('/workbench')}catch{overview.value=null}}
const taskCounts=computed(()=>{const tasks=overview.value?.parse_tasks||{};const queued=tasks.queued||0,running=tasks.running||0,failed=tasks.failed||0,succeeded=tasks.succeeded||0;return{queued,running,failed,succeeded,total:queued+running+failed+succeeded}})
const resumeTotal=computed(()=>taskCounts.value.total)
const runningPct=computed(()=>resumeTotal.value?Math.round((taskCounts.value.queued+taskCounts.value.running)/resumeTotal.value*100):0)
const failedPct=computed(()=>resumeTotal.value?Math.round(taskCounts.value.failed/resumeTotal.value*100):0)

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

// 批次记录：优先用结构化概览（时间/文件数/状态统计），失败时退回只有批次编号的旧接口。
interface BatchItem {id:string;created_at:number|null;total:number;counts:Record<string,number>;names:string[]}
const batchList=ref<BatchItem[]>([])
const selectedBatch=ref('')
const batchTasks=ref<{id:string;name:string;state:string;error_code:string|null}[]>([])
const batchFailures=ref<{id:string;name:string;message:string}[]>([])
const uploadOpen=ref(false)
const batchRows=computed(()=>[
  ...batchTasks.value.map(task=>({id:task.id,name:task.name,state:task.state,detail:task.error_code||'',link:true})),
  ...batchFailures.value.map(fail=>({id:fail.id,name:fail.name,state:'rejected',detail:fail.message,link:false})),
])
function batchCount(item:BatchItem,keys:string[]){return keys.reduce((sum,key)=>sum+(item.counts[key]||0),0)}
const batchFailed=computed(()=>batchRows.value.filter(row=>row.state==='failed'||row.state==='rejected').length)
function timeText(stamp:number|null){return stamp?new Date(stamp*1000).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}):'待解析'}
async function loadBatches(){
  try{
    const data=await props.api<{items?:BatchItem[]}>('/imports/summary')
    if(data&&Array.isArray(data.items)){batchList.value=data.items;return}
    throw new Error('EMPTY')
  }catch{
    try{const ids=await props.api<string[]>('/imports');batchList.value=(ids||[]).map(id=>({id,created_at:null,total:0,counts:{},names:[]}))}
    catch{batchList.value=[]}
  }
}
async function openBatch(id:string){
  selectedBatch.value=id
  try{
    const result=await props.api<{tasks:typeof batchTasks.value;failures:typeof batchFailures.value}>(`/imports/${id}`)
    batchTasks.value=result.tasks;batchFailures.value=result.failures
  }catch(error){ElMessage.error((error as Error).message)}
}
function startImport(){activeTab.value='imports';uploadOpen.value=true;void loadBatches()}
let pendingUpload: {signature:string; batch:string; keys:string[]} | null = null
function resetBatch() {
  pendingUpload=null; uploads.value=[]
  clearPicked()
}
async function load() {
  clearTimeout(searchTimer)
  const request=++listRequest
  loading.value=true;loadError.value=''
  checkedIds.value=[]
  try {
    const requestedFilters={...filters.value,name:filters.value.name.trim(),skill:filters.value.skill.trim()}
    const params = new URLSearchParams({...Object.fromEntries(Object.entries(requestedFilters).filter(([,v])=>v!=='')), offset: String((page.value - 1) * 20), limit: '20'})
    const data = await props.api<{items: Candidate[]; total: number}>(`/candidates?${params}`)
    if(request!==listRequest)return
    items.value = data.items; total.value = data.total;appliedFilters.value=requestedFilters
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
  busy.value = false; clearPicked()
  await load(); await loadBatches(); await openBatch(batch)
}
watch(()=>props.reloadToken,()=>void load())
onMounted(async()=>{void loadOverview();if(!props.profileMode)void loadBatches();await load();if(props.canRequirements){try{let offset=0;const all:typeof requirements.value=[];while(true){const data=await props.api<{items:typeof requirements.value;total:number}>(`/requirements?offset=${offset}&limit=100`);all.push(...data.items);if(!data.items.length||all.length>=data.total)break;offset+=data.items.length}requirements.value=all}catch(error){ElMessage.error((error as Error).message)}}})
</script>
<template>
  <PageHeader :title="title||'简历筛选'" :subtitle="profileMode?'查看授权范围内的人才档案，按姓名、身份与学历经验筛选。':'上传简历后自动解析建档，再按姓名、身份、学历与经验收窄范围。'">
    <slot name="actions"/>
    <el-button v-if="!profileMode" @click="activeTab=activeTab==='imports'?'candidates':'imports';loadBatches()">{{activeTab==='imports'?'返回筛选':'解析历史'}}</el-button>
    <el-button v-if="canImport" type="primary" @click="startImport">＋ 上传简历</el-button>
  </PageHeader>

  <div v-if="overview" class="overview-strip" aria-label="解析与人才范围概览">
    <div class="ov-card tone-blue">
      <div class="ov-head"><span class="ov-icon"><AppIcon name="file"/></span><span class="ov-label">解析简历总数</span></div>
      <strong class="ov-value">{{resumeTotal}}</strong>

    </div>
    <div class="ov-card tone-amber">
      <div class="ov-head"><span class="ov-icon"><AppIcon name="clock"/></span><span class="ov-label">解析进行中</span></div>
      <strong class="ov-value">{{taskCounts.queued+taskCounts.running}}</strong>
      <p class="ov-note"><span class="legend">排队 {{taskCounts.queued}}</span><span class="legend">执行 {{taskCounts.running}}</span></p>
      <div class="ov-bar" aria-hidden="true"><i class="seg amber" :style="{width:runningPct+'%'}"/></div>
    </div>
    <div class="ov-card tone-red" :class="{attention:taskCounts.failed>0}">
      <div class="ov-head"><span class="ov-icon"><AppIcon name="check"/></span><span class="ov-label">失败任务</span></div>
      <strong class="ov-value">{{taskCounts.failed}}</strong>
      <p class="ov-note">{{taskCounts.failed>0?'到导入与解析记录里逐份查看原因':'当前没有失败任务'}}</p>
      <div class="ov-bar" aria-hidden="true"><i class="seg red" :style="{width:failedPct+'%'}"/></div>
    </div>
  </div>



  <div v-show="activeTab==='candidates'" class="candidate-list-page">
  <form v-if="!selfView" class="filter-card" @submit.prevent="apply">
    <div class="filter-head">
      <span class="filter-title">筛选条件</span>
      <div class="filter-head-right">
        <span v-if="chips.length" class="filter-count">{{chips.length}} 个条件</span>
        <button type="button" class="reset-btn" :disabled="!chips.length" @click="clearAll">重置</button>
      </div>
    </div>
    <div v-if="profileMode" class="filter-main">
      <el-input v-model="filters.name" class="f-name" placeholder="姓名包含，如 杨" clearable aria-label="姓名" @input="scheduleSearch" @clear="apply" @compositionstart="compositionStart" @compositionend="compositionEnd"/>
      <el-input v-model="filters.skill" class="f-skill" placeholder="搜索技能关键词，如 Python" clearable aria-label="技能关键词" @input="scheduleSearch" @clear="apply" @compositionstart="compositionStart" @compositionend="compositionEnd"/>


    </div>
    <div v-if="!profileMode&&canRequirements" class="filter-quick" aria-label="应聘岗位" @change="apply">
      <button type="button" class="slice-chip" :class="{active:!filters.requirement_id}" @click="filters.requirement_id='';apply()">全部岗位</button>
      <button v-for="r in requirements" :key="r.id" type="button" class="slice-chip" :class="{active:filters.requirement_id===r.id}" :aria-pressed="filters.requirement_id===r.id" @click="filters.requirement_id=r.id;apply()">{{requirementLabel(r)}}</button>
    </div>
    <div class="filter-quick">
      <template v-if="profileMode"><button v-for="option in kindOptions" :key="option.value" type="button" class="slice-chip" :class="{active:filters.kind===option.value}" :aria-pressed="filters.kind===option.value" @click="filters.kind=option.value;apply()">{{option.label}}</button></template>

      <button v-for="s in slices" :key="s.key" type="button" class="slice-chip" :class="{active:sliceActive(s.patch)}" :aria-pressed="sliceActive(s.patch)" @click="applySlice(s.patch)">{{s.label}}</button>
      <button type="button" class="filter-toggle" :aria-expanded="moreOpen" @click="moreOpen=!moreOpen">更多筛选<span v-if="moreCount" class="filter-badge">{{moreCount}}</span><span class="chevron" :class="{open:moreOpen}" aria-hidden="true"/></button>
    </div>
    <div v-show="moreOpen" class="filter-more">
      <template v-if="!profileMode">
        <el-input v-model="filters.name" placeholder="姓名包含，如 杨" clearable aria-label="姓名" @input="scheduleSearch" @compositionstart="compositionStart" @compositionend="compositionEnd"/>
        <el-input v-model="filters.skill" placeholder="技能关键词" clearable aria-label="技能关键词" @input="scheduleSearch" @compositionstart="compositionStart" @compositionend="compositionEnd"/>
        <el-segmented v-model="filters.kind" :options="kindOptions" aria-label="人才身份" @change="apply"/>
      </template>
      <el-select v-model="filters.minimum_education" clearable placeholder="最低学历" aria-label="最低学历" @change="apply"><el-option label="不限学历" value=""/><el-option v-for="degree in ['高中','大专','本科','硕士','博士']" :key="degree" :label="degree+'及以上'" :value="degree"/></el-select>
      <el-select v-model="filters.minimum_experience_years" clearable placeholder="工作年限" aria-label="总工作经验" @change="apply"><el-option label="不限年限" value=""/><el-option v-for="years in [1,3,5,8,10]" :key="years" :label="years+' 年及以上'" :value="String(years)"/></el-select>
      <el-select v-if="canRequirements" v-model="filters.requirement_id" clearable placeholder="应聘岗位（仅显式关联者）" aria-label="应聘岗位" @change="apply"><el-option v-for="r in requirements" :key="r.id" :label="requirementLabel(r)" :value="r.id"/></el-select>
      <el-input v-model="filters.education" clearable placeholder="教育原文包含，如本科" aria-label="教育原文" @input="scheduleSearch"/>
      <el-input v-model="filters.experience" clearable placeholder="经历原文包含" aria-label="经历原文" @input="scheduleSearch"/>

    </div>
    <div v-if="chips.length" class="filter-chips">
      <span class="chips-label">已选条件</span>
      <el-tag v-for="chip in chips" :key="chip.key" closable @close="clearChip(chip.key)">{{chip.text}}</el-tag>
      <button type="button" class="chip-clear" @click="clearAll">清除全部</button>
    </div>
  </form>

  <div class="result-toolbar">
    <div class="result-count"><strong>{{total}}</strong><span> 人</span><p class="muted" data-testid="applied-filters">{{appliedText||'当前授权范围'}} · 每页 20 人</p></div>
    <div class="result-actions">
      <el-select v-model="filters.sort" class="sort-select" aria-label="排序方式" @change="apply"><el-option label="姓名升序" value="name_asc"/><el-option label="姓名降序" value="name_desc"/><el-option label="档案版本降序" value="version_desc"/></el-select>
      <template v-if="canChat"><el-button :disabled="loading||!checkedIds.length" @click="emit('chat',{kind:'selected',ids:[...checkedIds]})">比较 / 问答（{{checkedIds.length}}）</el-button><el-button :disabled="loading||!appliedFilters" @click="chatFiltered">按筛选范围问答</el-button></template>
    </div>
  </div>
  <p v-if="canChat" class="muted scope-note">范围问答使用已应用条件下全部 {{total}} 人；勾选限本页。学历和总工作年限仅包含有明确依据的满足者，资料未知不计为满足。</p>
  <el-alert v-if="loadError" :title="loadError" type="error" :closable="false"><el-button @click="load">重新加载</el-button></el-alert>
  <div v-loading="loading" class="candidate-results">
    <CandidateTable :items="items" :selected="checkedIds" :can-chat="canChat" @toggle="toggleChecked" @open="emit('open',$event)" @select-page="checkedIds=$event?items.map(p=>p.id):[]"/>
  </div>
  <EmptyState v-if="!loading&&!loadError&&!items.length" title="没有符合条件的人才" :hint="chips.length?'可以减少筛选条件，或清空姓名与身份限制后重试。':'当前授权范围内还没有已建档的简历，可先上传简历。'" :action-label="canImport?'上传简历':undefined" @action="startImport"/>
  <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="total,prev,pager,next" @current-change="load"/>
  </div>

  <div v-show="activeTab==='imports'" id="resume-import" class="import-page">
    <div class="import-head">
      <div class="import-title">
        <h2>导入与解析记录</h2>
        <p class="muted">每次上传是一个批次；点开批次可查看逐份文件的解析结果与失败原因。</p>
      </div>
      <div class="import-actions">
        <el-button @click="loadBatches">刷新记录</el-button>
        <el-button v-if="canImport" type="primary" @click="uploadOpen=true">＋ 上传新简历</el-button>
      </div>
    </div>

    <el-card class="batch-list-card">
      <el-table :data="batchList" class="batch-table">
        <el-table-column label="批次" width="210"><template #default="{row}"><UuidShort :id="row.id"/></template></el-table-column>
        <el-table-column label="导入时间" width="150"><template #default="{row}"><span class="batch-time">{{timeText(row.created_at)}}</span></template></el-table-column>
        <el-table-column label="文件" width="80"><template #default="{row}"><span class="batch-total">{{row.total||'—'}}</span></template></el-table-column>
        <el-table-column label="解析结果" min-width="260">
          <template #default="{row}">
            <div class="batch-states">
              <StatusTag v-if="batchCount(row,['succeeded','success','completed'])" state="succeeded" :label="'成功 '+batchCount(row,['succeeded','success','completed'])"/>
              <StatusTag v-if="batchCount(row,['running'])" state="running" :label="'执行 '+batchCount(row,['running'])"/>
              <StatusTag v-if="batchCount(row,['queued'])" state="queued" :label="'排队 '+batchCount(row,['queued'])"/>
              <StatusTag v-if="batchCount(row,['failed'])" state="failed" :label="'失败 '+batchCount(row,['failed'])"/>
              <StatusTag v-if="batchCount(row,['rejected'])" state="rejected" :label="'未接收 '+batchCount(row,['rejected'])"/>
              <span v-if="!Object.keys(row.counts||{}).length" class="muted">暂无逐文件状态</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="文件预览" min-width="220"><template #default="{row}"><span class="batch-names">{{(row.names||[]).join('、')||'—'}}</span></template></el-table-column>
        <el-table-column label="操作" width="110" align="right"><template #default="{row}"><el-button link type="primary" @click="openBatch(row.id)">查看明细</el-button></template></el-table-column>
      </el-table>
      <EmptyState v-if="!batchList.length" icon="file" title="还没有导入记录" hint="上传简历后会按批次记录每份文件的解析结果与失败原因。" :action-label="canImport?'上传简历':undefined" @action="uploadOpen=true"/>
    </el-card>

    <el-card v-if="selectedBatch" class="batch-detail-card">
      <template #header>
        <div class="detail-head">
          <div class="detail-title"><h2>批次明细</h2><UuidShort :id="selectedBatch"/></div>
          <div class="detail-actions"><StatusTag v-if="batchFailed" state="failed" :label="batchFailed+' 份未成功'"/><el-button link type="primary" @click="openBatch(selectedBatch)">刷新</el-button></div>
        </div>
      </template>
      <el-table :data="batchRows" class="batch-table">
        <el-table-column label="文件" min-width="240" prop="name"/>
        <el-table-column label="状态" width="110"><template #default="{row}"><StatusTag :state="row.state"/></template></el-table-column>
        <el-table-column label="说明" min-width="200"><template #default="{row}"><span :class="row.detail?'detail-error':'muted'">{{row.detail||'—'}}</span></template></el-table-column>
        <el-table-column label="操作" width="100" align="right"><template #default="{row}"><el-button v-if="row.link" link type="primary" @click="emit('task',row.id)">查看进度</el-button></template></el-table-column>
      </el-table>
      <p v-if="!batchRows.length" class="muted batch-hint">该批次没有可显示的文件记录，可能已被权限回收。</p>
    </el-card>

    <el-card v-if="canImport&&uploadOpen" class="upload-card">
      <template #header><div class="upload-head"><h2>上传新简历</h2><el-button link @click="uploadOpen=false">收起</el-button></div></template>
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
    </el-card>
  </div>
</template>

<style scoped>
/* ---------- 概览三卡：图标 + 数字 + 构成条，全部来自真实统计 ---------- */
.overview-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 16px}
.ov-card{position:relative;display:flex;flex-direction:column;gap:6px;padding:15px 18px 16px;background:var(--surface);border:1px solid var(--border);border-radius:14px;box-shadow:var(--shadow)}
.ov-head{display:flex;align-items:center;gap:8px}
.ov-icon{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;flex-shrink:0}
.ov-icon :deep(svg){width:16px;height:16px}
.ov-label{font-size:12.5px;color:var(--text-secondary)}
.ov-value{font-size:27px;font-weight:600;line-height:1.15;letter-spacing:-.6px;font-variant-numeric:tabular-nums}
.ov-note{display:flex;align-items:center;gap:12px;margin:0;font-size:11.5px;color:var(--text-tertiary)}
.legend{display:inline-flex;align-items:center;gap:5px}
.dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.dot.blue{background:#2f5bea}
.dot.teal{background:#0f766e}
.ov-bar{display:flex;height:5px;margin-top:2px;border-radius:3px;background:var(--surface-muted);overflow:hidden}
.ov-bar .seg{display:block;height:100%;transition:width .3s ease}
.ov-bar .seg.blue{background:#2f5bea}
.ov-bar .seg.teal{background:#0f766e}
.ov-bar .seg.amber{background:#d99426}
.ov-bar .seg.red{background:#c0393f}
.tone-blue .ov-icon{background:#eef2fe;color:#2f5bea}
.tone-amber .ov-icon{background:#fbf3e3;color:#b07a1e}
.tone-red .ov-icon{background:var(--surface-muted);color:var(--text-tertiary)}
.tone-red.attention .ov-icon{background:#faeaea;color:#c0393f}
.tone-red.attention .ov-value{color:#b4231f}

/* ---------- 筛选卡 ---------- */
.filter-card{display:flex;flex-direction:column;gap:11px;padding:14px 16px 15px;margin:0 0 16px;background:var(--surface);border:1px solid var(--border);border-radius:14px;box-shadow:var(--shadow)}
.filter-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.filter-title{font-size:13px;font-weight:600;color:var(--text)}
.filter-head-right{display:flex;align-items:center;gap:10px}
.filter-count{font-size:11.5px;color:var(--accent);background:var(--accent-soft);border-radius:999px;padding:2px 8px}
.reset-btn{border:0;background:transparent;color:var(--text-secondary);font-size:12px;cursor:pointer;padding:2px 2px;border-radius:4px}
.reset-btn:hover:not(:disabled){color:var(--accent)}
.reset-btn:disabled{opacity:.45;cursor:default}
.filter-main{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.f-name{flex:1 1 190px;max-width:260px}
.f-skill{flex:1 1 190px;max-width:300px}
.f-kind{flex-shrink:0}
.filter-quick{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding-top:10px;border-top:1px solid var(--border)}
.quick-label{font-size:12px;color:var(--text-tertiary);flex-shrink:0}
.slice-chip{border:1px solid var(--border);background:var(--surface);color:var(--text-secondary);border-radius:999px;padding:4px 12px;font-size:12px;line-height:1.5;cursor:pointer;transition:all .15s}
.slice-chip:hover{border-color:var(--accent);color:var(--accent)}
.slice-chip.active{border-color:var(--accent);background:var(--accent-soft);color:var(--accent);font-weight:500}
.filter-toggle{display:inline-flex;align-items:center;gap:4px;margin-left:auto;padding:4px 2px;border:0;background:transparent;color:var(--text-secondary);font-size:12px;cursor:pointer}
.filter-toggle:hover{color:var(--accent)}
.filter-badge{display:inline-grid;place-items:center;min-width:16px;height:16px;padding:0 4px;border-radius:8px;background:var(--accent-soft);color:var(--accent);font-size:10px;line-height:1}
.chevron{width:0;height:0;margin-top:2px;border-left:4px solid transparent;border-right:4px solid transparent;border-top:5px solid var(--text-tertiary);transition:transform .15s}
.chevron.open{transform:rotate(180deg)}
.filter-more{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding-top:10px;border-top:1px dashed var(--border)}
.filter-more .el-select{width:210px}
.filter-more .el-input{width:180px}
.filter-chips{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding-top:10px;border-top:1px dashed var(--border)}
.chips-label{font-size:12px;color:var(--text-tertiary)}
.chip-clear{border:0;background:transparent;color:var(--text-secondary);font-size:12px;cursor:pointer;padding:2px;text-decoration:underline;text-underline-offset:3px}
.chip-clear:hover{color:var(--accent)}

/* ---------- 结果区 ---------- */
.candidate-list-page{display:flex;flex-direction:column}
.result-toolbar{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin:0 0 12px}
.result-count{display:flex;align-items:baseline;gap:4px;flex-wrap:wrap;min-width:0}
.result-count strong{font-size:17px;font-weight:600;font-variant-numeric:tabular-nums}
.result-count>span{font-size:13px;color:var(--text-secondary)}
.result-count p{flex-basis:100%;margin:2px 0 0;font-size:12px}
.result-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.result-actions .el-button{margin:0}
.sort-select{width:136px}
.scope-note{margin:0 0 10px;font-size:12px}
.candidate-results{background:var(--surface);border:1px solid var(--border);border-radius:14px;overflow:hidden}
.candidate-results :deep(.el-table){margin:0}
.resume-tabs{margin-bottom:4px}

/* ---------- 导入与解析记录 ---------- */
.import-page{display:flex;flex-direction:column;gap:14px}
.import-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.import-title h2{margin:0;font-size:15px;font-weight:600}
.import-title p{margin:4px 0 0;font-size:12px}
.import-actions{display:flex;align-items:center;gap:8px;flex-shrink:0}
.import-actions .el-button{margin:0}
.batch-list-card :deep(.el-card__body),.batch-detail-card :deep(.el-card__body){padding:0}
.batch-table :deep(.el-table__cell){padding:9px 0}
.batch-time{font-size:12.5px;color:var(--text-secondary);font-variant-numeric:tabular-nums}
.batch-total{font-variant-numeric:tabular-nums;font-weight:550}
.batch-states{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.batch-names{display:block;font-size:12px;color:var(--text-tertiary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.detail-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.detail-title{display:flex;align-items:center;gap:10px}
.detail-title h2{margin:0;font-size:14px;font-weight:600}
.detail-actions{display:flex;align-items:center;gap:8px}
.detail-error{font-size:12px;color:var(--el-color-danger)}
.batch-hint{margin:12px 0 0;font-size:12px;padding:0 16px 4px}

/* ---------- 上传区 ---------- */
.upload-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.upload-head h2{margin:0;font-size:14px;font-weight:600}
.upload-zone{display:flex;flex-direction:column;align-items:center;gap:8px;padding:24px 16px;border:1.5px dashed #c3cad8;border-radius:12px;background:var(--surface);cursor:pointer;text-align:center;transition:border-color .15s,background .15s}
.upload-zone:hover,.upload-zone.dragging{border-color:var(--accent);background:var(--accent-soft)}
.upload-zone.dragging{border-style:solid}
.upload-icon{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;background:var(--surface);color:var(--accent);box-shadow:var(--shadow)}
.upload-icon :deep(svg){width:19px;height:19px}
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
.upload-actions{display:flex;align-items:center;gap:10px;margin-top:14px;flex-wrap:wrap}
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

@media(max-width:1180px){.f-name,.f-skill{max-width:none;flex:1 1 220px}}
@media(max-width:900px){.overview-strip{grid-template-columns:1fr}.filter-toggle{margin-left:0}}
@media(max-width:760px){.f-name,.f-skill{flex-basis:100%;max-width:none}.f-kind{width:100%}.filter-more .el-select,.filter-more .el-input{width:100%}.result-toolbar{flex-direction:column;gap:10px}.result-actions{width:100%}.sort-select{width:100%}.import-head{flex-direction:column}.import-actions{width:100%}.candidate-results{overflow-x:auto}}
</style>