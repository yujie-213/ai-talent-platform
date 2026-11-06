<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
const props=defineProps<{api:Api}>()
const data=ref<Record<string,Record<string,number|string>>|null>(null)
const groups:Record<string,string>={people:'已入档人才',parse_tasks:'解析及机制任务',match_entries:'本人发起的匹配明细',assessments:'测评任务',chat_jobs:'本人聊天与语义任务'}
const labels:Record<string,string>={internal:'内部员工',external:'外部候选人',queued:'待处理',running:'处理中',pending:'待参与 / 待处理',answering:'作答中',submitted:'已提交待评分',completed:'已完成',succeeded:'成功',failed:'失败',evaluated:'已评估'}
async function load(){try{data.value=await props.api('/workbench')}catch(e){ElMessage.error((e as Error).message)}}
onMounted(load)
</script>
<template><h1>工作台</h1><p class="muted">实时统计当前授权范围。历史任务不会被当作当前业务人数。</p><el-button @click="load">刷新统计</el-button><div v-if="data" class="two-col"><el-card v-for="(name,key) in groups" :key="key"><h2>{{name}}</h2><p v-for="(value,state) in data[key]" :key="state">{{labels[state]||state}}：{{value}}</p><el-empty v-if="!Object.keys(data[key]||{}).length" description="当前范围暂无记录"/><p class="muted">口径：{{data.definitions[key]}}</p></el-card></div></template>
