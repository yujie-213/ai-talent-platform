<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createApi } from './api'
import { errorName, categoryName } from './labels'
import CandidateWorkspace from './CandidateWorkspace.vue'
import RequirementWorkspace from './RequirementWorkspace.vue'
import ExtractionResult from './ExtractionResult.vue'
import AssessmentWorkspace from './AssessmentWorkspace.vue'
import Workbench from './Workbench.vue'
import LogWorkspace from './LogWorkspace.vue'
import ChatWorkspace, {type ChatScope} from './ChatWorkspace.vue'
import RoleWorkspace from './RoleWorkspace.vue'
import AppIcon from './AppIcon.vue'
import ProfileFacts from './ProfileFacts.vue'
import ProfileWorkspace from './ProfileWorkspace.vue'
import AccountWorkspace from './AccountWorkspace.vue'
import CatalogWorkspace from './CatalogWorkspace.vue'
interface Grant { action: string; scope: string; scope_id: string | null }
interface Me { id: string; username: string; menus?:string[]; grants: Grant[] }
interface Fact {id?:string;quote?:string;locator?:string;source_task_id?:string;source_file_id?:string;category: string; content: string; confirmed?: boolean; source_type?: string; source_version?: number}
interface Talent {id: string; kind: string; name: string; phone: string; email: string; department_id: string | null; department_position_id: string | null; owner_id: string | null; pool_id: string | null; version: number; field_states?: {field:string;confirmed:boolean;source_type:string;source_version:number}[]; facts?: Fact[]; history?: {version: number; actor_id: string; changed_fields: string[]; created_at: number}[]}
interface CatalogItem {id: string; enabled: boolean; version: number; name?: string; department_id?: string; position_id?: string}
interface FileItem {id: string; original_name: string; size: number}
interface Task {id: string; talent_id?: string; retryable?: boolean; state: string; run_version: number; error_code: string | null; result: string | null}
interface TaskDetail extends Task { attempts: {run_version: number; state: string}[] }
const auth = ref(''), me = ref<Me | null>(null), page = ref('workbench'), busy = ref(false)
const login = ref({username: '', password: ''}), talents = ref<Talent[]>([]), total = ref(0), offset = ref(0)
const catalog = ref<Record<string, CatalogItem[]>>({departments: [], positions: [], department_positions: [], pools: []})
const selected = ref<Talent | null>(null), edit = ref(false), files = ref<FileItem[]>([]), tasks = ref<Task[]>([])
const taskPage = ref(1), taskTotal = ref(0), taskPageSize = 20
const focusedTaskId = ref<string | null>(null), focusedTask = ref<TaskDetail | null>(null)
let taskListRequest = 0
const profileReload=ref(0)
const scopeChat=ref(false)
const chatContext = ref<ChatScope>({kind:'selected',ids:[]})
const chatFilterLabels=ref<Record<string,string>>({})
async function openChat(scope:ChatScope,labels:Record<string,string>={}){chatContext.value=scope;chatFilterLabels.value=labels;scopeChat.value=true}
const uploadInput = ref<HTMLInputElement | null>(null)
const createKey = ref(crypto.randomUUID()), uploadKey = ref(crypto.randomUUID())
const menuVisible=(key:string)=>me.value?.menus?me.value.menus.includes(key):true
const can = (action: string) => me.value?.grants.some(g => g.action === action) ?? false
const departmentName = (id: string | null) => catalog.value.departments.find(d => d.id === id)?.name || '—'
const positionOptions = computed(() => catalog.value.department_positions.filter(p => p.department_id === selected.value?.department_id))
const positionName = (id?: string) => catalog.value.positions.find(p => p.id === id)?.name || id
const stateName: Record<string,string> = {queued:'待处理', running:'处理中', succeeded:'成功', failed:'失败'}
const api = createApi(() => auth.value, logout)
async function run(fn: () => Promise<void>) { busy.value = true; try { await fn() } catch (e) { ElMessage.error((e as Error).message) } finally { busy.value = false } }
function logout() { profileCitation.value=null;scopeChat.value=false;detailRequest++; auth.value = ''; me.value = null; talents.value = []; selected.value = null; files.value = []; tasks.value = []; taskPage.value = 1; taskTotal.value = 0; focusedTaskId.value = null; focusedTask.value = null; taskListRequest++; login.value.password = '' }
async function signIn() { await run(async () => { const result = await api<{token: string}>('/auth/login', 'POST', login.value); auth.value = result.token; login.value.password = ''; me.value = await api<Me>('/auth/me'); catalog.value = await api('/catalog'); await navigate(me.value?.menus?.includes('workbench') || !me.value?.menus ? 'workbench' : me.value.menus[0] || 'no-menus') }) }
async function loadTalents() { const result = await api<{items: Talent[]; total: number}>(`/talents?offset=${offset.value}&limit=20`); talents.value = result.items; total.value = result.total }
let detailRequest=0
async function openTalent(t: Talent) { const request=++detailRequest,session=auth.value;await run(async () => { const [profile,sourceFiles]=await Promise.all([api<Talent>(`/talents/${t.id}`),can('file.read')?api<FileItem[]>(`/talents/${t.id}/files`):Promise.resolve([])]);if(request!==detailRequest||session!==auth.value)return;selected.value=profile;files.value=sourceFiles;edit.value=false }) }
async function closeProfile(){if(edit.value){try{await ElMessageBox.confirm('当前编辑尚未保存，返回将放弃这些修改。','离开档案编辑',{confirmButtonText:'放弃修改并返回',cancelButtonText:'继续编辑',type:'warning'})}catch{return}}selected.value=null;detailRequest++}
const profileCitation=ref<Fact|null>(null)
async function profileSource(fact:Fact){const id=selected.value?.id,ticket=detailRequest;if(!id)return;await run(async()=>{const current=await api<Talent>(`/talents/${id}`);if(selected.value?.id!==id||ticket!==detailRequest)return;const fresh=current.facts?.find(f=>f.id===fact.id);if(!fresh){ElMessage.info('该事实已更新，请重新打开档案核对');return}profileCitation.value=fresh})}
function newTalent() { selected.value = {id: '', kind: 'external', name: '', phone: '', email: '', department_id: null, department_position_id: null, owner_id: me.value!.id, pool_id: null, version: 1, facts: []}; files.value = []; edit.value = true; createKey.value = crypto.randomUUID() }
async function saveTalent() {
  await run(async () => {
    const t = selected.value!, session = auth.value
    const body = {kind:t.kind,name:t.name,phone:t.phone,email:t.email,department_id:t.department_id,department_position_id:t.department_position_id,owner_id:t.owner_id,pool_id:t.pool_id,facts:(t.facts || []).map(f => ({category:f.category,content:f.content}))}
    const saved = await api<Talent>(t.id ? `/talents/${t.id}` : '/talents', t.id ? 'PUT' : 'POST', t.id ? {...body, version:t.version} : body, t.id ? undefined : createKey.value)
    if (session !== auth.value) return
    // 用户保存期间关闭或切换详情，迟到响应不能重新打开旧档案。
    if (selected.value === t) { selected.value = saved; edit.value = false }
    await loadTalents();profileReload.value++
    ElMessage.success('档案已保存')
  })
}
async function upload() { await run(async () => { const file = uploadInput.value?.files?.[0]; if (!file || !selected.value?.id) return; const form = new FormData(); form.append('file', file); await api(`/talents/${selected.value.id}/files`, 'POST', form, uploadKey.value); uploadKey.value = crypto.randomUUID(); files.value = await api(`/talents/${selected.value.id}/files`); ElMessage.success('文件已保存，可点击解析简历') }) }
async function download(file: FileItem) { await run(async () => { const res = await fetch(`/api/files/${file.id}/download`, {headers:{Authorization:`Bearer ${auth.value}`}}); if (!res.ok) throw new Error('文件不可用或授权已变化'); const url = URL.createObjectURL(await res.blob()); const a = document.createElement('a'); a.href = url; a.download = file.original_name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000) }) }
async function parseFile(file: FileItem) { await run(async () => { const task = await api<Task>(`/files/${file.id}/parse`, 'POST', undefined, crypto.randomUUID()); selected.value=null;detailRequest++; page.value='tasks'; focusedTaskId.value=task.id;focusedTask.value=null; await refreshTasks() }) }
async function loadTasks() {
  const request = ++taskListRequest, requestedPage = taskPage.value, session = auth.value
  const result = await api<{items: Task[]; total: number}>(`/tasks?offset=${(requestedPage - 1) * taskPageSize}&limit=${taskPageSize}`)
  if (request !== taskListRequest || session !== auth.value || requestedPage !== taskPage.value) return
  const lastPage = Math.max(1, Math.ceil(result.total / taskPageSize))
  if (requestedPage > lastPage) { taskPage.value = lastPage; await loadTasks(); return }
  tasks.value = result.items
  taskTotal.value = result.total
}
async function loadFocusedTask() {
  const id = focusedTaskId.value, session = auth.value
  if (!id) return
  try {
    const detail = await api<TaskDetail>(`/tasks/${id}`)
    if (id === focusedTaskId.value && session === auth.value) focusedTask.value = detail
  } catch (error) {
    if (id === focusedTaskId.value && session === auth.value) { focusedTaskId.value = null; focusedTask.value = null }
    throw error
  }
}
async function refreshTasks() { await Promise.all([loadTasks(), loadFocusedTask()]) }
async function openTask(t: Task) { focusedTaskId.value = t.id; focusedTask.value = null; await run(loadFocusedTask) }
async function changeTaskPage(value: number) { taskPage.value = value; await run(loadTasks) }
async function retry(t: Task) { await run(async () => { await api(`/tasks/${t.id}/retry`, 'POST', {version:t.run_version}); await refreshTasks() }) }
async function navigate(p: string) { if(selected.value)await closeProfile();if(selected.value)return;profileCitation.value=null;scopeChat.value=false;page.value = p; await run(async () => { me.value = await api('/auth/me'); if(!menuVisible(p)){page.value='no-menus';return} if (p === 'talents') await loadTalents(); if (p === 'tasks') await refreshTasks();  }) }
function resetUploadKey() { uploadKey.value = crypto.randomUUID() }

const selfView=computed(()=>!!me.value?.grants.some(g=>g.action==='talent.read')&&me.value.grants.filter(g=>g.action==='talent.read').every(g=>g.scope==='self'))
const requirementEntry=ref<{id:string;runId?:string;serial:number}>()
async function openRequirement(entry:{id:string;runId?:string}){requirementEntry.value={...entry,serial:Date.now()};await navigate('requirements')}
const navGroups=computed(()=>[
 {label:'业务工作区',items:[{key:'workbench',name:'工作台',icon:'grid',allowed:true},{key:'candidates',name:'简历筛选',icon:'file',allowed:can('talent.read')&&!selfView.value},{key:'talents',name:selfView.value?'我的档案':'人才画像',icon:'people',allowed:can('talent.read')},{key:'requirements',name:'岗位与匹配',icon:'case',allowed:can('requirement.read')},{key:'assessments',name:selfView.value?'我的测评':'轻量测评',icon:'check',allowed:can('talent.read')||can('assessment.manage')||can('assessment.read')||can('assessment.assign')}]},
 {label:'记录与工具',items:[{key:'chat',name:'问答与历史',icon:'chat',allowed:can('chat.use')},{key:'tasks',name:'解析任务',icon:'clock',allowed:can('talent.read')&&!selfView.value}]},
 {label:'系统管理',items:[{key:'accounts',name:'账号管理',icon:'people',allowed:can('account.manage')},{key:'roles',name:'角色与菜单权限',icon:'shield',allowed:can('account.manage')},{key:'catalog',name:'基础资料',icon:'grid',allowed:can('catalog.manage')},{key:'audit',name:'操作审计',icon:'clock',allowed:can('audit.read')}]}
].map(group=>({...group,items:group.items.filter(item=>item.allowed&&menuVisible(item.key))})).filter(group=>group.items.length))
const managementItems=computed(()=>navGroups.value.find(g=>g.label==='系统管理')?.items||[])
const inManagement=computed(()=>managementItems.value.some(i=>i.key===page.value))
const currentTitle=computed(()=>navGroups.value.flatMap(group=>group.items).find(item=>item.key===page.value)?.name||'工作空间')

let timer: ReturnType<typeof setInterval>
onMounted(() => { timer = setInterval(() => { if (auth.value && page.value === 'tasks' && (tasks.value.some(t => ['queued','running'].includes(t.state)) || (focusedTask.value && ['queued','running'].includes(focusedTask.value.state)))) void run(refreshTasks) }, 3000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <main v-if="!me" class="login-page"><section class="intro"><div class="brand">AI 数字化人才平台</div><h1>人才信息，有据可循。</h1><p>从简历筛选、人才画像到岗位匹配与测评。</p></section><el-card class="login-card"><h2>登录工作台</h2><p class="muted">使用已获授权的账号进入工作空间</p><el-form @submit.prevent="signIn" label-position="top"><el-form-item label="账号"><el-input v-model="login.username" autocomplete="username" /></el-form-item><el-form-item label="密码"><el-input v-model="login.password" type="password" show-password autocomplete="current-password" /></el-form-item><el-button native-type="submit" type="primary" :loading="busy">登录</el-button></el-form></el-card></main>
  <div v-else class="workspace"><a href="#workspace-content" class="skip-link">跳到工作区</a>
    <aside class="app-sidebar"><div class="brand"><span class="brand-mark">AI</span><div>AI 数字化人才平台<span>TALENT WORKSPACE</span></div></div><nav aria-label="主导航"><section v-for="group in navGroups" :key="group.label" class="nav-group"><p>{{group.label}}</p><button v-if="group.label==='系统管理'" :class="{active:inManagement}" :aria-current="inManagement?'page':undefined" aria-label="系统管理" title="系统管理" @click="navigate(group.items[0].key)"><AppIcon name="shield"/>系统管理</button><template v-else><button v-for="item in group.items" :key="item.key" :class="{active:page===item.key}" :aria-current="page===item.key?'page':undefined" :aria-label="item.name" :title="item.name" @click="navigate(item.key)"><AppIcon :name="item.icon"/>{{item.name}}</button></template></section></nav><footer>当前授权工作空间</footer></aside>
    <section class="content" id="workspace-content" tabindex="-1"><header class="app-header"><span>AI 数字化人才平台 <span class="breadcrumb-divider">/</span> <strong>{{currentTitle}}</strong></span><div class="user-menu"><span class="user-avatar" aria-hidden="true">{{me.username.slice(0,1).toUpperCase()}}</span>{{ me.username }} <el-button text @click="logout">退出登录</el-button></div></header>
      <div v-show="!selected" class="workspace-page"><nav v-if="inManagement" class="management-tabs" aria-label="系统管理分区"><button v-for="item in managementItems" :key="item.key" :class="{active:page===item.key}" :aria-current="page===item.key?'page':undefined" @click="navigate(item.key)">{{item.name}}</button></nav>
      <el-empty v-if="page==='no-menus'" description="当前账号没有已配置的可见菜单，请联系账号管理员"/><ChatWorkspace v-if="page==='chat'" :key="JSON.stringify(chatContext)" :api="api" :token="auth" :context="chatContext"/><Workbench v-if="page==='workbench'" :api="api" :mode="selfView?'self':can('talent.read')?'hr':'admin'" @requirement="openRequirement" :shortcuts="navGroups.flatMap(g=>g.items).filter(i=>['candidates','talents','requirements','assessments','accounts','roles','catalog','audit','tasks'].includes(i.key))" @navigate="navigate"/><RoleWorkspace v-if="page==='roles'" :api="api" :catalog="catalog"/><AssessmentWorkspace v-if="page==='assessments'" :api="api" :manage="can('assessment.manage')" :assign="can('assessment.assign')"/><KeepAlive><RequirementWorkspace v-if="page==='requirements'" :api="api" :entry="requirementEntry" :catalog="catalog" :can-write="can('requirement.write')" :can-talent-write="can('talent.write')" @open="id => openTalent({id} as Talent)" @task="id => {focusedTaskId=id; navigate('tasks')}"/></KeepAlive><KeepAlive><CandidateWorkspace v-if="page==='candidates'" :api="api" :can-chat="can('chat.use')" @chat="openChat" :can-requirements="can('requirement.read')" :departments="catalog.departments" :can-import="can('file.write') && can('task.run') && can('talent.write')" @open="id => openTalent({id} as Talent)" @task="id => {focusedTaskId=id; navigate('tasks')}"/></KeepAlive><KeepAlive><CandidateWorkspace v-if="page==='talents'" :api="api" :can-import="false" :profile-mode="true" :self-view="selfView" :title="selfView?'我的档案':'人才画像'" :reload-token="profileReload" :can-chat="can('chat.use')" :can-requirements="can('requirement.read')" :departments="catalog.departments" @open="id=>openTalent({id} as Talent)" @chat="openChat" @task="id=>{focusedTaskId=id;navigate('tasks')}"><template #actions><el-button v-if="can('talent.write')&&!selfView" type="primary" @click="newTalent">新建人才</el-button></template></CandidateWorkspace></KeepAlive>
      <template v-if="page==='tasks'">
        <div class="title-row"><div><p class="eyebrow">PROCESSING</p><h1>任务记录</h1><p class="muted">逐文件查看解析进度、失败原因及重试记录。</p></div><el-button @click="run(refreshTasks)">刷新</el-button></div>
        <el-card v-if="focusedTask" data-testid="task-detail">
          <div class="table-head"><strong>任务详情</strong><el-button text @click="focusedTaskId=null; focusedTask=null">关闭详情</el-button></div>
          <p>任务编号：<span data-testid="focused-task-id">{{ focusedTask.id }}</span></p>
          <p>技术执行状态：{{ stateName[focusedTask.state] }} · 执行版本 {{ focusedTask.run_version }}</p>
          <p v-if="focusedTask.result">{{ focusedTask.result }}</p><p v-if="focusedTask.error_code">{{ errorName[focusedTask.error_code] || focusedTask.error_code }}</p>
          <el-button v-if="focusedTask.talent_id" @click="openTalent({id:focusedTask.talent_id} as Talent)">核对当前人才档案</el-button><ExtractionResult :api="api" :task-id="focusedTask.id" :state="focusedTask.state"/><p v-for="attempt in focusedTask.attempts" :key="attempt.run_version" class="muted">执行版本 {{attempt.run_version}} · {{stateName[attempt.state] || attempt.state}}</p>
          <el-button v-if="focusedTask.state==='failed' && focusedTask.run_version<3 && focusedTask.retryable!==false && can('task.run')" @click="retry(focusedTask)">重试此任务</el-button>
        </el-card>
        <p class="muted" data-testid="task-total">共 {{taskTotal}} 条任务</p>
        <el-table :data="tasks" data-testid="task-table"><el-table-column prop="id" label="任务编号"/><el-table-column label="状态"><template #default="s">{{stateName[s.row.state]}}</template></el-table-column><el-table-column prop="run_version" label="执行版本"/><el-table-column prop="result" label="结果"/><el-table-column prop="error_code" label="失败原因"/><el-table-column label="操作"><template #default="s"><el-button @click="openTask(s.row)">查看</el-button><el-button v-if="s.row.state==='failed' && s.row.run_version<3 && s.row.retryable!==false && can('task.run')" @click="retry(s.row)">重试</el-button></template></el-table-column></el-table>
        <el-empty v-if="!tasks.length" description="暂无解析任务，可先导入简历或在来源文件中发起解析"/>
        <el-pagination data-testid="task-pagination" layout="total, prev, pager, next" :current-page="taskPage" :total="taskTotal" :page-size="taskPageSize" @current-change="changeTaskPage"/>
      </template>
      <AccountWorkspace v-if="page==='accounts'" :api="api" :departments="catalog.departments"/>
      <CatalogWorkspace v-if="page==='catalog'" :api="api" :catalog="catalog" @changed="run(async()=>{catalog=await api('/catalog')})"/>
      <LogWorkspace v-if="page==='audit'" :api="api"/>
    </div>
    <ProfileWorkspace v-if="selected" :id="selected.id" :name="selected.name" :kind="selected.kind" :department="departmentName(selected.department_id)" :version="selected.version" :api="api" :token="auth" :can-chat="can('chat.use')" :editing="edit" :back-label="page==='candidates'?'返回筛选结果':page==='requirements'?'返回岗位与匹配':page==='tasks'?'返回解析任务':'返回人才列表'" @back="closeProfile">
      <template #actions><el-button v-if="!edit&&can('talent.write')" @click="edit=true">编辑档案</el-button></template>
      <template #facts><ProfileFacts :talent="selected" @source="profileSource"/><details v-if="selected.field_states?.length" class="field-provenance"><summary>字段来源与版本</summary><p v-for="state in selected.field_states" :key="state.field">{{categoryName[state.field]}} · {{state.confirmed?'人工维护':'简历声明'}} · 来源 v{{state.source_version}}</p></details></template>
      <template #edit><el-form label-position="top"><el-form-item label="姓名"><el-input v-model="selected.name"/></el-form-item><el-form-item label="身份"><el-select v-model="selected.kind" @change="() => {selected!.department_id=null; selected!.department_position_id=null}"><el-option label="外部候选人" value="external"/><el-option label="内部员工" value="internal"/></el-select></el-form-item><div class="two-col"><el-form-item label="电话"><el-input v-model="selected.phone"/></el-form-item><el-form-item label="邮箱"><el-input v-model="selected.email"/></el-form-item></div><template v-if="selected.kind==='internal'"><el-form-item label="部门"><el-select v-model="selected.department_id" @change="selected.department_position_id=null"><el-option v-for="d in catalog.departments" :key="d.id" :label="d.name" :value="d.id"/></el-select></el-form-item><el-form-item label="部门岗位"><el-select v-model="selected.department_position_id" clearable><el-option v-for="p in positionOptions" :key="p.id" :value="p.id" :label="positionName(p.position_id)"/></el-select></el-form-item></template><template v-else><el-form-item label="负责账号编号"><el-input v-model="selected.owner_id"/></el-form-item><el-form-item label="人才库"><el-select v-model="selected.pool_id" clearable><el-option v-for="p in catalog.pools" :key="p.id" :label="p.name" :value="p.id"/></el-select></el-form-item></template><h3>当前有效事实</h3><div v-for="(f,i) in selected.facts" :key="i" class="fact" style="flex-wrap:wrap"><span v-if="!edit" class="muted" style="flex-basis:100%">{{f.confirmed?'人工维护':'简历声明'}} · 来源版本 {{f.source_version}}</span><el-select v-model="f.category"><el-option label="教育" value="education"/><el-option label="经历" value="experience"/><el-option label="项目" value="project"/><el-option label="技能" value="skill"/><el-option label="证书" value="certificate"/></el-select><el-input v-model="f.content" type="textarea"/><el-button v-if="edit" @click="selected.facts?.splice(i,1)">移除</el-button></div><el-button v-if="edit" @click="selected.facts?.push({category:'skill',content:''})">添加事实</el-button></el-form><p v-if="edit" class="muted">保存会将表单中的基础字段（包括空值）和事实标记为人工确认，后续解析会保留它们并提供更新建议。</p><el-button v-if="edit" type="primary" :loading="busy" @click="saveTalent">保存档案</el-button>
</template>
      <template #files><h3>来源文件</h3><p class="muted">PDF / PNG / JPEG / DOCX，单份 ≤10 MiB，PDF ≤50 页。上传后可发起真实解析。</p><div v-if="can('file.write')"><input ref="uploadInput" type="file" accept=".pdf,.png,.jpg,.jpeg,.docx" @change="resetUploadKey()"/><el-button @click="upload" :loading="busy">上传</el-button></div><div v-for="f in files" :key="f.id" class="file-row"><span>{{ f.original_name }} · {{ Math.ceil(f.size/1024) }} KB</span><el-button @click="download(f)">下载</el-button><template v-if="can('task.run')"><el-button :loading="busy" @click="parseFile(f)">解析简历</el-button></template></div><el-empty v-if="!files.length" description="暂无来源文件，可以上传简历或核对人工事实" :image-size="48"/></template>
      <template #assessments><AssessmentWorkspace v-if="can('assessment.read')||can('talent.read')" :api="api" :manage="false" :assign="false" :talent-id="selected.id"/></template>
      <template #history><h2>修改历史</h2><el-timeline><el-timeline-item v-for="h in selected.history" :key="h.version" :timestamp="new Date(h.created_at*1000).toLocaleString()"><strong>档案 v{{h.version}}</strong><p>{{h.changed_fields.map(f=>categoryName[f]||({name:'姓名',phone:'电话',email:'邮箱',facts:'档案事实',kind:'身份',department_id:'部门',pool_id:'人才库'} as Record<string,string>)[f]||f).join('、')}}</p></el-timeline-item></el-timeline><el-empty v-if="!selected.history?.length" description="暂无修改记录"/></template>
    </ProfileWorkspace>
    </section>
    <el-dialog v-model="scopeChat" title="人才范围问答" width="min(1060px,96vw)" class="scope-chat-dialog" destroy-on-close :close-on-click-modal="false"><ChatWorkspace v-if="scopeChat" :key="JSON.stringify(chatContext)" :api="api" :token="auth" :context="chatContext" :filter-labels="chatFilterLabels" embedded/></el-dialog>
    <el-dialog :model-value="!!profileCitation" title="事实来源" width="min(740px,94vw)" @close="profileCitation=null"><template v-if="profileCitation"><p>{{profileCitation.source_type==='manual'?'人工维护事实':'简历声明'}} · 来源 v{{profileCitation.source_version}}</p><p class="pre-line">{{profileCitation.content}}</p><blockquote v-if="profileCitation.quote">{{profileCitation.quote}}</blockquote><p v-if="profileCitation.locator">原文位置：{{profileCitation.locator}}</p><p v-if="profileCitation.source_type==='manual'" class="muted">人工事实以档案版本记录为依据。</p><el-button v-if="profileCitation.source_task_id" @click="focusedTaskId=profileCitation.source_task_id;profileCitation=null;selected=null;navigate('tasks')">打开解析出处</el-button><p v-else-if="profileCitation.source_type==='resume'" class="muted">当前没有可读取的原文定位，可在来源文件中核对已授权文件。</p></template></el-dialog>
  </div>
</template>
