// 真实后端响应不变，仅注入2秒传输延迟，验证切换会话后的迟到结果隔离。
import {chromium,expect} from '@playwright/test'
import {readFile,writeFile} from 'node:fs/promises'
const report=JSON.parse(await readFile('../data/stage-four/chat-live.json','utf8'))
const credentials=await readFile('../data/local-access.txt','utf8'),password=credentials.match(/^demo.hr \/ demo.employee: (.+)$/m)?.[1]
if(!password)throw new Error('缺少合成账号')
const browser=await chromium.launch({channel:'msedge',headless:true}),context=await browser.newContext(),page=await context.newPage()
try{
 await page.goto('http://127.0.0.1:5173');await page.locator('input').nth(0).fill('demo.hr');await page.locator('input').nth(1).fill(password)
 const auth=page.waitForResponse(r=>r.url().endsWith('/auth/login'));await page.getByRole('button',{name:'登录',exact:true}).click();const token=(await(await auth).json()).data.token
 await expect(page.getByRole('heading',{name:'工作台',exact:true})).toBeVisible()
 async function get(path){const r=await fetch('http://127.0.0.1:8000/api'+path,{headers:{Authorization:'Bearer '+token}});if(!r.ok)throw new Error('读取合成记录失败');return (await r.json()).data}
 let [a,b]=await Promise.all([get('/chat/jobs/'+report.exact_job),get('/chat/jobs/'+report.single_job)])
 const [ca,cb]=await Promise.all([get('/chat/conversations/'+a.conversation_id),get('/chat/conversations/'+b.conversation_id)])
 a=await get('/chat/jobs/'+ca.messages.at(-1).job.id)
 await page.getByRole('button',{name:'档案聊天',exact:true}).click()
 let intercepted=false
 await page.route(`**/api/chat/jobs/${a.id}`,async route=>{intercepted=true;const response=await route.fetch();await new Promise(resolve=>setTimeout(resolve,2000));await route.fulfill({response}).catch(()=>{})})
 async function open(c){await page.locator('.el-select').first().click();await page.getByRole('option',{name:`${new Date(c.created_at*1000).toLocaleString()} · ${c.scope.ids.length}人`,exact:true}).first().click()}
 const delayed=page.waitForRequest(r=>r.url().endsWith('/chat/jobs/'+a.id));await open(ca);await delayed
 await open(cb);await expect(page.getByTestId('chat-job')).toContainText(b.id)
 await new Promise(resolve=>setTimeout(resolve,2500))
 await expect(page.getByTestId('chat-job')).toContainText(b.id);await expect(page.getByTestId('chat-job')).not.toContainText(a.id)
 await expect(page.getByTestId('chat-job')).toContainText('该轮固定范围 1 人')
 if(!intercepted)throw new Error('未实际注入迟到响应')
 await writeFile('../data/stage-four/chat-late-browser.json',JSON.stringify({passed:true,real_backend_responses:true,injected_transport_delay_ms:2000,stale_view_response_ignored:true},null,2))
 console.log('真实响应+明确2秒网络延迟注入：迟到会话结果未串入新范围')
}finally{await browser.close()}
