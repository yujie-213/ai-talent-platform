<script setup lang="ts">
import {ref,onMounted} from 'vue'
import {ElMessage} from 'element-plus'
import type {Api} from './api'
import {auditActionName, aiOperationName, errorName} from './labels'
import PageHeader from './PageHeader.vue'
import StatusTag from './StatusTag.vue'
import UuidShort from './UuidShort.vue'
import EmptyState from './EmptyState.vue'
const props=defineProps<{api:Api}>()
const kind=ref('audit'),action=ref(''),state=ref(''),page=ref(1),total=ref(0),items=ref<Record<string,unknown>[]>([])
let requestSerial=0
async function load(){const request=++requestSerial;try{const data=await props.api<{items:Record<string,unknown>[];total:number}>(`/admin/logs/${kind.value}?offset=${(page.value-1)*20}&limit=20&action=${encodeURIComponent(action.value)}&state=${encodeURIComponent(state.value)}`);if(request!==requestSerial)return;items.value=data.items;total.value=data.total}catch(e){if(request===requestSerial)ElMessage.error((e as Error).message)}}
onMounted(load)
const actionText=(row:Record<string,unknown>)=>{const code=String(kind.value==='audit'?row.action:row.operation||'');return (kind.value==='audit'?auditActionName:aiOperationName)[code]||code||'—'}
const actionCode=(row:Record<string,unknown>)=>String(kind.value==='audit'?row.action:row.operation||'')
const stateText=(row:Record<string,unknown>)=>String(kind.value==='audit'?row.outcome??row.state:row.state||'')
</script>
<template>
  <PageHeader title="操作审计与 AI 调用记录" subtitle="谁在什么时间做了什么，以及每次 AI 调用的耗时与结果。"/>
  <div class="log-filters">
    <el-radio-group v-model="kind" @change="page=1;load()"><el-radio-button value="audit">操作审计</el-radio-button><el-radio-button value="ai">AI 调用记录</el-radio-button></el-radio-group>
    <el-form inline @submit.prevent="page=1;load()">
      <el-form-item :label="kind==='audit'?'操作动作':'调用类型'"><el-input v-model="action" placeholder="按名称包含" clearable/></el-form-item>
      <el-form-item label="执行状态"><el-select v-model="state" clearable placeholder="全部状态" style="width:150px"><el-option v-for="(label,value) in {success:'成功',succeeded:'已完成',failed:'失败',denied:'已拒绝'}" :key="value" :label="label" :value="value"/></el-select></el-form-item>
      <el-button type="primary" native-type="submit">查询</el-button>
    </el-form>
  </div>
  <el-table :data="items">
    <el-table-column :label="kind==='audit'?'动作':'调用类型'" min-width="130"><template #default="s"><span class="action-name">{{actionText(s.row)}}</span><span class="action-code">{{actionCode(s.row)}}</span></template></el-table-column>
    <el-table-column :label="kind==='audit'?'对象':'目标'" min-width="118"><template #default="s"><UuidShort v-if="s.row.target_id" :id="String(s.row.target_id)"/><span v-else class="muted">—</span></template></el-table-column>
    <el-table-column label="状态" width="88"><template #default="s"><StatusTag :state="stateText(s.row)"/></template></el-table-column>
    <template v-if="kind==='ai'"><el-table-column prop="model" label="模型" min-width="120" show-overflow-tooltip/><el-table-column label="耗时" width="90"><template #default="s">{{s.row.elapsed_ms!=null?Math.round(Number(s.row.elapsed_ms)/100)/10+' s':'—'}}</template></el-table-column><el-table-column label="错误" min-width="140"><template #default="s"><span v-if="s.row.error_code" class="err-text">{{errorName[String(s.row.error_code)]||s.row.error_code}}</span><span v-else class="muted">—</span></template></el-table-column></template>
    <el-table-column v-else label="追踪编号" min-width="118"><template #default="s"><UuidShort v-if="s.row.request_id" :id="String(s.row.request_id)"/><span v-else class="muted">—</span></template></el-table-column>
    <el-table-column label="时间" width="134"><template #default="s">{{new Date(Number(s.row.created_at)*1000).toLocaleString()}}</template></el-table-column>
  </el-table>
  <EmptyState v-if="!items.length" icon="clock" title="当前条件下暂无记录" hint="调整筛选条件或时间范围后再试。"/>
  <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="total,prev,pager,next" @current-change="load"/>
</template>

<style scoped>
.log-filters{display:flex;align-items:flex-start;gap:14px;flex-wrap:wrap;margin-bottom:14px}
.log-filters .el-form-item{margin-bottom:0}
.action-name{display:block;font-size:13px;color:var(--text);font-weight:500}
.action-code{display:block;font-size:11px;color:var(--text-tertiary);font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;margin-top:2px}
.err-text{color:#a93434;font-size:12px}
.muted{color:var(--text-tertiary);font-size:12px}
</style>
