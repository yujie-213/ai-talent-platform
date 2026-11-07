<script setup lang="ts">
import {computed,ref} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import type {Api} from './api'
interface Item {id:string;name?:string;version:number;enabled:boolean;department_id?:string;position_id?:string}
const props=defineProps<{api:Api;catalog:Record<string,Item[]>}>()
const emit=defineEmits<{changed:[]}>()
const kind=ref('departments'),name=ref(''),department=ref(''),position=ref(''),busy=ref(false)
const names:Record<string,string>={departments:'部门',positions:'公司岗位',department_positions:'部门岗位',pools:'人才库'}
const items=computed(()=>props.catalog[kind.value]||[])
const lookup=(key:string,id?:string)=>props.catalog[key]?.find(i=>i.id===id)?.name||'未找到历史名称'
async function run(fn:()=>Promise<void>){busy.value=true;try{await fn();emit('changed')}catch(e){ElMessage.error((e as Error).message)}finally{busy.value=false}}
async function add(){await run(async()=>{await props.api('/catalog/'+kind.value,'POST',kind.value==='department_positions'?{department_id:department.value,position_id:position.value}:{name:name.value});name.value='';ElMessage.success('基础资料已新增')})}
async function rename(item:Item){let value;try{value=await ElMessageBox.prompt('请输入新名称，历史归属保持不变。','修改'+names[kind.value],{inputValue:item.name,confirmButtonText:'保存',cancelButtonText:'取消',inputValidator:v=>!!v?.trim()||'名称不能为空'})}catch{return}await run(async()=>{await props.api(`/catalog/${kind.value}/${item.id}`,'PATCH',{version:item.version,name:value.value});ElMessage.success('名称已更新')})}
async function toggle(item:Item){if(item.enabled){try{await ElMessageBox.confirm('停用后不再用于新的选择，已有档案和历史归属保留。','停用'+names[kind.value],{confirmButtonText:'确认停用',cancelButtonText:'取消',type:'warning'})}catch{return}}await run(async()=>{await props.api(`/catalog/${kind.value}/${item.id}`,'PATCH',{version:item.version,enabled:!item.enabled});ElMessage.success(item.enabled?'已停用，历史保留':'已启用')})}
</script>
<template>
  <div class="title-row"><h1>基础资料</h1></div><el-tabs v-model="kind" class="workspace-tabs"><el-tab-pane v-for="(label,key) in names" :key="key" :label="label" :name="key"/></el-tabs>
  <el-card><h2>新增{{names[kind]}}</h2><el-form inline @submit.prevent="add"><template v-if="kind==='department_positions'"><el-form-item label="部门"><el-select v-model="department" style="width:200px"><el-option v-for="d in catalog.departments.filter(i=>i.enabled)" :key="d.id" :value="d.id" :label="d.name"/></el-select></el-form-item><el-form-item label="公司岗位"><el-select v-model="position" style="width:200px"><el-option v-for="p in catalog.positions.filter(i=>i.enabled)" :key="p.id" :value="p.id" :label="p.name"/></el-select></el-form-item></template><el-form-item v-else :label="names[kind]+'名称'"><el-input v-model="name"/></el-form-item><el-button type="primary" native-type="submit" :loading="busy">新增</el-button></el-form><p v-if="kind==='department_positions'" class="muted">同一个公司岗位可设置在不同部门；部门岗位用于档案归属与招聘需求。</p></el-card>
  <el-card><el-table :data="items" v-loading="busy"><el-table-column v-if="kind!=='department_positions'" prop="name" :label="names[kind]+'名称'"/><template v-else><el-table-column label="部门"><template #default="{row}">{{lookup('departments',row.department_id)}}</template></el-table-column><el-table-column label="公司岗位"><template #default="{row}">{{lookup('positions',row.position_id)}}</template></el-table-column></template><el-table-column label="状态" width="140"><template #default="{row}"><el-tag :type="row.enabled?'success':'info'">{{row.enabled?'启用':'停用（历史保留）'}}</el-tag></template></el-table-column><el-table-column label="操作" width="190"><template #default="{row}"><el-button v-if="kind!=='department_positions'" link type="primary" @click="rename(row)">修改名称</el-button><el-button link :type="row.enabled?'danger':'primary'" @click="toggle(row)">{{row.enabled?'停用':'启用'}}</el-button></template></el-table-column></el-table><el-empty v-if="!items.length" description="暂无资料，可使用上方表单新增" :image-size="48"/></el-card>
</template>
