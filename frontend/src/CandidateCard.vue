<script setup lang="ts">
import {ref} from 'vue'
import {qualityName,indexName} from './labels'
import type {Candidate} from './candidate'
defineProps<{person:Candidate;selected:boolean;canChat?:boolean}>()
const emit=defineEmits<{open:[id:string];toggle:[id:string]}>()
const expanded=ref(false)
const groups:Record<string,string>={pass:'满足',unknown:'待核对',fail:'不满足',pending:'待处理',failed:'失败',unmatched:'未匹配',evaluated:'已评估'}
</script>
<template>
    <article class="candidate-card" :class="{'is-selected':selected}" data-testid="candidate-card">
      <div class="candidate-top"><div class="person-monogram" aria-hidden="true">{{person.name.slice(0,1)||'人'}}</div><div class="person-title"><h2>{{person.name||'姓名未知'}}</h2><span class="muted">{{person.kind==='internal'?'内部员工':'外部候选人'}}</span></div><el-checkbox v-if="canChat" :model-value="selected" :aria-label="'选择'+person.name" @change="emit('toggle',person.id)"/></div>
      <div class="card-status"><el-tag :type="['complete','manual'].includes(person.quality||'')?'info':'warning'" size="small">{{qualityName[person.quality||'']||'资料状态未知'}}</el-tag><span class="muted">{{person.tags.some(t=>!t.confirmed)?'含简历声明':'人工维护资料'}}</span></div>
      <p class="career-summary">{{person.tags.find(t=>t.category==='experience')?.content||person.tags.find(t=>t.category==='education')?.content||'暂无履历摘要，可打开档案查看来源。'}}</p>
      <div class="skill-tags"><span v-for="(tag,i) in person.tags.filter(t=>t.category==='skill').slice(0,expanded?undefined:4)" :key="i">{{tag.content}}</span><span v-if="!person.tags.some(t=>t.category==='skill')" class="muted">暂未记录技能</span></div>
      <el-button v-if="person.tags.filter(t=>t.category==='skill').length>4" text @click="expanded=!expanded">{{expanded?'收起标签':'展开全部技能'}}</el-button>
      <details v-if="person.requirements?.length" class="match-summary"><summary>关联 {{person.requirements.length}} 个岗位需求</summary><p v-for="r in person.requirements" :key="r.requirement_id">{{r.title}} · {{groups[r.group||r.state]||r.state}} · {{r.score??'—'}}<small v-if="r.requirement_version"> / 需求v{{r.requirement_version}}</small><el-tag v-if="r.stale||r.requirement_status!=='active'" type="warning">旧结果 / 需求、档案或规则已变更</el-tag></p></details>
      <div class="candidate-bottom"><span class="muted">索引：{{indexName[person.index_state]||person.index_state}}</span><el-button type="primary" plain @click="emit('open',person.id)">查看档案</el-button></div>
    </article>
</template>
<style scoped>
.candidate-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:22px;display:flex;flex-direction:column;min-width:0;transition:border-color .18s,box-shadow .18s}.candidate-card:hover{border-color:var(--el-color-primary-light-5);box-shadow:var(--shadow)}.candidate-card.is-selected{border:2px solid var(--accent);padding:21px;background:var(--accent-soft)}.candidate-top{display:flex;gap:12px;align-items:center}.person-monogram{display:grid;place-items:center;width:44px;height:44px;flex-shrink:0;border-radius:14px;background:var(--accent-soft);color:var(--accent);font-weight:700}.person-title{flex:1;min-width:0}.person-title h2{font-size:18px;margin:0 0 4px;overflow-wrap:anywhere}.card-status{display:flex;gap:8px;align-items:center;margin-top:20px;flex-wrap:wrap}.career-summary{font-size:14px;line-height:1.8;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;min-height:76px}.skill-tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:20px}.skill-tags span{font-size:12px;padding:4px 9px;border-radius:6px;background:var(--surface-muted);overflow-wrap:anywhere;max-width:100%}.candidate-bottom{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:auto;padding-top:16px;border-top:1px solid var(--border)}.candidate-bottom .muted{font-size:12px}.match-summary{font-size:13px;margin-bottom:16px}.match-summary summary{cursor:pointer}
</style>
