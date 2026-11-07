<script setup lang="ts">
import {ref,computed,onMounted} from 'vue'
import type {Api} from './api'
interface RequirementSummary {id:string;title:string;department:string;status:string;active_version:number|null}
interface MatchSummary {id:string;requirement_id:string;title:string;requirement_version:number;created_at:number;state:string;total:number;stale:boolean;counts:Record<string,number>}
interface Summary {people:Record<string,number>;parse_tasks:Record<string,number>;assessments:Record<string,number>;requirements:Record<string,number>;recent_requirements:RequirementSummary[];recent_matches:MatchSummary[]}
const props=defineProps<{api:Api;shortcuts?:{key:string;name:string;icon:string}[];mode?:'hr'|'self'|'admin'}>()
const emit=defineEmits<{navigate:[key:string];requirement:[entry:{id:string;runId?:string} ]}>()
const loading=ref(false),error=ref(''),data=ref<Summary|null>(null)
const available=(key:string)=>props.shortcuts?.some(s=>s.key===key)
const count=(group:keyof Summary,state:string)=>Number((data.value?.[group] as Record<string,number>|undefined)?.[state]||0)
const cards=computed(()=>props.mode==='self'?[
 {label:'本人档案',value:count('people','internal')+count('people','external'),note:'当前绑定与授权内',key:'talents'},
 {label:'待参与测评',value:count('assessments','pending')+count('assessments','answering'),note:'含作答中任务',key:'assessments'},
 {label:'已完成测评',value:count('assessments','completed'),note:'查看成绩与历史',key:'assessments'}
]:[
 {label:'授权人才',value:count('people','internal')+count('people','external'),note:`外部 ${count('people','external')} / 内部 ${count('people','internal')}`,key:'talents'},
 {label:'有效岗位',value:count('requirements','active'),note:`草稿 ${count('requirements','draft')} / 停用 ${count('requirements','disabled')}`,key:'requirements'},
 {label:'处理中解析',value:count('parse_tasks','queued')+count('parse_tasks','running'),note:'排队及执行中的文件任务',key:'tasks'},
 {label:'待参与测评',value:count('assessments','pending')+count('assessments','answering'),note:'当前测评与人才权限内',key:'assessments'}
].filter(c=>available(c.key)))
const names:Record<string,string>={draft:'草稿',active:'有效',disabled:'已停用',queued:'待处理',running:'处理中',succeeded:'已完成',failed:'失败'}
const notes:Record<string,string>={candidates:'筛选、比较与导入',talents:'履历、来源与问答',requirements:'岗位、匹配与历史',assessments:'任务、答题与成绩',accounts:'账号与人才绑定',roles:'功能、范围与菜单',catalog:'组织与岗位资料',audit:'操作与模型调用记录'}
async function load(){loading.value=true;error.value='';try{data.value=await props.api('/workbench')}catch(e){error.value=(e as Error).message}finally{loading.value=false}}
onMounted(load)
</script>
<template>
  <div class="title-row"><h1>{{mode==='self'?'我的工作台':mode==='admin'?'管理工作台':'工作台'}}</h1><el-button :loading="loading" @click="load">刷新</el-button></div>
  <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button @click="load">重试</el-button></el-alert>
  <div v-if="mode!=='admin'" v-loading="loading" class="overview-stats"><button v-for="c in cards" :key="c.label" @click="emit('navigate',c.key)"><span>{{c.label}}</span><strong>{{data?c.value:'—'}}</strong><small>{{c.note}}</small></button></div>
  <p v-else class="muted">管理账号、角色和组织资料；此视角仅显示已获授权的管理入口。</p>
  <div class="overview-body"><el-card v-if="mode!=='admin'"><template #header><h2>{{mode==='self'?'我的待办':'待处理事项'}}</h2></template>
    <div v-if="available('tasks')" class="todo-row"><div><strong>解析与资料核对</strong><p>待处理 {{count('parse_tasks','queued')}} · 处理中 {{count('parse_tasks','running')}} · 失败 {{count('parse_tasks','failed')}}</p></div><el-button @click="emit('navigate','tasks')">查看文件任务</el-button></div>
    <div v-if="available('assessments')" class="todo-row"><div><strong>测评任务</strong><p>待参与 {{count('assessments','pending')}} · 作答中 {{count('assessments','answering')}} · 待评分 {{count('assessments','submitted')}}</p></div><el-button @click="emit('navigate','assessments')">进入测评</el-button></div>
    <div v-if="available('requirements')" class="todo-row"><div><strong>完善岗位需求</strong><p>草稿 {{count('requirements','draft')}} 个 · 确认生效后可匹配</p></div><el-button @click="emit('navigate','requirements')">查看岗位</el-button></div>
  </el-card><el-card :class="{'admin-shortcuts':mode==='admin'}"><template #header><h2>业务入口</h2></template><div class="overview-flow"><button v-for="item in shortcuts" :key="item.key" @click="emit('navigate',item.key)"><strong>{{item.name}}</strong><span>{{notes[item.key]||'进入工作区'}} →</span></button></div><el-empty v-if="!shortcuts?.length" description="暂无可用入口，请联系管理员配置菜单与权限" :image-size="48"/></el-card></div>
  <div v-if="available('requirements')" class="overview-body"><el-card><template #header><h2>当前招聘需求</h2></template><div v-for="r in data?.recent_requirements||[]" :key="r.id" class="todo-row"><div><strong>{{r.title||'未命名草稿'}}</strong><p>{{r.department}} · {{names[r.status]}} · {{r.active_version?'有效版本 v'+r.active_version:'尚未生效'}}</p></div><el-button @click="emit('requirement',{id:r.id})">进入岗位</el-button></div><el-empty v-if="!data?.recent_requirements?.length" description="当前权限内暂无岗位需求" :image-size="48"/></el-card>
  <el-card><template #header><h2>最近匹配结果</h2></template><div v-for="m in data?.recent_matches||[]" :key="m.id" class="todo-row"><div><strong>{{m.title||'岗位匹配'}}</strong><p>{{new Date(m.created_at*1000).toLocaleString()}} · 岗位 v{{m.requirement_version}} · {{names[m.state]}} · 可见 {{m.total}} 人</p><el-tag v-if="m.stale" type="warning" size="small">历史参考</el-tag></div><el-button @click="emit('requirement',{id:m.requirement_id,runId:m.id})">查看结果</el-button></div><el-empty v-if="!data?.recent_matches?.length" description="暂无本人发起且当前有权查看的匹配结果" :image-size="48"/></el-card></div>
</template>
<style scoped>
.overview-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:16px}.overview-stats button{border:1px solid var(--border);background:var(--surface);border-radius:var(--radius);padding:16px 18px;text-align:left;cursor:pointer;color:var(--text)}.overview-stats button:hover{border-color:var(--accent)}.overview-stats span,.overview-stats small{display:block;color:var(--text-secondary);font-size:12px}.overview-stats strong{display:block;font-size:28px;margin:7px 0;font-variant-numeric:tabular-nums}.overview-body{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}.overview-body>.el-card{margin:0}.overview-body h2{font-size:16px;margin:0}.todo-row{display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid var(--border);padding:12px 0}.todo-row:first-child{padding-top:0}.todo-row:last-child{border:0;padding-bottom:0}.todo-row strong{font-size:14px;font-weight:550}.todo-row p{font-size:12px;color:var(--text-secondary);margin:4px 0}.overview-flow{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.overview-flow button{padding:14px;text-align:left;cursor:pointer;color:var(--text);background:var(--surface);border:1px solid var(--border);border-radius:8px}.overview-flow button:hover{border-color:var(--accent);background:var(--accent-soft)}.overview-flow strong,.overview-flow span{display:block}.overview-flow span{font-size:12px;color:var(--text-secondary);margin-top:5px}.admin-shortcuts{grid-column:1/-1}.admin-shortcuts .overview-flow{grid-template-columns:repeat(4,minmax(0,1fr))}@media(max-width:1050px){.overview-body{grid-template-columns:1fr}.admin-shortcuts .overview-flow{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.overview-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.overview-flow{grid-template-columns:1fr}}
</style>
