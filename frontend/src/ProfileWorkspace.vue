<script setup lang="ts">
import {ref,watch} from 'vue'
import ChatWorkspace from './ChatWorkspace.vue'
import type {Api} from './api'
const props=defineProps<{id:string;name:string;kind:string;department:string;version:number;api:Api;token:string;canChat:boolean;editing:boolean;backLabel:string}>()
const emit=defineEmits<{back:[];edit:[]}>()
const tab=ref('facts'),showAI=ref(window.matchMedia('(min-width:901px)').matches)
const stored=Number(localStorage.getItem('profile-split'))
const docPct=ref(Number.isFinite(stored)&&stored>=32&&stored<=72?stored:50)
const splitEl=ref<HTMLElement|null>(null),dragging=ref(false)
watch(()=>props.id,()=>{tab.value='facts';showAI.value=window.matchMedia('(min-width:901px)').matches})
// 拖拽分隔条调整档案与 AI 的宽度比例，比例记在本机；键盘左右键也可调整。
function startDrag(event:PointerEvent){
  const el=splitEl.value;if(!el)return
  const rect=el.getBoundingClientRect(),handle=event.currentTarget as HTMLElement
  handle.setPointerCapture?.(event.pointerId);dragging.value=true
  const move=(ev:PointerEvent)=>{docPct.value=Math.min(72,Math.max(32,((ev.clientX-rect.left)/rect.width)*100))}
  const up=()=>{dragging.value=false;localStorage.setItem('profile-split',String(Math.round(docPct.value)));window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up)}
  window.addEventListener('pointermove',move);window.addEventListener('pointerup',up)
}
function nudge(delta:number){docPct.value=Math.min(72,Math.max(32,docPct.value+delta));localStorage.setItem('profile-split',String(Math.round(docPct.value)))}
</script>
<template>
  <section class="profile-workspace" aria-label="人才画像工作区">
    <div class="object-heading"><el-button @click="emit('back')">← {{backLabel}}</el-button><div class="object-title"><h1>{{name||'新建人才'}}</h1><span class="muted">{{kind==='internal'?'内部员工':'外部候选人'}}<template v-if="kind==='internal'"> · {{department}}</template> · 档案 v{{version}}</span></div><div class="object-actions"><slot name="actions"/><el-button v-if="id&&canChat" :aria-expanded="showAI" @click="showAI=!showAI">{{showAI?'收起 AI 助手':'打开 AI 助手'}}</el-button></div></div>
    <div ref="splitEl" class="profile-split" :class="{'with-ai':id&&canChat&&showAI,'ai-focused':showAI&&!editing,dragging}" :style="{'--doc-width':docPct+'%'}">
      <section class="profile-document" aria-label="档案资料">
        <template v-if="editing"><slot name="edit"/></template>
        <template v-else><el-tabs v-model="tab" class="workspace-tabs"><el-tab-pane label="事实与履历" name="facts"/><el-tab-pane label="来源文件" name="files"/><el-tab-pane label="测评记录" name="assessments"/><el-tab-pane label="修改历史" name="history"/></el-tabs><div class="profile-document-body"><slot v-if="tab==='facts'" name="facts"/><slot v-if="tab==='files'" name="files"/><slot v-if="tab==='assessments'" name="assessments"/><slot v-if="tab==='history'" name="history"/></div></template>
      </section>
      <div v-if="id&&canChat&&showAI" class="split-handle" role="separator" aria-orientation="vertical" aria-label="调整档案与 AI 宽度" :aria-valuenow="Math.round(docPct)" tabindex="0" @pointerdown.prevent="startDrag" @keydown.left.prevent="nudge(-4)" @keydown.right.prevent="nudge(4)"><span class="split-line"></span></div>
      <section v-if="id&&canChat" v-show="showAI" class="profile-ai" aria-label="当前人才AI助手"><ChatWorkspace :key="id" :api="api" :token="token" :context="{kind:'selected',ids:[id]}" :scope-label="name" embedded/></section>
    </div>
  </section>
</template>
<style scoped>
.profile-workspace{height:calc(100dvh - 100px);min-height:320px;display:flex;flex-direction:column;gap:12px}
.profile-split{display:grid;grid-template-columns:minmax(0,1fr);gap:0;flex:1;min-height:0}
.profile-split.with-ai{grid-template-columns:var(--doc-width,50%) 18px minmax(0,1fr)}
.profile-document{min-width:0;min-height:0;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:auto;padding:14px 18px}
.profile-document>.workspace-tabs{flex-shrink:0;margin:0}
.profile-document-body{flex:1;min-height:0;overflow:auto;padding:8px 4px 14px 0}
.profile-ai{padding:14px 16px;min-height:0;min-width:0;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
.split-handle{display:flex;align-items:center;justify-content:center;cursor:col-resize;touch-action:none;background:transparent;border-radius:6px}
.split-line{display:block;width:2px;height:40px;border-radius:2px;background:var(--border-strong);transition:background .15s,height .15s}
.split-handle:hover .split-line,.split-handle:focus-visible .split-line{background:var(--accent);height:64px}
.profile-split.dragging{cursor:col-resize;user-select:none}
.profile-split.dragging .profile-document,.profile-split.dragging .profile-ai{pointer-events:none}
.object-actions{display:flex;gap:8px;flex-wrap:wrap}
.object-actions .el-button{margin:0}
@media(max-width:900px){.profile-split.with-ai{grid-template-columns:1fr}.score-handle,.split-handle{display:none}.profile-split.with-ai.ai-focused .profile-document{display:none}.profile-split.with-ai:not(.ai-focused) .profile-ai{display:none}.profile-document{padding:12px}.profile-workspace{height:calc(100dvh - 120px)}.object-heading{gap:8px}.object-actions{width:100%}.profile-ai{padding:12px}}
</style>
