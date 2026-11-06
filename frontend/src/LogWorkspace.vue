<script setup lang="ts">
import {ref,onMounted} from 'vue'
import {ElMessage} from 'element-plus'
import type {Api} from './api'
const props=defineProps<{api:Api}>()
const kind=ref('audit'),action=ref(''),state=ref(''),page=ref(1),total=ref(0),items=ref<Record<string,unknown>[]>([])
let requestSerial=0
async function load(){const request=++requestSerial;try{const data=await props.api<{items:Record<string,unknown>[];total:number}>(`/admin/logs/${kind.value}?offset=${(page.value-1)*20}&limit=20&action=${encodeURIComponent(action.value)}&state=${encodeURIComponent(state.value)}`);if(request!==requestSerial)return;items.value=data.items;total.value=data.total}catch(e){if(request===requestSerial)ElMessage.error((e as Error).message)}}
onMounted(load)
</script>
<template><h1>操作审计与 AI 调用记录</h1><p>仅保留动作、对象编号、时间、状态、耗时与安全错误码，不展示完整简历、聊天正文或密钥。调用成功仅表示接口返回，业务是否完成以任务状态为准。</p><el-radio-group v-model="kind" @change="page=1;load()"><el-radio-button value="audit">操作审计</el-radio-button><el-radio-button value="ai">AI 调用记录</el-radio-button></el-radio-group><el-input v-model="action" placeholder="动作/调用类型包含" style="width:240px"/><el-input v-model="state" placeholder="状态精确筛选，如 failed" style="width:240px"/><el-button @click="page=1;load()">查询</el-button><el-table :data="items"><el-table-column v-if="kind==='audit'" prop="action" label="动作"/><el-table-column v-else prop="operation" label="调用类型"/><el-table-column prop="target_id" label="对象/任务编号"/><el-table-column :prop="kind==='ai'?'state':'outcome'" label="状态"/><template v-if="kind==='ai'"><el-table-column prop="model" label="模型"/><el-table-column prop="elapsed_ms" label="耗时ms"/><el-table-column prop="error_code" label="错误码"/></template><el-table-column v-else prop="request_id" label="追踪编号"/><el-table-column label="时间"><template #default="s">{{new Date(s.row.created_at*1000).toLocaleString()}}</template></el-table-column></el-table><el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="total,prev,pager,next" @current-change="load"/></template>
