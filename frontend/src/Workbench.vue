<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
const props=defineProps<{api:Api;shortcuts?:{key:string;name:string;icon:string}[]}>()
const emit=defineEmits<{navigate:[key:string]}>()
const loading=ref(false),error=ref('')
const data=ref<Record<string,Record<string,number|string>>|null>(null)
const groups:Record<string,string>={people:'已入档人才',parse_tasks:'解析及机制任务',match_entries:'本人发起的匹配明细',assessments:'测评任务',chat_jobs:'本人聊天与语义任务'}
const labels:Record<string,string>={internal:'内部员工',external:'外部候选人',queued:'待处理',running:'处理中',pending:'待参与 / 待处理',answering:'作答中',submitted:'已提交待评分',completed:'已完成',succeeded:'成功',failed:'失败',evaluated:'已评估'}
async function load(){loading.value=true;error.value='';try{data.value=await props.api('/workbench')}catch(e){error.value=(e as Error).message;ElMessage.error(error.value)}finally{loading.value=false}}
onMounted(load)
</script>
<template><div class="title-row"><div><p class="eyebrow">OVERVIEW / 今日工作</p><h1>工作台</h1><p class="muted">人才、招聘与成长，一处掌握当前进展。</p></div><el-button :loading="loading" @click="load">刷新统计</el-button></div>
<div v-if="shortcuts?.length" class="quick-actions"><a v-for="item in shortcuts" :key="item.key" :href="'#'+item.key" @click.prevent="emit('navigate',item.key)"><span>{{item.name}}</span><span aria-hidden="true">↗</span></a></div>
<el-alert v-if="error" :title="error" type="error" :closable="false"/>
<div v-loading="loading" v-if="data" class="workbench-grid"><el-card v-for="(name,key,index) in groups" :key="key"><div class="metric-heading"><span class="metric-index">0{{index+1}}</span><h2>{{name}}</h2></div><div class="metrics"><div v-for="(value,state) in data[key]" :key="state"><span class="muted">{{labels[state]||state}}</span><strong>{{value}}</strong></div></div><el-empty v-if="!Object.keys(data[key]||{}).length" description="当前范围暂无记录" :image-size="48"/><p class="metric-definition">{{data.definitions[key]}}</p></el-card></div><p class="muted">实时统计当前授权范围。历史任务不会被当作当前业务人数。</p></template>
<style scoped>.quick-actions{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}.quick-actions a{display:flex;gap:32px;justify-content:space-between;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 20px;color:var(--accent);font:inherit;cursor:pointer;text-decoration:none}.quick-actions a:hover{background:var(--accent-soft);border-color:var(--accent)}.workbench-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.workbench-grid>.el-card{margin:0}.metric-heading{display:flex;align-items:center;gap:12px;margin-bottom:24px}.metric-heading h2{font-size:16px;margin:0}.metric-index{color:var(--accent);font-size:12px;background:var(--accent-soft);padding:8px;border-radius:8px}.metrics{display:flex;flex-wrap:wrap;gap:20px}.metrics>div{display:flex;flex-direction:column;gap:10px;min-width:76px}.metrics strong{font-size:30px;font-weight:650;font-variant-numeric:tabular-nums}.metric-definition{color:var(--text-secondary);font-size:12px;border-top:1px solid var(--border);padding-top:16px;margin-bottom:0}@media(max-width:900px){.workbench-grid{grid-template-columns:1fr}}
</style>