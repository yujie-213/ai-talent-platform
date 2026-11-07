<script setup lang="ts">
import type { Candidate } from './candidate'
import {qualityName} from './labels'
defineProps<{items:Candidate[];selected:string[];canChat?:boolean}>()
const emit=defineEmits<{open:[id:string];toggle:[id:string];selectPage:[checked:boolean]}>()
const text=(p:Candidate,category:string)=>p.tags.filter(t=>t.category===category).map(t=>t.content).join('；')
const groupNames:Record<string,string>={pass:'满足',unknown:'待核对',fail:'不满足',pending:'处理中',failed:'执行失败'}
</script>
<template>
  <el-table :data="items" row-key="id" class="candidate-table" aria-label="候选人列表" @row-click="(p:Candidate)=>emit('open',p.id)">
    <el-table-column v-if="canChat" width="48">
      <template #header><el-checkbox aria-label="选择本页全部人才" :model-value="!!items.length&&items.every(p=>selected.includes(p.id))" :indeterminate="selected.length>0&&!items.every(p=>selected.includes(p.id))" @change="(v:unknown)=>emit('selectPage',!!v)"/></template>
      <template #default="{row}"><el-checkbox :aria-label="'选择'+row.name" :model-value="selected.includes(row.id)" @click.stop @change="emit('toggle',row.id)"/></template>
    </el-table-column>
    <el-table-column label="人才" min-width="150"><template #default="{row}"><button class="person-name" @click.stop="emit('open',row.id)">{{row.name}}</button><span class="cell-meta">{{row.kind==='internal'?'内部员工':'外部候选人'}}</span><el-tag v-if="row.quality&&!['complete','manual'].includes(row.quality)" type="warning" size="small">{{qualityName[row.quality]||'资料需核对'}}</el-tag></template></el-table-column>
    <el-table-column label="教育与经历" min-width="250"><template #default="{row}"><div class="resume-snippet"><p>{{text(row,'education')||'教育未记录'}}</p><p class="muted">{{text(row,'experience')||'经历未记录'}}</p></div></template></el-table-column>
    <el-table-column label="技能 / 项目" min-width="220"><template #default="{row}"><div class="skill-list"><el-tag v-for="(t,i) in row.tags.filter((t:any)=>t.category==='skill')" :key="i" size="small">{{t.content}}</el-tag><span v-if="!text(row,'skill')" class="muted">技能未记录</span></div><details v-if="text(row,'project')" class="row-projects" @click.stop><summary>项目经历</summary><p>{{text(row,'project')}}</p></details></template></el-table-column>
    <el-table-column label="应聘岗位与已有匹配" min-width="235"><template #default="{row}"><div v-for="r in row.requirements||[]" :key="r.requirement_id" class="linked-requirement"><strong>{{r.title}}</strong><span v-if="r.score!=null" class="match-number">{{r.score}} 分</span><span class="cell-meta">{{groupNames[r.group||r.state]||'尚无匹配'}}<template v-if="r.requirement_version"> · 岗位 v{{r.requirement_version}}</template><template v-if="r.created_at"> · {{new Date(r.created_at*1000).toLocaleString()}}</template></span><el-tag v-if="r.stale||r.requirement_status!=='active'" type="warning" size="small">历史参考</el-tag></div><span v-if="!row.requirements?.length" class="muted">未关联应聘岗位</span></template></el-table-column>
    <el-table-column label="操作" width="100" fixed="right"><template #default="{row}"><el-button link type="primary" @click.stop="emit('open',row.id)">查看画像</el-button></template></el-table-column>
  </el-table>
</template>
<style scoped>
.person-name{border:0;background:transparent;color:var(--accent);font-weight:650;cursor:pointer;padding:4px 0;font-size:14px;text-align:left}.cell-meta{display:block;font-size:12px;color:var(--text-secondary);line-height:1.6;margin:3px 0}.resume-snippet p{margin:3px 0;white-space:pre-wrap;font-size:13px;line-height:1.6}.skill-list{display:flex;flex-wrap:wrap;gap:5px}.skill-list .el-tag{height:auto;white-space:normal;line-height:1.5;padding:3px 6px}.row-projects{font-size:12px;margin-top:8px}.row-projects summary{color:var(--accent);cursor:pointer}.row-projects p{white-space:pre-wrap;margin:6px 0}.linked-requirement+.linked-requirement{margin-top:10px}.linked-requirement strong{font-size:12px;font-weight:550}.match-number{font-weight:650;color:var(--accent);margin-left:8px;font-variant-numeric:tabular-nums}
</style>
