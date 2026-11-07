<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
import { categoryName, qualityName, errorName } from './labels'
import FactGrid from './FactGrid.vue'
const props = defineProps<{api: Api; taskId: string; state: string}>()
interface Record {run_version: number | null; quality: string; base_version: number; segments: {id: string; locator: string; method: string; text: string}[] | null; validated: {fields: {category:string; value:string; locator:string; quote:string}[]; missing:string[]; issues:{code:string;field?:{category:string;value:string;quote:string};category?:string}[]; duplicate_ids?:string[]; suggestions?:{category:string;value:string;quote:string}[]} | null}
const result = ref<Record | null>(null)
const targetId = ref(''), target = ref<{id:string;name:string;phone:string;email:string;version:number;facts:{category:string;content:string}[]} | null>(null)
async function compare() {
  try { target.value = await props.api(`/talents/${targetId.value}`) } catch(error) {ElMessage.error((error as Error).message)}
}
async function resolve(action: 'link'|'exclude') {
  try {
    result.value = await props.api(`/tasks/${props.taskId}/resolve`, 'POST', {action, target_id: action==='link'?target.value?.id:null, version:target.value?.version || 1})
    ElMessage.success('核对结果已保存')
  } catch(error) {ElMessage.error((error as Error).message)}
}
watch(() => [props.taskId, props.state], async () => {
  result.value = null
  try { result.value = await props.api<Record>(`/tasks/${props.taskId}/extraction`) } catch { /* 机制测试没有解析记录 */ }
}, {immediate: true})
</script>
<template><section v-if="result"><h3>解析资料与证据</h3><FactGrid :items="[{key:'quality',label:'资料状态'},{key:'run',label:'对应执行版本'},{key:'base',label:'启动档案版本'}]"><template #quality>{{qualityName[result.quality] || result.quality}}</template><template #run>{{result.run_version ? '第 '+result.run_version+' 次执行' : '尚未产生'}}</template><template #base>档案 v{{result.base_version}}</template></FactGrid><template v-if="result.validated"><p class="muted">缺失：{{result.validated.missing.map(x => categoryName[x] || x).join('、') || '无'}}；异常字段 {{result.validated.issues.length}} 项</p><p v-if="result.validated.duplicate_ids?.length">疑似重复人才：{{result.validated.duplicate_ids.join('、')}}。请对比档案，不会自动合并。</p><div v-if="result.quality==='possible_duplicate'"><el-select v-model="targetId" placeholder="选择授权内疑似重复档案"><el-option v-for="id in result.validated.duplicate_ids" :key="id" :value="id" :label="id"/></el-select><el-button @click="compare">对比档案</el-button><div v-if="target"><p>{{target.name}} · {{target.phone}} · {{target.email}} · 版本{{target.version}}</p><p v-for="(fact,i) in target.facts" :key="i">{{fact.category}}：{{fact.content}}</p><el-button @click="resolve('link')">确认同一人，关联此档案</el-button></div><el-button @click="resolve('exclude')">排除重复，按新人入档</el-button></div><p v-for="(issue,i) in result.validated.issues" :key="i">{{errorName[issue.code] || issue.code}}：{{issue.field?.value || issue.category}}</p><el-table :data="result.validated.fields" class="evidence-table"><el-table-column type="expand" width="40"><template #default="s"><div class="quote-expand"><span class="quote-expand-label">原文依据</span><blockquote class="quote-expand-text">{{s.row.quote}}</blockquote></div></template></el-table-column><el-table-column label="类别" width="90"><template #default="s">{{categoryName[s.row.category] || s.row.category}}</template></el-table-column><el-table-column prop="value" label="抽取值" min-width="220"/><el-table-column prop="locator" label="定位" width="80"/><el-table-column label="原文依据" min-width="200"><template #default="s"><span class="quote-preview" :title="s.row.quote">{{s.row.quote}}</span></template></el-table-column></el-table></template><section v-if="result.validated?.suggestions?.length"><h4>更新建议（未自动写入）</h4><p v-for="(suggestion,i) in result.validated.suggestions" :key="i">{{categoryName[suggestion.category]}}：{{suggestion.value}}；依据：{{suggestion.quote}}</p><p class="muted">请打开当前人才档案，核对后人工编辑确认。</p></section><details><summary>查看逐页/段落原文</summary><article v-for="segment in result.segments" :key="segment.id"><strong>{{segment.locator}} · {{segment.method}}</strong><pre style="white-space:pre-wrap">{{segment.text}}</pre></article></details></section></template>

<style scoped>
h3 { margin: 18px 0 12px; font-size: 14px; }
.muted { font-size: 12px; color: var(--text-tertiary); margin: 12px 0; }
.evidence-table { margin-top: 10px; }
.quote-preview { display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; font-size: 12px; color: var(--text-secondary); }
.quote-expand { padding: 10px 16px; background: var(--surface-muted); border-radius: 8px; margin: 2px 8px 2px 0; }
.quote-expand-label { display: block; font-size: 11px; color: var(--text-tertiary); margin-bottom: 5px; }
.quote-expand-text { margin: 0; font-size: 12px; line-height: 1.8; color: var(--text); white-space: pre-wrap; overflow-wrap: anywhere; border-left: 3px solid var(--accent-soft); padding-left: 10px; }
details { margin-top: 14px; }
details > summary { cursor: pointer; font-size: 12px; color: var(--text-tertiary); width: fit-content; }
details > summary:hover { color: var(--accent); }
details article { margin: 12px 0; }
details strong { display: block; font-size: 12px; margin-bottom: 4px; }
details pre { background: var(--surface-muted); border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-size: 12px; line-height: 1.8; overflow-wrap: anywhere; }
</style>
