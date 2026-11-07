<script setup lang="ts">
import {categoryName} from './labels'
interface ProfileFact {id?:string;category:string;content:string;confirmed?:boolean;source_version?:number;source_type?:string;quote?:string;locator?:string;source_task_id?:string}
defineProps<{talent:{name:string;kind:string;phone:string;email:string;facts?:ProfileFact[]}}>()
const emit=defineEmits<{source:[fact:ProfileFact]}>()
const categories=['education','experience','project','skill','certificate']
</script>
<template><div class="profile-contacts"><div><span>电话</span><p>{{talent.phone||'未记录'}}</p></div><div><span>邮箱</span><p>{{talent.email||'未记录'}}</p></div></div><section v-for="category in categories" :key="category" class="profile-fact-group"><h2>{{categoryName[category]}}</h2><article v-for="(fact,index) in talent.facts?.filter(f=>f.category===category)||[]" :key="index"><p>{{fact.content}}</p><div class="fact-source"><span class="muted">{{fact.confirmed?'人工维护':'简历声明'}} · 来源版本 {{fact.source_version??'未知'}}</span><el-button link type="primary" @click="emit('source',fact)">核对来源</el-button></div></article><p v-if="!talent.facts?.some(f=>f.category===category)" class="muted">暂未记录{{categoryName[category]}}资料</p></section></template>
<style scoped>
.profile-contacts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;padding:8px 0 14px;border-bottom:1px solid var(--border)}.profile-contacts span{font-size:12px;color:var(--text-secondary)}.profile-contacts p{margin:5px 0;overflow-wrap:anywhere}.profile-fact-group h2{font-size:15px;margin:20px 0 12px}.profile-fact-group article{padding:0 0 0 12px;border-left:2px solid var(--accent-soft);margin:12px 0 18px}.profile-fact-group article p{white-space:pre-wrap;font-size:14px;line-height:1.85;margin:0 0 5px}.fact-source{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.fact-source .muted{font-size:12px}
</style>
