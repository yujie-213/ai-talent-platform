<script setup lang="ts">
import {categoryName} from './labels'
import AppIcon from './AppIcon.vue'
import StatusTag from './StatusTag.vue'
import FactGrid from './FactGrid.vue'
interface ProfileFact {id?:string;category:string;content:string;confirmed?:boolean;source_version?:number;source_type?:string;quote?:string;locator?:string;source_task_id?:string}
const props=defineProps<{talent:{name:string;kind:string;phone:string;email:string;facts?:ProfileFact[]}}>()
const emit=defineEmits<{source:[fact:ProfileFact]}>()
const categories=['education','experience','project','skill','certificate']
// 每类事实一个稳定的图标与配色，扫一眼即可分区。
const meta:Record<string,{icon:string;bg:string;fg:string}>={
  education:{icon:'file',bg:'#e8efff',fg:'#2f5bea'},
  experience:{icon:'case',bg:'#e7f6ef',fg:'#14715a'},
  project:{icon:'grid',bg:'#f3ebfd',fg:'#7b3fd4'},
  skill:{icon:'check',bg:'#fbf3e3',fg:'#9a6a1c'},
  certificate:{icon:'shield',bg:'#faeaea',fg:'#a93434'},
}
const byCategory=(category:string)=>props.talent.facts?.filter(f=>f.category===category)||[]
const contacts=[{key:'phone',label:'电话',value:props.talent.phone||'未记录'},{key:'email',label:'邮箱',value:props.talent.email||'未记录'}]
</script>
<template>
<FactGrid :items="contacts" class="profile-contacts"/>
<section v-for="category in categories" :key="category" class="profile-fact-group">
  <div class="fact-group-head">
    <span class="fact-group-icon" :style="{background:meta[category].bg,color:meta[category].fg}"><AppIcon :name="meta[category].icon"/></span>
    <h2>{{categoryName[category]}}</h2>
    <span class="fact-group-count">{{byCategory(category).length}} 条</span>
  </div>
  <article v-for="(fact,index) in byCategory(category)" :key="index" class="fact-entry" :style="{borderLeftColor:meta[category].fg}">
    <p class="fact-content">{{fact.content}}</p>
    <blockquote v-if="fact.quote" class="fact-quote">{{fact.quote}}</blockquote>
    <div class="fact-source">
      <StatusTag :state="fact.confirmed?'active':'draft'" :label="fact.confirmed?'人工维护':'简历声明'"/>
      <span class="muted">来源版本 {{fact.source_version??'未知'}}</span>
      <el-button link type="primary" @click="emit('source',fact)">核对来源</el-button>
    </div>
  </article>
  <p v-if="!byCategory(category).length" class="muted fact-empty">暂未记录{{categoryName[category]}}资料</p>
</section>
</template>
<style scoped>
.profile-contacts{padding:4px 0 16px;border-bottom:1px solid var(--border)}
.profile-fact-group{margin-top:20px}
.fact-group-head{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.fact-group-icon{width:26px;height:26px;border-radius:8px;display:grid;place-items:center;flex-shrink:0}
.fact-group-icon :deep(svg){width:14px;height:14px}
.fact-group-head h2{font-size:15px;margin:0;font-weight:600}
.fact-group-count{margin-left:auto;font-size:11px;color:var(--text-tertiary);background:var(--surface-muted);border-radius:10px;padding:2px 8px}
.fact-entry{padding:2px 0 0 12px;border-left:2px solid var(--accent);margin:0 0 16px}
.fact-content{white-space:pre-wrap;font-size:14px;line-height:1.85;margin:0 0 6px}
.fact-quote{margin:0 0 6px;padding:6px 10px;border-left:3px solid var(--border-strong);color:var(--text-secondary);font-size:12px;line-height:1.7;overflow-wrap:anywhere}
.fact-source{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.fact-source .muted{font-size:12px}
.fact-empty{font-size:12px;margin:0 0 4px}
</style>
