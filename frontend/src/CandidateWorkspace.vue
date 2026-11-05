<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
const props = defineProps<{api: Api; canImport: boolean}>()
const emit = defineEmits<{open: [id: string]; task: [id: string]}>()
interface Candidate {id: string; name: string; kind: string; index_state: string; tags: {category: string; content: string; confirmed: boolean}[]}
const filters = ref({kind: 'external', skill: '', education: '', experience: ''})
const items = ref<Candidate[]>([]), total = ref(0), page = ref(1), busy = ref(false)
const input = ref<HTMLInputElement | null>(null)
const uploads = ref<{name: string; state: string; id?: string}[]>([])
async function load() {
  try {
    const params = new URLSearchParams({...filters.value, offset: String((page.value - 1) * 20), limit: '20'})
    const data = await props.api<{items: Candidate[]; total: number}>(`/candidates?${params}`)
    items.value = data.items; total.value = data.total
  } catch (error) { ElMessage.error((error as Error).message) }
}
async function upload() {
  const files = Array.from(input.value?.files || [])
  if (!files.length || files.length > 20) { ElMessage.error('请选择1至20份简历'); return }
  busy.value = true
  const batch = crypto.randomUUID()
  uploads.value = files.map(file => ({name: file.name, state: '等待上传'}))
  for (const [i, file] of files.entries()) {
    try {
      const form = new FormData(); form.append('file', file)
      const task = await props.api<{id: string}>(`/imports/${batch}`, 'POST', form, crypto.randomUUID())
      uploads.value[i] = {name: file.name, state: '已接受，查看解析进度', id: task.id}
    } catch (error) { uploads.value[i]!.state = (error as Error).message }
  }
  busy.value = false; await load()
}
onMounted(load)
</script>
<template>
  <h1>候选人筛选</h1><p class="muted">默认外部候选人；筛选与人数均来自当前授权范围。技能表示简历声明，不代表测评通过。</p>
  <el-card><el-form inline><el-select v-model="filters.kind" style="width:150px"><el-option label="外部候选人" value="external"/><el-option label="内部员工" value="internal"/><el-option label="全部授权人才" value=""/></el-select><el-input v-model="filters.skill" placeholder="技能包含" style="width:150px"/><el-input v-model="filters.education" placeholder="教育原文包含，如本科" style="width:190px"/><el-input v-model="filters.experience" placeholder="经历原文包含" style="width:160px"/><el-button @click="page=1; load()">筛选</el-button></el-form>
  <p>共 {{ total }} 人</p><el-table :data="items" @row-click="(row: Candidate) => emit('open', row.id)"><el-table-column prop="name" label="姓名"/><el-table-column label="分类事实"><template #default="s"><el-tag v-for="tag in s.row.tags" :key="tag.id" style="margin:3px">{{tag.category}} · {{tag.content}} {{tag.confirmed?'已确认':'未确认'}}</el-tag></template></el-table-column><el-table-column prop="index_state" label="检索索引状态"/><el-table-column label="岗位匹配"><template #default>未匹配</template></el-table-column></el-table>
  <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="prev,pager,next" @current-change="load"/></el-card>
  <el-card v-if="canImport" style="margin-top:20px"><h2>导入简历</h2><p>PDF / PNG / JPEG / DOCX；单份10 MiB，PDF最多50页，每批最多20份。图片最多2500万像素，DOCX解压最多50 MiB/1000条目。</p><p class="muted">导入先建立“待解析”档案；身份疑似重复时保留核对，不自动合并。</p><input ref="input" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.docx"/><el-button :loading="busy" @click="upload">上传并解析</el-button><p v-for="(item,i) in uploads" :key="i">{{item.name}}：{{item.state}} <el-button v-if="item.id" @click="emit('task',item.id)">进度与结果</el-button></p></el-card>
</template>
