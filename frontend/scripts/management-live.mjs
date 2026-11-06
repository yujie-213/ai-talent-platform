// 真实页面创建合成角色/账号、配置菜单与绑定；finally禁用并解绑合成账号。
import {chromium,expect} from '@playwright/test'
import {readFile,mkdir,writeFile} from 'node:fs/promises'
import {randomUUID} from 'node:crypto'
const access=await readFile('../data/local-access.txt','utf8'),password=access.match(/^admin: (.+)$/m)?.[1]
const report=JSON.parse(await readFile('../data/stage-four/chat-live.json','utf8'))
if(!password)throw new Error('缺少既有管理员账号')
const browser=await chromium.launch({channel:'msedge',headless:true}),context=await browser.newContext({viewport:{width:1600,height:1100}}),page=await context.newPage()
let adminToken,userId,newToken,roleId
const tag=randomUUID().slice(0,8),roleName='合成页面角色-'+tag,username='synthetic.stage4.'+tag,newPassword=randomUUID()+'-Synthetic'
async function api(path,method='GET',body,token=adminToken){const response=await fetch('http://127.0.0.1:8000/api'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const json=await response.json();if(!response.ok)throw new Error(`HTTP ${response.status} ${json.error?.code}`);return json.data}
async function login(p,name,pw){await p.goto('http://127.0.0.1:5173');await p.locator('input').nth(0).fill(name);await p.locator('input').nth(1).fill(pw);const auth=p.waitForResponse(r=>r.url().endsWith('/auth/login'));await p.getByRole('button',{name:'登录',exact:true}).click();const data=(await(await auth).json()).data;await expect(p.getByRole('heading',{name:'工作台',exact:true})).toBeVisible();return data.token}
async function accountRow(){let row=page.locator('.el-table__row').filter({hasText:username});for(let i=0;i<50 && !(await row.count());i++){const next=page.locator('.el-pagination .btn-next');if(await next.isDisabled())break;await next.click();await page.waitForResponse(r=>r.url().includes('/admin/user-page'))}await expect(row).toBeVisible();return row}
try{
 adminToken=await login(page,'admin',password)
 await page.getByRole('button',{name:'角色与菜单权限',exact:true}).click()
 await page.getByPlaceholder('新角色名称',{exact:true}).fill(roleName)
 const createdRole=page.waitForResponse(r=>r.url().endsWith('/admin/roles')&&r.request().method()==='POST')
 await page.getByRole('button',{name:'创建角色',exact:true}).click();roleId=(await(await createdRole).json()).data.id
 let card=page.locator('.el-card').filter({has:page.getByRole('heading',{name:new RegExp(roleName)})})
 await expect(card).toBeVisible();await card.getByRole('button',{name:'增加授权',exact:true}).click()
 const grantSaved=page.waitForResponse(r=>r.url().endsWith(`/roles/${roleId}/grants`)&&r.request().method()==='PUT')
 await card.getByRole('button',{name:'保存全部授权',exact:true}).click();if((await grantSaved).status()!==200)throw new Error('页面授权保存失败')
 await expect(card.getByRole('heading',{name:new RegExp(roleName)})).toContainText('v2')
 await card.getByText('档案聊天',{exact:true}).click()
 const menuSaved=page.waitForResponse(r=>r.url().endsWith(`/roles/${roleId}/menus`)&&r.request().method()==='PUT')
 await card.getByRole('button',{name:'保存菜单配置',exact:true}).click();if((await menuSaved).status()!==200)throw new Error('页面菜单保存失败')
 const role=(await api('/admin/roles')).find(r=>r.id===roleId)
 if(!role.grants.some(g=>g.action==='talent.read'&&g.scope==='self')||role.enabled_menus.includes('chat'))throw new Error('角色/菜单未真实保存')
 await page.getByRole('button',{name:'账号管理',exact:true}).click()
 await page.locator('.el-form-item').filter({has:page.locator('.el-form-item__label').filter({hasText:'新账号'})}).locator('input').fill(username)
 await page.locator('.el-form-item').filter({has:page.locator('.el-form-item__label').filter({hasText:'初始密码'})}).locator('input').fill(newPassword)
 const createdUser=page.waitForResponse(r=>r.url().endsWith('/admin/users')&&r.request().method()==='POST')
 await page.getByRole('button',{name:'创建',exact:true}).click();userId=(await(await createdUser).json()).data.id
 const row=await accountRow()
 await row.locator('.el-select').nth(0).click();await page.getByRole('option',{name:roleName,exact:true}).click()
 await page.getByRole('heading',{name:'账号管理',exact:true}).click()
 const binding=row.locator('.el-select').nth(2);await binding.click();await binding.locator('input').fill(report.profiles[0].name)
 await page.getByRole('option',{name:`${report.profiles[0].name} · 外部 · ${report.profiles[0].id.slice(0,8)}`,exact:true}).click()
 const saved=page.waitForResponse(r=>r.url().endsWith('/admin/users/'+userId)&&r.request().method()==='PATCH')
 await row.getByRole('button',{name:'保存',exact:true}).click();if((await saved).status()!==200)throw new Error('页面角色/绑定保存失败')
 await expect(row).toContainText(report.profiles[0].name)
 const employeeContext=await browser.newContext(),employeePage=await employeeContext.newPage()
 newToken=await login(employeePage,username,newPassword)
 const own=await api('/talents','GET',undefined,newToken)
 if(own.total!==1||own.items[0].id!==report.profiles[0].id)throw new Error('新角色本人范围不正确')
 const forbidden=await fetch('http://127.0.0.1:8000/api/talents/'+report.profiles[1].id,{headers:{Authorization:'Bearer '+newToken}})
 if(forbidden.status!==404)throw new Error('新角色越权')
 await expect(employeePage.getByRole('button',{name:'档案聊天',exact:true})).toHaveCount(0)
 await employeeContext.close()
 await mkdir('../data/stage-four',{recursive:true});await row.screenshot({path:'../data/stage-four/account-binding-browser.png'})
 await writeFile('../data/stage-four/management-browser.json',JSON.stringify({passed:true,role_id:roleId,user_id:userId,checks:['页面创建角色','页面保存本人范围','页面配置菜单','页面创建账号','页面设置角色及按姓名绑定','新角色本人范围与跨人拒绝','finally禁用解绑']},null,2))
 console.log('真实角色、菜单、账号与绑定操作闭环通过')
}finally{
 if(userId&&adminToken){let user;for(let offset=0;offset<5000;offset+=100){const data=await api(`/admin/user-page?offset=${offset}&limit=100`);user=data.items.find(u=>u.id===userId);if(user||offset+100>=data.total)break}if(!user)throw new Error('未找到合成账号用于清理');await api('/admin/users/'+userId,'PATCH',{version:user.version,enabled:false,role_ids:user.role_ids,talent_id:null,department_id:null});if(newToken){const revoked=await fetch('http://127.0.0.1:8000/api/auth/me',{headers:{Authorization:'Bearer '+newToken}});if(revoked.status!==401)throw new Error('禁用后旧令牌未拒绝')}}
 await browser.close()
}
