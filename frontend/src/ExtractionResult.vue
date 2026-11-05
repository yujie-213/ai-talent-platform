<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Api } from './api'
const props = defineProps<{api: Api; taskId: string; state: string}>()
interface Record {quality: string; base_version: number; segments: {id: string; locator: string; method: string; text: string}[] | null; validated: {fields: {category:string; value:string; locator:string; quote:string}[]; missing:string[]; issues:unknown[]; duplicate_ids?:string[]} | null}
const result = ref<Record | null>(null)
watch(() => [props.taskId, props.state], async () => {
  result.value = null
  try { result.value = await props.api<Record>(`/tasks/${props.taskId}/extraction`) } catch { /* 机制测试没有解析记录 */ }
}, {immediate: true})
</script>
<template><section v-if="result"><h3>解析资料与证据</h3><p>资料状态：{{result.quality}} · 启动档案版本 {{result.base_version}}</p><template v-if="result.validated"><p>缺失：{{result.validated.missing.join('、') || '无'}}；异常字段 {{result.validated.issues.length}} 项</p><p v-if="result.validated.duplicate_ids?.length">疑似重复人才：{{result.validated.duplicate_ids.join('、')}}。请对比档案，不会自动合并。</p><el-table :data="result.validated.fields"><el-table-column prop="category" label="类别"/><el-table-column prop="value" label="抽取值"/><el-table-column prop="locator" label="定位"/><el-table-column prop="quote" label="原文依据"/></el-table></template><details><summary>查看逐页/段落原文</summary><article v-for="segment in result.segments" :key="segment.id"><strong>{{segment.locator}} · {{segment.method}}</strong><pre style="white-space:pre-wrap">{{segment.text}}</pre></article></details></section></template>
