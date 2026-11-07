<script setup lang="ts">
import type { Candidate } from './candidate'
import {qualityName} from './labels'
defineProps<{items:Candidate[];selected:string[];canChat?:boolean}>()
const emit=defineEmits<{open:[id:string];toggle:[id:string];selectPage:[checked:boolean]}>()
const text=(p:Candidate,category:string)=>p.tags.filter(t=>t.category===category).map(t=>t.content).join('；')
// 技能事实有两种写法：一条是「Python、FastAPI、MySQL」的列举，一条是「Python开发经验3年，……」的整句。
// 取第一个分句，再按顿号拆分，能同时覆盖两种写法，也不会把整句描述塞进标签。
function skills(p:Candidate){
  const out:string[]=[]
  for(const tag of p.tags){
    if(tag.category!=='skill')continue
    const lead=tag.content.split(/[，。；;]/)[0]||''
    for(const raw of lead.split('、')){
      const value=raw.trim().replace(/\s+/g,' ').replace(/(开发|使用|工作)经验\s*\d+\s*年?$/,'').trim()
      if(!value||value.length>16||out.includes(value))continue
      out.push(value)
    }
  }
  return out
}
const groupNames:Record<string,string>={pass:'满足',unknown:'待核对',fail:'不满足',pending:'处理中',failed:'执行失败'}
const groupTypes:Record<string,string>={pass:'success',unknown:'warning',fail:'danger',pending:'info',failed:'danger'}
const scoreText=(value:number|null|undefined)=>value==null?'—':String(Math.round(value))
</script>
<template>
  <el-table :data="items" row-key="id" class="candidate-table" aria-label="候选人列表" @row-click="(p:Candidate)=>emit('open',p.id)">
    <el-table-column v-if="canChat" width="44">
      <template #header><el-checkbox aria-label="选择本页全部人才" :model-value="!!items.length&&items.every(p=>selected.includes(p.id))" :indeterminate="selected.length>0&&!items.every(p=>selected.includes(p.id))" @change="(v:unknown)=>emit('selectPage',!!v)"/></template>
      <template #default="{row}"><el-checkbox :aria-label="'选择'+row.name" :model-value="selected.includes(row.id)" @click.stop @change="emit('toggle',row.id)"/></template>
    </el-table-column>
    <el-table-column label="人才" min-width="148"><template #default="{row}"><div class="person-cell"><button class="person-name" @click.stop="emit('open',row.id)">{{row.name}}</button><div class="person-meta"><span>{{row.kind==='internal'?'内部员工':'外部候选人'}}</span><el-tag v-if="row.quality&&!['complete','manual'].includes(row.quality)" type="warning" size="small">{{qualityName[row.quality]||'待核对'}}</el-tag></div></div></template></el-table-column>
    <el-table-column label="履历摘要" min-width="270"><template #default="{row}"><p class="digest-line">{{text(row,'education')||'教育未记录'}}</p><p class="digest-line digest-muted">{{text(row,'experience')||'经历未记录'}}</p></template></el-table-column>
    <el-table-column label="核心技能" min-width="216"><template #default="{row}"><div class="skill-list"><el-tag v-for="(s,i) in skills(row).slice(0,4)" :key="i" size="small" type="info">{{s}}</el-tag><span v-if="skills(row).length>4" class="skill-rest">+{{skills(row).length-4}}</span><span v-if="!skills(row).length" class="empty-hint">未记录</span></div></template></el-table-column>
    <el-table-column label="应聘岗位 / 匹配" min-width="222"><template #default="{row}"><div v-for="r in row.requirements||[]" :key="r.requirement_id" class="linked-requirement"><div class="requirement-line"><strong>{{r.title}}</strong></div><div class="requirement-meta"><el-tag :type="groupTypes[r.group||r.state]||'info'" size="small">{{groupNames[r.group||r.state]||'尚无匹配'}}</el-tag><span v-if="r.score!=null" class="match-score" title="本次范围内的辅助排序值，不代表能力或录用概率">{{scoreText(r.score)}} 分</span><span v-if="r.stale||r.requirement_status!=='active'">历史参考</span><span v-else-if="r.created_at">{{new Date(r.created_at*1000).toLocaleDateString()}}</span></div></div><span v-if="!row.requirements?.length" class="empty-hint">未关联应聘岗位</span></template></el-table-column>
    <el-table-column width="84" fixed="right"><template #default="{row}"><el-button link type="primary" class="row-action" @click.stop="emit('open',row.id)">查看画像</el-button></template></el-table-column>
  </el-table>
</template>
<style scoped>
.candidate-table :deep(.el-table__row){height:66px;cursor:pointer}
.candidate-table :deep(.el-table__cell){padding:8px 0}
.person-cell{display:flex;flex-direction:column;gap:3px;min-width:0}
.person-name{border:0;background:transparent;color:var(--text);font-weight:600;cursor:pointer;padding:0;font-size:14px;text-align:left;line-height:1.4}
.person-name:hover{color:var(--accent)}
.person-meta{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text-tertiary)}
.digest-line{display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden;margin:0;font-size:13px;line-height:1.6;color:var(--text)}
.digest-muted{margin-top:2px;font-size:12px;color:var(--text-secondary)}
.skill-list{display:flex;flex-wrap:wrap;gap:4px;align-items:center;max-height:52px;overflow:hidden}
.skill-list :deep(.el-tag){background:var(--surface-muted);border-color:var(--border);color:var(--text-secondary);white-space:nowrap;flex-shrink:0;max-width:100%}
.skill-rest{font-size:12px;color:var(--text-tertiary)}
.empty-hint{font-size:12px;color:var(--text-tertiary)}
.linked-requirement+.linked-requirement{margin-top:6px}
.requirement-line{min-width:0}
.requirement-line strong{display:block;font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.match-score{font-size:12px;font-weight:600;color:var(--text);font-variant-numeric:tabular-nums}
.requirement-meta{display:flex;align-items:center;gap:6px;margin-top:4px;font-size:11px;color:var(--text-tertiary)}
.row-action{padding:0}
</style>
