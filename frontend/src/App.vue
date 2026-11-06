<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { createApi } from './api'
import { errorName, categoryName } from './labels'
import CandidateWorkspace from './CandidateWorkspace.vue'
import RequirementWorkspace from './RequirementWorkspace.vue'
import ExtractionResult from './ExtractionResult.vue'
interface Grant { action: string; scope: string; scope_id: string | null }
interface Me { id: string; username: string; grants: Grant[] }
interface Fact {category: string; content: string; confirmed?: boolean; source_type?: string; source_version?: number}
interface Talent {id: string; kind: string; name: string; phone: string; email: string; department_id: string | null; department_position_id: string | null; owner_id: string | null; pool_id: string | null; version: number; field_states?: {field:string;confirmed:boolean;source_type:string;source_version:number}[]; facts?: Fact[]; history?: {version: number; actor_id: string; changed_fields: string[]; created_at: number}[]}
interface CatalogItem {id: string; name?: string; department_id?: string; position_id?: string}
interface FileItem {id: string; original_name: string; size: number}
interface Task {id: string; talent_id?: string; retryable?: boolean; state: string; run_version: number; error_code: string | null; result: string | null}
interface TaskDetail extends Task { attempts: {run_version: number; state: string}[] }
interface Account {id: string; username: string; enabled: boolean; version: number; talent_id: string | null; role_ids: string[]}
const auth = ref(''), me = ref<Me | null>(null), page = ref('candidates'), busy = ref(false)
const login = ref({username: '', password: ''}), talents = ref<Talent[]>([]), total = ref(0), offset = ref(0)
const catalog = ref<Record<string, CatalogItem[]>>({departments: [], positions: [], department_positions: [], pools: []})
const selected = ref<Talent | null>(null), edit = ref(false), files = ref<FileItem[]>([]), tasks = ref<Task[]>([])
const taskPage = ref(1), taskTotal = ref(0), taskPageSize = 20
const focusedTaskId = ref<string | null>(null), focusedTask = ref<TaskDetail | null>(null)
let taskListRequest = 0
const accounts = ref<Account[]>([]), roles = ref<{id: string; name: string}[]>([]), audits = ref<Record<string, unknown>[]>([])
const newAccount = ref({username: '', password: '', department_id: null as string | null})
const catalogKind = ref('departments'), catalogName = ref(''), dp = ref({department_id: '', position_id: ''})
const uploadInput = ref<HTMLInputElement | null>(null)
const createKey = ref(crypto.randomUUID()), uploadKey = ref(crypto.randomUUID())
const can = (action: string) => me.value?.grants.some(g => g.action === action) ?? false
const departmentName = (id: string | null) => catalog.value.departments.find(d => d.id === id)?.name || '—'
const positionOptions = computed(() => catalog.value.department_positions.filter(p => p.department_id === selected.value?.department_id))
const positionName = (id?: string) => catalog.value.positions.find(p => p.id === id)?.name || id
const stateName: Record<string,string> = {queued:'待处理', running:'处理中', succeeded:'成功', failed:'失败'}
const api = createApi(() => auth.value, logout)
async function run(fn: () => Promise<void>) { busy.value = true; try { await fn() } catch (e) { ElMessage.error((e as Error).message) } finally { busy.value = false } }
function logout() { auth.value = ''; me.value = null; talents.value = []; selected.value = null; files.value = []; tasks.value = []; taskPage.value = 1; taskTotal.value = 0; focusedTaskId.value = null; focusedTask.value = null; taskListRequest++; accounts.value = []; roles.value = []; audits.value = []; login.value.password = '' }
async function signIn() { await run(async () => { const result = await api<{token: string}>('/auth/login', 'POST', login.value); auth.value = result.token; login.value.password = ''; me.value = await api<Me>('/auth/me'); catalog.value = await api('/catalog'); await loadTalents() }) }
async function loadTalents() { const result = await api<{items: Talent[]; total: number}>(`/talents?offset=${offset.value}&limit=20`); talents.value = result.items; total.value = result.total }
async function openTalent(t: Talent) { await run(async () => { selected.value = await api<Talent>(`/talents/${t.id}`); edit.value = false; files.value = can('file.read') ? await api<FileItem[]>(`/talents/${t.id}/files`) : [] }) }
function newTalent() { selected.value = {id: '', kind: 'external', name: '', phone: '', email: '', department_id: null, department_position_id: null, owner_id: me.value!.id, pool_id: null, version: 1, facts: []}; files.value = []; edit.value = true; createKey.value = crypto.randomUUID() }
async function saveTalent() {
  await run(async () => {
    const t = selected.value!, session = auth.value
    const body = {kind:t.kind,name:t.name,phone:t.phone,email:t.email,department_id:t.department_id,department_position_id:t.department_position_id,owner_id:t.owner_id,pool_id:t.pool_id,facts:(t.facts || []).map(f => ({category:f.category,content:f.content}))}
    const saved = await api<Talent>(t.id ? `/talents/${t.id}` : '/talents', t.id ? 'PUT' : 'POST', t.id ? {...body, version:t.version} : body, t.id ? undefined : createKey.value)
    if (session !== auth.value) return
    // 用户保存期间关闭或切换详情，迟到响应不能重新打开旧档案。
    if (selected.value === t) { selected.value = saved; edit.value = false }
    await loadTalents()
    ElMessage.success('档案已保存')
  })
}
async function upload() { await run(async () => { const file = uploadInput.value?.files?.[0]; if (!file || !selected.value?.id) return; const form = new FormData(); form.append('file', file); await api(`/talents/${selected.value.id}/files`, 'POST', form, uploadKey.value); uploadKey.value = crypto.randomUUID(); files.value = await api(`/talents/${selected.value.id}/files`); ElMessage.success('文件已保存，可点击解析简历') }) }
async function download(file: FileItem) { await run(async () => { const res = await fetch(`/api/files/${file.id}/download`, {headers:{Authorization:`Bearer ${auth.value}`}}); if (!res.ok) throw new Error('文件不可用或授权已变化'); const url = URL.createObjectURL(await res.blob()); const a = document.createElement('a'); a.href = url; a.download = file.original_name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000) }) }
async function rebuildSelectedIndex() { await run(async () => { const t=selected.value!; await api(`/talents/${t.id}/reindex`, 'POST', {version:t.version}); ElMessage.success('已安排当前版本索引更新') }) }
async function parseFile(file: FileItem) { await run(async () => { const task = await api<Task>(`/files/${file.id}/parse`, 'POST', undefined, crypto.randomUUID()); selected.value=null; page.value='tasks'; focusedTaskId.value=task.id; await refreshTasks() }) }
async function task(file: FileItem, mode: string) {
  await run(async () => {
    const created = await api<Task>(`/files/${file.id}/test-tasks`, 'POST', {mode}, crypto.randomUUID())
    selected.value = null
    page.value = 'tasks'
    taskPage.value = 1
    focusedTaskId.value = created.id
    focusedTask.value = null
    // 新任务的 UUID 排序位置不固定，直接按返回编号读取，避免依赖列表当前页。
    await refreshTasks()
  })
}
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
async function navigate(p: string) { page.value = p; await run(async () => { me.value = await api('/auth/me'); if (p === 'talents') await loadTalents(); if (p === 'tasks') await refreshTasks(); if (p === 'accounts') {accounts.value = await api('/admin/users'); roles.value = await api('/admin/roles')} if (p === 'audit') audits.value = await api('/admin/audit') }) }
async function addAccount() { await run(async () => { await api('/admin/users', 'POST', newAccount.value); newAccount.value.password = ''; accounts.value = await api('/admin/users'); ElMessage.success('账号已创建，请设置角色与绑定') }) }
async function saveAccount(a: Account) { await run(async () => { await api(`/admin/users/${a.id}`, 'PATCH', {version:a.version,enabled:a.enabled,role_ids:a.role_ids,talent_id:a.talent_id || null}); accounts.value = await api('/admin/users'); ElMessage.success('账号授权已保存') }) }
async function addCatalog() { await run(async () => { await api(`/catalog/${catalogKind.value}`, 'POST', catalogKind.value === 'department_positions' ? dp.value : {name:catalogName.value}); catalogName.value = ''; catalog.value = await api('/catalog'); ElMessage.success('基础资料已创建') }) }
function copyTalentId() { if (selected.value) void navigator.clipboard.writeText(selected.value.id) }
function resetUploadKey() { uploadKey.value = crypto.randomUUID() }
let timer: ReturnType<typeof setInterval>
onMounted(() => { timer = setInterval(() => { if (auth.value && page.value === 'tasks' && (tasks.value.some(t => ['queued','running'].includes(t.state)) || (focusedTask.value && ['queued','running'].includes(focusedTask.value.state)))) void run(refreshTasks) }, 3000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <main v-if="!me" class="login-page"><section class="intro"><div class="brand">TALENT / 人才</div><h1>让每一份人才资料，<br>成为可用的积累。</h1><p>AI 数字化人才平台 · 岗位与人才匹配</p><div class="stage-note">上传真实简历、核对资料与筛选候选人。<br>仅展示当前授权范围。</div></section><el-card class="login-card"><h2>登录工作台</h2><p class="muted">使用本机管理员或已创建的账号</p><el-form @submit.prevent="signIn" label-position="top"><el-form-item label="账号"><el-input v-model="login.username" autocomplete="username" /></el-form-item><el-form-item label="密码"><el-input v-model="login.password" type="password" show-password autocomplete="current-password" /></el-form-item><el-button native-type="submit" type="primary" :loading="busy">登录</el-button></el-form></el-card></main>
  <div v-else class="workspace">
    <aside><div class="brand">TALENT<span>人才工作台</span></div><nav><button @click="navigate('candidates')">候选人筛选</button><button :class="{active:page==='talents'}" @click="navigate('talents')">人才档案</button><button v-if="can('requirement.read')" @click="navigate('requirements')">岗位需求</button><button @click="navigate('tasks')" :class="{active:page==='tasks'}">任务记录</button><button v-if="can('account.manage')" @click="navigate('accounts')">账号管理</button><button v-if="can('catalog.manage')" @click="navigate('catalog')">基础资料</button><button v-if="can('audit.read')" @click="navigate('audit')">操作审计</button></nav><footer>第三阶段 · 岗位需求<br><small>仅展示当前授权范围</small></footer></aside>
    <section class="content"><header><span>AI 数字化人才平台</span><div>{{ me.username }} <el-button text @click="logout">退出登录</el-button></div></header>
      <RequirementWorkspace v-if="page==='requirements'" :api="api" :catalog="catalog" :can-write="can('requirement.write')" :can-talent-write="can('talent.write')" @open="id => openTalent({id} as Talent)" @task="id => {focusedTaskId=id; navigate('tasks')}"/><CandidateWorkspace v-if="page==='candidates'" :api="api" :can-requirements="can('requirement.read')" :departments="catalog.departments" :can-import="can('file.write') && can('task.run') && can('talent.write')" @open="id => openTalent({id} as Talent)" @task="id => {focusedTaskId=id; navigate('tasks')}"/><template v-if="page==='talents'"><div class="title-row"><div><p class="eyebrow">PEOPLE & PROFILES</p><h1>人才档案</h1><p class="muted">维护真实资料，保留来源与修改记录。</p></div><el-button v-if="can('talent.write')" type="primary" @click="newTalent">新建人才</el-button></div><el-card><div class="table-head"><strong>授权范围内的人才</strong><span class="muted">共 {{ total }} 人</span></div><el-table :data="talents" @row-click="openTalent"><el-table-column prop="name" label="姓名"/><el-table-column label="身份"><template #default="s"><el-tag :type="s.row.kind==='external'?'success':'primary'">{{s.row.kind==='external'?'外部候选人':'内部员工'}}</el-tag></template></el-table-column><el-table-column label="部门"><template #default="s">{{departmentName(s.row.department_id)}}</template></el-table-column><el-table-column prop="email" label="邮箱"/><el-table-column prop="version" label="档案版本"/></el-table><el-empty v-if="!talents.length" description="暂无可查看的人才，可新建档案或联系管理员授权"/><el-pagination layout="prev, pager, next" :total="total" :page-size="20" @current-change="(n: number) => {offset=(n-1)*20; run(loadTalents)}"/></el-card></template>
      <template v-if="page==='tasks'">
        <div class="title-row"><div><p class="eyebrow">PROCESSING</p><h1>任务记录</h1><p class="muted">逐文件查看实际解析或机制测试任务、失败原因及重试记录。</p></div><el-button @click="run(refreshTasks)">刷新</el-button></div>
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
        <el-empty v-if="!tasks.length" description="暂无任务，请在人才档案文件区发起机制测试"/>
        <el-pagination data-testid="task-pagination" layout="total, prev, pager, next" :current-page="taskPage" :total="taskTotal" :page-size="taskPageSize" @current-change="changeTaskPage"/>
      </template>
      <template v-if="page==='accounts'"><h1>账号管理</h1><p class="muted">系统管理身份不自动获得人才正文访问权。角色范围可通过受控接口配置，详见开发说明。</p><el-form inline><el-form-item label="新账号"><el-input v-model="newAccount.username"/></el-form-item><el-form-item label="初始密码"><el-input v-model="newAccount.password" type="password" placeholder="至少 12 字符"/></el-form-item><el-button @click="addAccount">创建</el-button></el-form><el-table :data="accounts"><el-table-column prop="username" label="账号"/><el-table-column label="启用"><template #default="s"><el-switch v-model="s.row.enabled"/></template></el-table-column><el-table-column label="角色"><template #default="s"><el-select v-model="s.row.role_ids" multiple><el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id"/></el-select></template></el-table-column><el-table-column label="人才绑定"><template #default="s"><el-input v-model="s.row.talent_id" placeholder="人才编号，可留空"/></template></el-table-column><el-table-column label="操作"><template #default="s"><el-button @click="saveAccount(s.row)">保存</el-button></template></el-table-column></el-table></template>
      <template v-if="page==='catalog'"><h1>基础资料</h1><p class="muted">同一个公司岗位可分别设置在不同部门。</p><el-form inline><el-select v-model="catalogKind" style="width:180px"><el-option label="部门" value="departments"/><el-option label="公司岗位" value="positions"/><el-option label="部门岗位" value="department_positions"/><el-option label="人才库" value="pools"/></el-select><template v-if="catalogKind==='department_positions'"><el-select v-model="dp.department_id" placeholder="部门" style="width:180px"><el-option v-for="d in catalog.departments" :key="d.id" :label="d.name" :value="d.id"/></el-select><el-select v-model="dp.position_id" placeholder="公司岗位" style="width:180px"><el-option v-for="p in catalog.positions" :key="p.id" :label="p.name" :value="p.id"/></el-select></template><el-input v-else v-model="catalogName" style="width:220px" placeholder="名称"/><el-button @click="addCatalog">新增</el-button></el-form><el-table :data="catalog[catalogKind]"><el-table-column prop="id" label="编号"/><el-table-column v-if="catalogKind!=='department_positions'" prop="name" label="名称"/><template v-else><el-table-column label="部门"><template #default="s">{{departmentName(s.row.department_id)}}</template></el-table-column><el-table-column label="岗位"><template #default="s">{{positionName(s.row.position_id)}}</template></el-table-column></template></el-table></template>
      <template v-if="page==='audit'"><h1>操作审计</h1><p class="muted">仅保存动作、目标编号与结果，不记录敏感正文。</p><el-table :data="audits"><el-table-column prop="action" label="动作"/><el-table-column prop="target_id" label="目标"/><el-table-column prop="outcome" label="结果"/><el-table-column prop="request_id" label="追踪编号"/></el-table></template>
    </section>
    <el-drawer :model-value="!!selected" @close="selected=null" size="min(780px, 95vw)" :title="selected?.id?'人才详情':'新建人才'">
      <template v-if="selected"><div class="detail-tools"><el-tag>档案版本 {{ selected.version }}</el-tag><el-button v-if="!edit && can('talent.write')" @click="edit=true">编辑</el-button><el-button v-if="!edit && selected.id" @click="copyTalentId()">复制人才编号</el-button><el-button v-if="!edit && selected.id && can('talent.write') && can('file.read')" @click="rebuildSelectedIndex">重建检索索引</el-button></div><p v-if="selected.field_states?.length" class="muted">字段来源：<span v-for="state in selected.field_states" :key="state.field">{{categoryName[state.field]}} {{state.confirmed?'人工已确认':'文件抽取待确认'}}（版本{{state.source_version}}）；</span></p><el-form label-position="top" :disabled="!edit"><el-form-item label="姓名"><el-input v-model="selected.name"/></el-form-item><el-form-item label="身份"><el-select v-model="selected.kind" @change="() => {selected!.department_id=null; selected!.department_position_id=null}"><el-option label="外部候选人" value="external"/><el-option label="内部员工" value="internal"/></el-select></el-form-item><div class="two-col"><el-form-item label="电话"><el-input v-model="selected.phone"/></el-form-item><el-form-item label="邮箱"><el-input v-model="selected.email"/></el-form-item></div><template v-if="selected.kind==='internal'"><el-form-item label="部门"><el-select v-model="selected.department_id" @change="selected.department_position_id=null"><el-option v-for="d in catalog.departments" :key="d.id" :label="d.name" :value="d.id"/></el-select></el-form-item><el-form-item label="部门岗位"><el-select v-model="selected.department_position_id" clearable><el-option v-for="p in positionOptions" :key="p.id" :value="p.id" :label="positionName(p.position_id)"/></el-select></el-form-item></template><template v-else><el-form-item label="负责账号编号"><el-input v-model="selected.owner_id"/></el-form-item><el-form-item label="人才库"><el-select v-model="selected.pool_id" clearable><el-option v-for="p in catalog.pools" :key="p.id" :label="p.name" :value="p.id"/></el-select></el-form-item></template><h3>当前有效事实</h3><div v-for="(f,i) in selected.facts" :key="i" class="fact" style="flex-wrap:wrap"><span v-if="!edit" class="muted" style="flex-basis:100%">{{f.confirmed?'人工已确认':'文件抽取，未人工确认'}} · 来源版本 {{f.source_version}}</span><el-select v-model="f.category"><el-option label="教育" value="education"/><el-option label="经历" value="experience"/><el-option label="项目" value="project"/><el-option label="技能" value="skill"/><el-option label="证书" value="certificate"/></el-select><el-input v-model="f.content" type="textarea"/><el-button v-if="edit" @click="selected.facts?.splice(i,1)">移除</el-button></div><el-button v-if="edit" @click="selected.facts?.push({category:'skill',content:''})">添加事实</el-button></el-form><p v-if="edit" class="muted">保存会将表单中的基础字段（包括空值）和事实标记为人工确认，后续解析会保留它们并提供更新建议。</p><el-button v-if="edit" type="primary" :loading="busy" @click="saveTalent">保存档案</el-button>
      <template v-if="selected.id && !edit"><h3>来源文件</h3><p class="muted">PDF / PNG / JPEG / DOCX，单份 ≤10 MiB，PDF ≤50 页。上传后可发起真实解析。</p><div v-if="can('file.write')"><input ref="uploadInput" type="file" accept=".pdf,.png,.jpg,.jpeg,.docx" @change="resetUploadKey()"/><el-button @click="upload" :loading="busy">上传</el-button></div><div v-for="f in files" :key="f.id" class="file-row"><span>{{ f.original_name }} · {{ Math.ceil(f.size/1024) }} KB</span><el-button @click="download(f)">下载</el-button><template v-if="can('task.run')"><el-button @click="parseFile(f)">解析简历</el-button><el-button @click="task(f,'success')">测试成功</el-button><el-button @click="task(f,'fail')">测试失败</el-button></template></div><h3>修改历史</h3><p v-for="h in selected.history" :key="h.version" class="muted">版本 {{h.version}} · {{new Date(h.created_at*1000).toLocaleString()}} · {{h.changed_fields.join('、')}}</p></template></template>
    </el-drawer>
  </div>
</template>
