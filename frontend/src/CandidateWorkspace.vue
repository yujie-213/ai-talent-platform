<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
import { categoryName, qualityName, indexName } from './labels'
const props = defineProps<{api: Api; canImport: boolean;canRequirements?:boolean;departments?:{id:string;name?:string}[]}>()
const emit = defineEmits<{open: [id: string]; task: [id: string]}>()
interface Candidate {id: string; name: string; kind: string; index_state: string; tags: {category: string; content: string; confirmed: boolean}[];requirements?:{requirement_id:string;title:string;score:number|null;state:string;group:string|null;stale:boolean;requirement_version:number|null;created_at:number|null;requirement_status:string}[]}
const filters = ref({kind: 'external', skill: '', education: '', experience: '', sort: 'name_asc',requirement_id:''})
const requirements=ref<{id:string;department_id?:string;draft:{title:string}}[]>([])
function requirementLabel(r:typeof requirements.value[number]){const department=props.departments?.find(d=>d.id===r.department_id)?.name;return (department?department+' · ':'')+(r.draft.title||'未命名需求')}
const groups:Record<string,string>={pass:'满足',unknown:'待核对',fail:'不满足',pending:'待处理',failed:'失败',unmatched:'未匹配',evaluated:'已评估'}
const items = ref<Candidate[]>([]), total = ref(0), page = ref(1), busy = ref(false)
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
  try {
    const params = new URLSearchParams({...filters.value, offset: String((page.value - 1) * 20), limit: '20'})
    const data = await props.api<{items: Candidate[]; total: number}>(`/candidates?${params}`)
    items.value = data.items; total.value = data.total
    batches.value = await props.api<string[]>('/imports')
  } catch (error) { ElMessage.error((error as Error).message) }
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
  <h1>候选人筛选</h1><p class="muted">默认外部候选人；筛选与人数均来自当前授权范围。技能表示简历声明，不代表测评通过。</p>
  <el-card><el-form inline><el-select v-model="filters.kind" style="width:150px"><el-option label="外部候选人" value="external"/><el-option label="内部员工" value="internal"/><el-option label="全部授权人才" value=""/></el-select><el-input v-model="filters.skill" placeholder="技能包含" style="width:150px"/><el-input v-model="filters.education" placeholder="教育原文包含，如本科" style="width:190px"/><el-input v-model="filters.experience" placeholder="经历原文包含" style="width:160px"/><el-select v-model="filters.sort" style="width:150px"><el-option label="姓名升序" value="name_asc"/><el-option label="姓名降序" value="name_desc"/><el-option label="档案版本降序" value="version_desc"/></el-select><el-button @click="page=1; load()">筛选</el-button></el-form>
  <el-select v-if="canRequirements" v-model="filters.requirement_id" clearable placeholder="应聘需求（仅显式关联者）" style="width:330px" @change="page=1;load()"><el-option v-for="r in requirements" :key="r.id" :label="requirementLabel(r)" :value="r.id"/></el-select><p>共 {{ total }} 人</p><el-table :data="items" @row-click="(row: Candidate) => emit('open', row.id)"><el-table-column prop="name" label="姓名"/><el-table-column label="分类事实"><template #default="s"><span class="fact-tag" v-for="tag in s.row.tags" :key="tag.id">{{categoryName[tag.category] || tag.category}} · {{tag.content}} · {{tag.confirmed?'已确认':'未确认'}}</span></template></el-table-column><el-table-column label="资料状态"><template #default="s">{{qualityName[s.row.quality] || s.row.quality}}</template></el-table-column><el-table-column label="检索索引状态"><template #default="s">{{indexName[s.row.index_state] || s.row.index_state}}</template></el-table-column><el-table-column label="岗位关联与已有匹配"><template #default="s"><p v-if="!s.row.requirements?.length">未关联应聘需求；仍可参加全范围匹配</p><p v-for="r in s.row.requirements||[]" :key="r.requirement_id">{{r.title}} · {{groups[r.group||r.state]||r.state}} · {{r.score??'—'}}<small v-if="r.requirement_version"> / 需求v{{r.requirement_version}} / {{new Date(r.created_at*1000).toLocaleString()}}</small><el-tag v-if="r.stale||r.requirement_status!=='active'" type="warning">旧结果 / 需求、档案或规则已变更</el-tag></p></template></el-table-column></el-table>
  <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="prev,pager,next" @current-change="load"/></el-card>
  <el-card v-if="canImport" style="margin-top:20px"><h2>导入简历</h2><p>PDF / PNG / JPEG / DOCX；单份10 MiB，PDF最多50页，每批最多20份。图片最多2500万像素，DOCX解压最多50 MiB/1000条目。</p><p class="muted">单文件解析最多12万字符、500个文字片段、100张文档图片。超时或失败会明确提示，最多执行3次。</p><p class="muted">导入先建立“待解析”档案；身份疑似重复时保留核对，不自动合并。</p><input ref="input" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.docx"/><el-button :loading="busy" @click="upload">上传并解析</el-button><el-button :disabled="busy" @click="resetBatch">新建另一批</el-button><p v-for="(item,i) in uploads" :key="i">{{item.name}}：{{item.state}} <el-button v-if="item.id" @click="emit('task',item.id)">进度与结果</el-button></p></el-card>
  <el-card style="margin-top:20px"><h2>导入与解析批次</h2><el-select v-model="selectedBatch" placeholder="选择历史批次（最多50个）" style="width:400px" @change="loadBatch"><el-option v-for="batch in batches" :key="batch" :label="batch" :value="batch"/></el-select><el-button @click="loadBatch">刷新逐文件对账</el-button><p v-for="item in batchTasks" :key="item.id">{{item.name}} · {{item.state}} · {{item.error_code}} <el-button @click="emit('task',item.id)">查看</el-button></p><p v-for="item in batchFailures" :key="item.id">{{item.name}} · 上传失败：{{item.message}}</p></el-card>
</template>

<style scoped>.fact-tag{display:block;white-space:normal;overflow-wrap:anywhere;font-size:13px;line-height:1.7;padding:4px 6px;margin:4px 0;color:#24584c;background:#edf6f2;border-radius:4px}.el-form{flex-wrap:wrap}</style>
