<script setup lang="ts">
import {ref,watch} from 'vue'
import ChatWorkspace from './ChatWorkspace.vue'
import type {Api} from './api'
const props=defineProps<{id:string;name:string;kind:string;department:string;version:number;api:Api;token:string;canChat:boolean;editing:boolean;backLabel:string}>()
const emit=defineEmits<{back:[];edit:[]}>()
const tab=ref('facts'),showAI=ref(window.matchMedia('(min-width:901px)').matches)
watch(()=>props.id,()=>{tab.value='facts';showAI.value=window.matchMedia('(min-width:901px)').matches})
</script>
<template>
  <section class="profile-workspace" aria-label="人才画像工作区">
    <div class="object-heading"><el-button @click="emit('back')">← {{backLabel}}</el-button><div class="object-title"><h1>{{name||'新建人才'}}</h1><span class="muted">{{kind==='internal'?'内部员工':'外部候选人'}}<template v-if="kind==='internal'"> · {{department}}</template> · 档案 v{{version}}</span></div><div class="object-actions"><slot name="actions"/><el-button v-if="id&&canChat" :aria-expanded="showAI" @click="showAI=!showAI">{{showAI?'收起 AI 助手':'打开 AI 助手'}}</el-button></div></div>
    <div class="profile-split" :class="{'with-ai':id&&canChat&&showAI,'ai-focused':showAI&&!editing}">
      <section class="profile-document" aria-label="档案资料">
        <template v-if="editing"><slot name="edit"/></template>
        <template v-else><el-tabs v-model="tab" class="workspace-tabs"><el-tab-pane label="事实与履历" name="facts"/><el-tab-pane label="来源文件" name="files"/><el-tab-pane label="测评记录" name="assessments"/><el-tab-pane label="修改历史" name="history"/></el-tabs><div class="profile-document-body"><slot v-if="tab==='facts'" name="facts"/><slot v-if="tab==='files'" name="files"/><slot v-if="tab==='assessments'" name="assessments"/><slot v-if="tab==='history'" name="history"/></div></template>
      </section>
      <section v-if="id&&canChat" v-show="showAI" class="profile-ai" aria-label="当前人才AI助手"><ChatWorkspace :key="id" :api="api" :token="token" :context="{kind:'selected',ids:[id]}" :scope-label="name" embedded/></section>
    </div>
  </section>
</template>
<style scoped>
.profile-workspace{height:calc(100dvh - 100px);min-height:320px;display:flex;flex-direction:column;gap:12px}.profile-split{display:grid;grid-template-columns:minmax(0,1fr);gap:16px;flex:1;min-height:0}.profile-split.with-ai{grid-template-columns:minmax(0,1.25fr) minmax(360px,1fr)}.profile-document{min-width:0;min-height:0;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:auto;padding:16px 20px}.profile-document>.workspace-tabs{flex-shrink:0;margin:0}.profile-document-body{flex:1;min-height:0;overflow:auto;padding:8px 4px 16px 0}.profile-ai{padding:16px;min-height:0;min-width:0;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}.object-actions{display:flex;gap:8px;flex-wrap:wrap}.object-actions .el-button{margin:0}@media(max-width:1050px){.profile-split.with-ai{grid-template-columns:minmax(0,1fr) minmax(310px,1fr)}}@media(max-width:900px){.profile-split.with-ai{grid-template-columns:1fr}.profile-split.with-ai.ai-focused .profile-document{display:none}.profile-split.with-ai:not(.ai-focused) .profile-ai{display:none}.profile-document{padding:12px}.profile-workspace{height:calc(100dvh - 120px)}.object-heading{gap:8px}.object-actions{width:100%}.profile-ai{padding:12px}}
</style>
