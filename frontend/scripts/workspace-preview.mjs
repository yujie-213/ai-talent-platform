// 只读浏览器核对当前用户授权的仿真资料，不新增业务记录。
import {chromium,expect} from '@playwright/test'
import {readFile,mkdir,writeFile} from 'node:fs/promises'
const state=JSON.parse(await readFile('../data/workspace/installed.json','utf8'))
const hrLogin=state.primary_hr_login||'zhou.yan'
if(!state.complete)throw Error('资料尚未补齐')
const accounts=Object.fromEntries((await readFile('../data/local-access.txt','utf8')).split(/\r?\n/).filter(s=>s.includes(': ')).map(s=>[s.slice(0,s.indexOf(': ')),s.slice(s.indexOf(': ')+2)]))
const browser=await chromium.launch({channel:'msedge',headless:true}),errors=[],checks=[]
await mkdir('../data/workspace/screens',{recursive:true})
async function login(username){
 const context=await browser.newContext({viewport:{width:1440,height:960}}),page=await context.newPage()
 page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:5173')
 await page.locator('input').nth(0).fill(username);await page.locator('input').nth(1).fill(accounts[username])
 const authenticated=page.waitForResponse(r=>r.url().endsWith('/auth/login')),loaded=page.waitForResponse(r=>r.url().endsWith('/workbench'));await page.getByRole('button',{name:'登录',exact:true}).click()
 const response=await authenticated;expect(response.status()).toBe(200)
 await expect(page.getByRole('heading',{name:/^(工作台|我的工作台|管理工作台)$/})).toBeVisible()
 expect((await loaded).status()).toBe(200)
 if(username!=='admin')await expect(page.locator('.overview-stats strong').first()).toHaveText(username===hrLogin?'48':'1')
 return {context,page,token:(await response.json()).data.token}
}
async function clean(page){expect(await page.locator('body').innerText()).not.toMatch(/合成|测试|演示|示例|demo\.|synthetic/i)}
try{
 const hr=await login(hrLogin),p=hr.page,nav=name=>p.getByRole('navigation',{name:'主导航'}).getByRole('button',{name,exact:true})
 await expect(p.locator('.overview-stats button').filter({hasText:'有效岗位'}).locator('strong')).toHaveText('5')
 await clean(p);await p.screenshot({path:'../data/workspace/screens/工作台.png',fullPage:true})
 await nav('简历筛选').click();await expect(p.locator('.candidate-table .el-table__body tr')).toHaveCount(20);await expect(p.getByText('共 36 人',{exact:true})).toBeVisible();await clean(p)
 await p.screenshot({path:'../data/workspace/screens/候选人.png',fullPage:true})
 await p.getByPlaceholder(/技能关键词/).fill('RAG');await p.getByRole('button',{name:'查询',exact:true}).click()
 const row=p.locator('.candidate-table .el-table__body tr').filter({hasText:'周奕辰'});await row.getByRole('button',{name:'查看画像',exact:true}).click()
 await expect(p.getByRole('heading',{name:'周奕辰',exact:true})).toBeVisible();await clean(p)
 await p.getByRole('tab',{name:'来源文件',exact:true}).click();await expect(p.locator('.file-row').filter({hasText:'周奕辰_AI应用工程师_简历.pdf'})).toBeVisible()
 await p.screenshot({path:'../data/workspace/screens/来源简历.png',fullPage:true})
 await p.getByRole('button',{name:'← 返回筛选结果',exact:true}).click();await nav('岗位与匹配').click()
 await expect(p.getByText('企业知识助手 AI应用工程师',{exact:true}).first()).toBeVisible();await clean(p)
 await p.screenshot({path:'../data/workspace/screens/岗位.png',fullPage:true});checks.push('HR工作台/36位候选人分页/真实来源文件/岗位可用，无旧标签')
 await hr.context.close()
 const employee=await login('chen.yu');await clean(employee.page)
 await employee.page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'我的测评',exact:true}).click()
 await expect(employee.page.getByText('数字化协作与数据安全',{exact:true})).toBeVisible();await expect(employee.page.getByText('AI应用基础与风险识别',{exact:true})).toBeVisible();await clean(employee.page)
 await employee.page.screenshot({path:'../data/workspace/screens/员工测评.png',fullPage:true});checks.push('员工有已完成与待参与测评')
 await employee.context.close()
 const admin=await login('admin');await admin.page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'系统管理',exact:true}).click()
 await expect(admin.page.getByText(hrLogin,{exact:true})).toBeVisible();await clean(admin.page)
 await admin.page.screenshot({path:'../data/workspace/screens/账号.png',fullPage:true});checks.push('管理员账号/角色/绑定为新资料')
 await admin.context.close()
 if(errors.length)throw Error(errors.join('\n'))
 await writeFile('../data/workspace/browser-verification.json',JSON.stringify({passed:true,checks},null,2))
 console.log('Current workspace browser verification passed')
}finally{await browser.close()}
