// 只读真实业务验证，不写入资料，不输出凭据。
import {chromium,expect} from '@playwright/test'
import {readFile,mkdir} from 'node:fs/promises'
const state=JSON.parse(await readFile('../data/workspace/installed.json','utf8')),user=state.primary_hr_login||'zhou.yan'
const accounts=Object.fromEntries((await readFile('../data/local-access.txt','utf8')).split(/\r?\n/).filter(s=>s.includes(': ')).map(s=>{const i=s.indexOf(': ');return [s.slice(0,i),s.slice(i+2)]}))
const b=await chromium.launch({channel:'msedge',headless:true}),p=await b.newPage({viewport:{width:1440,height:960}}),errors=[]
p.on('pageerror',e=>errors.push(e.message));await mkdir('../data/filter-task-review',{recursive:true})
try{
await p.goto('http://127.0.0.1:5173');await p.locator('input').nth(0).fill(user);await p.locator('input').nth(1).fill(accounts[user])
const login=p.waitForResponse(r=>r.url().endsWith('/auth/login'));await p.getByRole('button',{name:'登录',exact:true}).click();const token=(await (await login).json()).data.token,headers={Authorization:'Bearer '+token}
const nav=name=>p.getByRole('navigation',{name:'主导航'}).getByRole('button',{name,exact:true})
await expect(nav('问答与历史')).toHaveCount(0);await nav('人才画像').click()
const search=p.getByRole('textbox',{name:'姓名',exact:true});await expect(search).toBeVisible()
const found=p.waitForResponse(r=>r.url().includes('/candidates?')&&new URL(r.url()).searchParams.get('name')==='杨');await search.fill('杨');const data=(await (await found).json()).data
expect(data.total).toBeGreaterThan(0);expect(data.items.every(t=>t.name.includes('杨'))).toBeTruthy();await expect(p.locator('.candidate-table .el-table__body tr')).toHaveCount(data.items.length)
await expect(p.getByRole('button',{name:'查询',exact:true})).toHaveCount(0);await expect(p.locator('.filter-chips')).toContainText('姓名含');await p.waitForTimeout(350);await p.screenshot({path:'../data/filter-task-review/profile.png',fullPage:true})
await p.getByRole('button',{name:'重置',exact:true}).click();await expect(search).toHaveValue('')
await nav('简历筛选').click();await expect(p.getByRole('button',{name:'全部岗位',exact:true})).toBeVisible()
await expect(p.locator('.ov-card').first()).not.toContainText('外部')
const summary=(await (await p.request.get('http://127.0.0.1:5173/api/workbench',{headers})).json()).data
await expect(p.locator('.ov-card').first().locator('.ov-value')).toHaveText(String(Object.values(summary.parse_tasks).reduce((a,v)=>a+v,0)))
await p.getByRole('button',{name:'解析历史',exact:true}).click();await expect(p.locator('.batch-list-card')).toBeVisible();await p.getByRole('button',{name:'返回筛选',exact:true}).click();await expect(p.getByRole('button',{name:'全部岗位',exact:true})).toBeVisible();await p.screenshot({path:'../data/filter-task-review/candidates.png',fullPage:true})
await nav('解析任务').click();await expect(p.getByText('解析时间',{exact:true})).toBeVisible()
const tasks=(await (await p.request.get('http://127.0.0.1:5173/api/tasks?limit=100',{headers})).json()).data.items
expect(tasks.every((t,i)=>!i||(tasks[i-1].parsed_at||0)>=(t.parsed_at||0))).toBeTruthy();expect(tasks.some(t=>t.file_name)).toBeTruthy();await p.screenshot({path:'../data/filter-task-review/tasks.png',fullPage:true})
await nav('人才画像').click();for(const width of [1280,800,390]){await p.setViewportSize({width,height:900});expect(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()}
expect(errors).toEqual([]);console.log('PASS real name search/reset/history/count/task order; widths 1440/1280/800/390; no page errors')
}finally{await b.close()}
