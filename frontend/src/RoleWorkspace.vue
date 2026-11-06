<script setup lang="ts">
import { ref,onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { Api } from './api'
const props=defineProps<{api:Api;catalog:Record<string,{id:string;name?:string}[]>}>()
interface Grant {action:string;scope:string;scope_id:string|null}
interface Role {id:string;name:string;version:number;grants:Grant[];enabled_menus:string[]|null}
const menus=ref<{key:string;label:string}[]>([])
const roles=ref<Role[]>([]), name=ref(''), busy=ref(false)
const actions:Record<string,string>={'talent.read':'人才查看','talent.write':'人才编辑','file.read':'文件查看','file.write':'文件上传','task.run':'解析执行','requirement.read':'需求查看','requirement.write':'需求维护','account.manage':'账号角色管理','catalog.manage':'基础资料维护','audit.read':'审计查看','assessment.manage':'题库试卷管理','assessment.assign':'测评分配','assessment.read':'测评结果查看','chat.use':'档案聊天'}
const scopes:Record<string,string>={self:'本人',department:'指定部门',internal_all:'全公司内部',external_all:'全部外部',owner:'本人负责外部',pool:'指定人才库',global:'全局管理'}
async function run(fn:()=>Promise<void>){busy.value=true;try{await fn()}catch(e){ElMessage.error((e as Error).message)}finally{busy.value=false}}
async function load(){menus.value=await props.api('/admin/menu-options');roles.value=await props.api('/admin/roles');for(const r of roles.value)r.enabled_menus??=menus.value.map(m=>m.key)}
async function saveMenus(r:Role){await run(async()=>{await props.api(`/admin/roles/${r.id}/menus`,'PUT',{version:r.version,menus:r.enabled_menus});await load();ElMessage.success('菜单显示配置已保存；API仍按功能与数据范围授权')})}
async function create(){await run(async()=>{await props.api('/admin/roles','POST',{name:name.value});name.value='';await load()})}
async function save(r:Role){await run(async()=>{await props.api(`/admin/roles/${r.id}/grants`,'PUT',{version:r.version,grants:r.grants.map(g=>({action:g.action,scope:g.scope,scope_id:['department','pool'].includes(g.scope)?g.scope_id:null}))});await load();ElMessage.success('角色权限已保存，下次请求即生效')})}
function options(action:string){return ['account.manage','catalog.manage','audit.read','assessment.manage'].includes(action)?['global']:action.startsWith('requirement.')?['global','department']:['self','department','internal_all','external_all','owner','pool']}
onMounted(()=>run(load))
</script>
<template><h1>角色、功能与数据范围</h1><p>每项动作独立配置；查看权不会扩大修改权。菜单随当前授权显示，后端始终重新鉴权。</p><el-input v-model="name" placeholder="新角色名称" style="width:260px"/><el-button @click="create">创建角色</el-button><el-card v-for="r in roles" :key="r.id"><h2>{{r.name}} · v{{r.version}}</h2><div v-for="(g,i) in r.grants" :key="i" class="file-row"><el-select v-model="g.action" @change="g.scope=options(g.action)[0];g.scope_id=null"><el-option v-for="(label,value) in actions" :key="value" :label="label" :value="value"/></el-select><el-select v-model="g.scope" @change="g.scope_id=null"><el-option v-for="s in options(g.action)" :key="s" :value="s" :label="scopes[s]"/></el-select><el-select v-if="['department','pool'].includes(g.scope)" v-model="g.scope_id" placeholder="指定范围"><el-option v-for="c in catalog[g.scope==='department'?'departments':'pools']" :key="c.id" :value="c.id" :label="c.name"/></el-select><el-button @click="r.grants.splice(i,1)">移除</el-button></div><h3>菜单显示范围</h3><p class="muted">显示菜单还需具备对应功能权限；隐藏菜单不撤销功能授权，撤权请修改上方授权。</p><el-checkbox-group v-model="r.enabled_menus"><el-checkbox v-for="m in menus" :key="m.key" :value="m.key">{{m.label}}</el-checkbox></el-checkbox-group><el-button @click="saveMenus(r)">保存菜单配置</el-button><el-divider/><el-button @click="r.grants.push({action:'talent.read',scope:'self',scope_id:null})">增加授权</el-button><el-button type="primary" :loading="busy" @click="save(r)">保存全部授权</el-button></el-card><h2>菜单对应授权</h2><p>候选人/档案/解析：人才查看；岗位需求：需求查看；测评：本人或测评相关动作；角色与账号：账号管理；基础资料：基础资料维护；日志：审计查看。管理员不自动拥有业务资料权限。</p></template>

<style scoped>.file-row{display:flex;gap:10px;flex-wrap:wrap}.file-row .el-select{width:240px}.el-card{margin-bottom:16px}</style>
