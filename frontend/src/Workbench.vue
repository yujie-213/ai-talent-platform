<script setup lang="ts">
import {ref,computed,onMounted} from 'vue'
import type {Api} from './api'
import AppIcon from './AppIcon.vue'
import MiniDonut from './MiniDonut.vue'
interface RequirementSummary {id:string;title:string;department:string;status:string;active_version:number|null}
interface MatchSummary {id:string;requirement_id:string;title:string;requirement_version:number;created_at:number;state:string;total:number;stale:boolean;counts:Record<string,number>}
interface Summary {people:Record<string,number>;parse_tasks:Record<string,number>;assessments:Record<string,number>;requirements:Record<string,number>;recent_requirements:RequirementSummary[];recent_matches:MatchSummary[]}
const props=defineProps<{api:Api;shortcuts?:{key:string;name:string;icon:string}[];mode?:'hr'|'self'|'admin'}>()
const emit=defineEmits<{navigate:[key:string];requirement:[entry:{id:string;runId?:string} ]}>()
const loading=ref(false),error=ref(''),data=ref<Summary|null>(null)
const available=(key:string)=>props.shortcuts?.some(s=>s.key===key)
const count=(group:keyof Summary,state:string)=>Number((data.value?.[group] as Record<string,number>|undefined)?.[state]||0)
// 指标卡的图形都来自真实计数：没有可对比的分母时返回 null，前端不画进度条，避免编造比例。
const pct=(part:number,whole:number)=>whole>0?Math.round(part/whole*100):null
interface Segment {label:string;value:number;color:string}
interface Card {label:string;value:number;note:string;key:string;tone:string;icon:string;ratio:number|null;segments?:Segment[];legend?:Segment[]}
const cards=computed<Card[]>(()=>{
  const external=count('people','external'),internal=count('people','internal'),people=external+internal
  const active=count('requirements','active'),draft=count('requirements','draft'),disabled=count('requirements','disabled')
  const queued=count('parse_tasks','queued'),running=count('parse_tasks','running'),failed=count('parse_tasks','failed'),parsed=count('parse_tasks','succeeded')
  const pending=count('assessments','pending'),answering=count('assessments','answering'),submitted=count('assessments','submitted'),completed=count('assessments','completed')
  // 内外部分布是「构成」而不是「进度」，用环形图呈现；其他卡片仍用占比条。
  const peopleSegments:Segment[]=[{label:'外部',value:external,color:'#2f5bea'},{label:'内部',value:internal,color:'#0f766e'}]
  if(props.mode==='self')return [
    {label:'本人档案',value:people,note:'当前绑定与授权内',key:'talents',tone:'blue',icon:'people',ratio:null},
    {label:'待参与测评',value:pending+answering,note:`待参与 ${pending} · 作答中 ${answering}`,key:'assessments',tone:'violet',icon:'check',ratio:pct(pending+answering,pending+answering+submitted+completed)},
    {label:'已完成测评',value:completed,note:'查看成绩与历史记录',key:'assessments',tone:'teal',icon:'check',ratio:pct(completed,pending+answering+submitted+completed)}
  ]
  return [
    {label:'授权人才',value:people,note:`外部 ${external} · 内部 ${internal}`,key:'talents',tone:'blue',icon:'people',ratio:null,segments:peopleSegments,legend:peopleSegments},
    {label:'有效岗位',value:active,note:`草稿 ${draft} · 停用 ${disabled}`,key:'requirements',tone:'teal',icon:'case',ratio:pct(active,active+draft+disabled)},
    {label:'处理中解析',value:queued+running,note:`排队 ${queued} · 执行 ${running}${failed?` · 失败 ${failed}`:''}`,key:'tasks',tone:failed?'rose':'amber',icon:'file',ratio:pct(queued+running,queued+running+failed+parsed)},
    {label:'待参与测评',value:pending+answering,note:`待参与 ${pending} · 作答中 ${answering}`,key:'assessments',tone:'violet',icon:'check',ratio:pct(pending+answering,pending+answering+submitted+completed)}
  ].filter(c=>available(c.key))
})
// 待办行的数字同样取真实状态计数，用颜色区分「有没有要处理的事」。
const todos=computed(()=>[
  {key:'tasks',tone:'amber',icon:'file',title:'解析与资料核对',value:count('parse_tasks','queued')+count('parse_tasks','running')+count('parse_tasks','failed'),note:`待处理 ${count('parse_tasks','queued')} · 处理中 ${count('parse_tasks','running')} · 失败 ${count('parse_tasks','failed')}`},
  {key:'assessments',tone:'violet',icon:'check',title:'测评任务',value:count('assessments','pending')+count('assessments','answering')+count('assessments','submitted'),note:`待参与 ${count('assessments','pending')} · 作答中 ${count('assessments','answering')} · 待评分 ${count('assessments','submitted')}`},
  {key:'requirements',tone:'teal',icon:'case',title:'完善岗位需求',value:count('requirements','draft'),note:`草稿 ${count('requirements','draft')} 个 · 确认生效后可匹配`}
].filter(t=>available(t.key)))
const pendingTotal=computed(()=>todos.value.reduce((sum,t)=>sum+t.value,0))
const names:Record<string,string>={draft:'草稿',active:'有效',disabled:'已停用',queued:'待处理',running:'处理中',succeeded:'运行成功',failed:'执行失败'}
const notes:Record<string,string>={candidates:'筛选、比较与导入',talents:'履历、来源与问答',requirements:'岗位、匹配与历史',assessments:'任务、答题与成绩',accounts:'账号与人才绑定',roles:'功能、范围与菜单',catalog:'组织与岗位资料',audit:'操作与模型调用记录'}
const timeText=(seconds:number)=>new Date(seconds*1000).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})
// 匹配进度只用后端真实返回的 pending/evaluated/failed，不再拆成满足/不满足（工作台接口没有该口径）。
const matchDone=(m:MatchSummary)=>m.counts?.evaluated||0
const matchFailed=(m:MatchSummary)=>m.counts?.failed||0
const matchPct=(n:number,m:MatchSummary)=>m.total>0?Math.min(100,Math.round(n/m.total*100)):0
async function load(){loading.value=true;error.value='';try{data.value=await props.api('/workbench')}catch(e){error.value=(e as Error).message}finally{loading.value=false}}
onMounted(load)
</script>
<template>
  <div class="title-row"><div><h1>{{mode==='self'?'我的工作台':mode==='admin'?'管理工作台':'工作台'}}</h1><p class="title-sub">{{mode==='admin'?'账号、角色与组织资料的统一管理入口':'今天需要处理的事，以及仍在进行中的招聘'}}</p></div><el-button :loading="loading" @click="load">刷新</el-button></div>
  <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button @click="load">重试</el-button></el-alert>

  <div v-if="mode!=='admin'" v-loading="loading" class="kpi-grid">
    <button v-for="c in cards" :key="c.label" type="button" class="kpi-card" :class="['tone-'+c.tone,{'has-donut':!!c.segments}]" @click="emit('navigate',c.key)">
      <div class="kpi-top"><span class="kpi-icon"><AppIcon :name="c.icon"/></span><span class="kpi-label">{{c.label}}</span></div>
      <strong class="kpi-value">{{data?c.value:'—'}}</strong>
      <MiniDonut v-if="c.segments" class="kpi-donut" :segments="c.segments" :size="40" :thickness="7"/>
      <span v-if="c.legend" class="kpi-legend"><span v-for="l in c.legend" :key="l.label"><i :style="{background:l.color}"/>{{l.label}} {{l.value}}</span></span>
      <span v-else class="kpi-note">{{c.note}}</span>
      <span v-if="c.ratio!==null" class="kpi-meter" :title="c.note"><i :style="{width:(c.ratio??0)+'%'}"/></span>
      <span v-else-if="!c.segments" class="kpi-meter is-flat"><i style="width:100%"/></span>
    </button>
  </div>
  <p v-else class="muted">管理账号、角色和组织资料；此视角仅显示已获授权的管理入口。</p>

  <div v-if="mode==='admin'" class="overview-body single"><el-card><template #header><h2>业务入口</h2></template><div class="overview-flow admin-flow"><button v-for="item in shortcuts" :key="item.key" @click="emit('navigate',item.key)"><strong>{{item.name}}</strong><span>{{notes[item.key]||'进入工作区'}} →</span></button></div><el-empty v-if="!shortcuts?.length" description="暂无可用入口，请联系管理员配置菜单与权限" :image-size="48"/></el-card></div>

  <div v-else class="overview-body">
    <el-card>
      <template #header><div class="card-head"><h2>{{mode==='self'?'我的待办':'待处理事项'}}</h2><span class="card-hint" :class="{warn:pendingTotal>0}">{{pendingTotal?pendingTotal+' 项需要处理':'暂无积压'}}</span></div></template>
      <div v-for="t in todos" :key="t.key" class="todo-item" :class="'tone-'+t.tone" @click="emit('navigate',t.key)">
        <span class="todo-icon"><AppIcon :name="t.icon"/></span>
        <div class="todo-body"><strong>{{t.title}}</strong><p>{{t.note}}</p></div>
        <span class="todo-count" :class="{zero:!t.value}">{{t.value}}</span>
        <el-button link type="primary" class="todo-go" @click.stop="emit('navigate',t.key)">查看</el-button>
      </div>
      <el-empty v-if="!pendingTotal" description="当前没有待处理事项" :image-size="40"/>
    </el-card>
    <el-card v-if="available('requirements')">
      <template #header><div class="card-head"><h2>当前招聘需求</h2><el-button link type="primary" @click="emit('navigate','requirements')">全部岗位</el-button></div></template>
      <div v-for="r in data?.recent_requirements||[]" :key="r.id" class="req-item">
        <span class="req-dot" :class="'state-'+r.status"/>
        <div class="req-body"><strong>{{r.title||'未命名草稿'}}</strong><p>{{r.department}} · {{r.active_version?'有效版本 v'+r.active_version:'尚未生效'}}</p></div>
        <el-tag :type="r.status==='active'?'success':r.status==='draft'?'warning':'info'" size="small" effect="light">{{names[r.status]}}</el-tag>
        <el-button link type="primary" @click="emit('requirement',{id:r.id})">进入</el-button>
      </div>
      <el-empty v-if="!data?.recent_requirements?.length" description="当前权限内暂无岗位需求" :image-size="40"/>
    </el-card>
  </div>

  <el-card v-if="mode!=='admin'" class="recent-matches">
    <template #header><div class="card-head"><h2>最近匹配结果</h2><el-button v-if="available('requirements')" link type="primary" @click="emit('navigate','requirements')">全部记录</el-button></div></template>
    <div v-for="m in data?.recent_matches||[]" :key="m.id" class="match-item">
      <div class="match-head">
        <strong>{{m.title||'岗位匹配'}}</strong>
        <el-tag v-if="m.stale" type="warning" size="small">历史参考</el-tag>
        <span class="match-time">岗位 v{{m.requirement_version}} · {{timeText(m.created_at)}}</span>
        <el-button link type="primary" @click="emit('requirement',{id:m.requirement_id,runId:m.id})">查看结果</el-button>
      </div>
      <div class="match-meter" :title="`已完成 ${matchDone(m)} / ${m.total} 人`">
        <i class="seg-done" :style="{width:matchPct(matchDone(m),m)+'%'}"/>
        <i v-if="matchFailed(m)" class="seg-fail" :style="{width:matchPct(matchFailed(m),m)+'%'}"/>
      </div>
      <p class="match-legend"><span class="dot-done"/>已完成 {{matchDone(m)}} / {{m.total}} 人<span v-if="matchFailed(m)" class="fail-text"><span class="dot-fail"/>执行失败 {{matchFailed(m)}}</span></p>
    </div>
    <el-empty v-if="!data?.recent_matches?.length" description="暂无本人发起且当前有权查看的匹配结果" :image-size="40"/>
  </el-card>
</template>
<style scoped>
.title-sub{margin:4px 0 0;font-size:12px;color:var(--text-tertiary)}
/* 指标卡：一个语义色只代表一类对象，颜色不承担装饰作用。 */
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px}
.kpi-card{position:relative;display:flex;flex-direction:column;gap:5px;border:1px solid var(--border);background:var(--surface);border-radius:var(--radius);padding:14px 16px 13px;text-align:left;cursor:pointer;color:var(--text);box-shadow:var(--shadow);transition:border-color .15s,transform .15s}
.kpi-card:hover{border-color:var(--tone);transform:translateY(-1px)}
.kpi-top{display:flex;align-items:center;gap:8px}
.kpi-icon{width:26px;height:26px;border-radius:8px;display:grid;place-items:center;background:var(--tone-soft);color:var(--tone)}
.kpi-label{font-size:12px;color:var(--text-secondary)}
.kpi-value{font-size:27px;font-weight:600;line-height:1.15;font-variant-numeric:tabular-nums;letter-spacing:-.5px}
/* 环形图与数值行垂直对齐，不改变卡片的文字基线。 */
.kpi-donut{position:absolute;right:14px;top:42px}
.kpi-card.has-donut .kpi-value{padding-right:50px}
.kpi-note{font-size:11px;color:var(--text-tertiary)}
/* 构成类指标用环形图 + 颜色图例，避免用进度条暗示「完成度」。 */
.kpi-legend{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:11px;color:var(--text-secondary)}
.kpi-legend span{display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.kpi-legend i{width:7px;height:7px;border-radius:50%;display:inline-block;flex-shrink:0}
.kpi-meter{display:block;height:4px;border-radius:99px;background:#eceff6;overflow:hidden;margin-top:3px}
.kpi-meter i{display:block;height:100%;border-radius:99px;background:var(--tone);transition:width .4s ease}
.kpi-meter.is-flat i{background:var(--border-strong)}
.tone-blue{--tone:#2f5bea;--tone-soft:#eef3ff}
.tone-teal{--tone:#0f766e;--tone-soft:#e2f5f1}
.tone-amber{--tone:#b45309;--tone-soft:#fdf1e0}
.tone-rose{--tone:#c0393f;--tone-soft:#fdeceb}
.tone-violet{--tone:#7440c4;--tone-soft:#f2ebfd}
.overview-body{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;align-items:start}
.overview-body.single{grid-template-columns:1fr}
.overview-body>.el-card{margin:0}
.card-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.card-head h2{font-size:14px;margin:0;font-weight:600}
.card-hint{font-size:11px;color:var(--text-tertiary);padding:2px 8px;border-radius:99px;background:var(--surface-muted)}
.card-hint.warn{color:#b45309;background:#fdf1e0}
.todo-item{display:flex;align-items:center;gap:11px;padding:11px 8px;margin:0 -8px;border-radius:10px;cursor:pointer;border-bottom:1px solid var(--border)}
.todo-item:last-of-type{border-bottom:0}
.todo-item:hover{background:var(--surface-muted)}
.todo-icon{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;background:var(--tone-soft);color:var(--tone);flex-shrink:0}
.todo-body{flex:1;min-width:0}
.todo-body strong{display:block;font-size:13px;font-weight:550}
.todo-body p{font-size:11.5px;color:var(--text-secondary);margin:3px 0 0}
.todo-count{font-size:19px;font-weight:600;color:var(--tone);font-variant-numeric:tabular-nums;line-height:1;flex-shrink:0}
.todo-count.zero{color:var(--text-tertiary)}
.todo-go{flex-shrink:0;margin-left:6px}
.req-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border)}
.req-item:last-of-type{border-bottom:0;padding-bottom:0}
.req-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;background:var(--border-strong)}
.req-dot.state-active{background:#1a9e6f}
.req-dot.state-draft{background:#d99426}
.req-body{flex:1;min-width:0}
.req-body strong{display:block;font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.req-body p{font-size:11.5px;color:var(--text-secondary);margin:3px 0 0}
.recent-matches{margin-bottom:0}
.match-item{padding:11px 0;border-bottom:1px solid var(--border)}
.match-item:last-of-type{border-bottom:0;padding-bottom:0}
.match-head{display:flex;align-items:center;gap:8px}
.match-head strong{font-size:13px;font-weight:550;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.match-head .el-button{margin-left:auto;flex-shrink:0}
.match-time{font-size:11px;color:var(--text-tertiary);white-space:nowrap;flex-shrink:0}
.match-meter{display:flex;height:4px;border-radius:99px;background:#eceff6;overflow:hidden;margin:8px 0 5px}
.match-meter i{display:block;height:100%}
.seg-done{background:linear-gradient(90deg,#3b63f3,#2f5bea)}
.seg-fail{background:#c0393f}
.match-legend{display:flex;align-items:center;gap:6px;margin:0;font-size:11px;color:var(--text-tertiary)}
.dot-done,.dot-fail{width:6px;height:6px;border-radius:50%;display:inline-block}
.dot-done{background:#2f5bea}
.dot-fail{background:#c0393f;margin-right:4px}
.fail-text{display:inline-flex;align-items:center;margin-left:8px;color:#c0393f}
.overview-flow{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.overview-flow button{padding:14px;text-align:left;cursor:pointer;color:var(--text);background:var(--surface);border:1px solid var(--border);border-radius:10px}
.overview-flow button:hover{border-color:var(--accent);background:var(--accent-soft)}
.overview-flow strong{display:block;font-size:13px;font-weight:500}
.overview-flow span{display:block;font-size:12px;color:var(--text-tertiary);margin-top:4px}
.admin-flow{grid-template-columns:repeat(4,minmax(0,1fr))}
@media(max-width:1050px){.overview-body{grid-template-columns:1fr}.admin-flow{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:600px){.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.overview-flow{grid-template-columns:1fr}.match-head{flex-wrap:wrap}}
</style>
