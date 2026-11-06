// 真实Edge/API/MySQL/Worker/模型，无API替身。使用前置合成效果报告。
import {chromium,expect} from '@playwright/test'
import {readFile,mkdir,writeFile} from 'node:fs/promises'
const report=JSON.parse(await readFile('../data/stage-four/chat-live.json','utf8'))
const access=await readFile('../data/local-access.txt','utf8')
const password=access.match(/^demo.hr \/ demo.employee: (.+)$/m)?.[1]
const adminPassword=access.match(/^admin: (.+)$/m)?.[1]
if(!password||!adminPassword)throw new Error('缺少本机合成账号')
const browser=await chromium.launch({channel:'msedge',headless:true}),errors=[]
async function login(name,pw){const ctx=await browser.newContext({viewport:{width:1440,height:1100}});const p=await ctx.newPage();p.on('pageerror',e=>errors.push(e.message));await p.goto('http://127.0.0.1:5173');await p.locator('input').nth(0).fill(name);await p.locator('input').nth(1).fill(pw);const auth=p.waitForResponse(r=>r.url().endsWith('/auth/login'));await p.getByRole('button',{name:'登录',exact:true}).click();const token=(await(await auth).json()).data.token;await expect(p.getByRole('heading',{name:'工作台',exact:true})).toBeVisible();return {ctx,p,token}}
try{
 const {ctx,p,token}=await login('demo.hr',password)
 // 只在三份自有合成档案增加页面筛选标签，验证当前档案/勾选/筛选三种上下文。
 const scopeTag='合成页面筛选专用-'+report.profiles[0].id.slice(0,8)
 for(const profile of report.profiles){const r=await ctx.request.get('http://127.0.0.1:8000/api/talents/'+profile.id,{headers:{Authorization:'Bearer '+token}});const t=(await r.json()).data;if(!t.facts.some(f=>f.content===scopeTag)){const body={};for(const k of ['kind','name','phone','email','department_id','department_position_id','owner_id','pool_id','version'])body[k]=t[k];body.facts=[...t.facts.map(f=>({category:f.category,content:f.content})),{category:'skill',content:scopeTag}];const saved=await ctx.request.put('http://127.0.0.1:8000/api/talents/'+profile.id,{headers:{Authorization:'Bearer '+token},data:body});if(saved.status()!==200)throw new Error('合成筛选标签保存失败')}}
 async function candidates(){await p.getByRole('button',{name:'候选人筛选',exact:true}).click();await p.getByPlaceholder('技能包含',{exact:true}).fill(scopeTag);await p.getByRole('button',{name:'筛选',exact:true}).click();await expect(p.getByTestId('candidate-card')).toHaveCount(3)}
 async function createScope(expectedKind,expectedCount,detail=false){const panel=p.getByRole('dialog',{name:detail?'人才详情':'人才范围问答'});const response=p.waitForResponse(r=>r.url().endsWith('/chat/conversations')&&r.request().method()==='POST');await panel.locator('textarea').fill('这些人有多少？');await panel.getByRole('button',{name:'发送',exact:true}).click();const scope=(await(await response).json()).data.scope;if(scope.kind!==expectedKind||scope.ids.length!==expectedCount)throw new Error('页面上下文范围不一致');await expect(panel.getByTestId('chat-job')).toBeVisible();await panel.getByRole('button',{name:/Close this dialog|关闭此对话框/,exact:true}).click()}
 await candidates();await p.getByTestId('candidate-card').filter({hasText:report.profiles[0].name}).locator('.el-checkbox').click();await p.getByRole('button',{name:'与勾选人才聊天（1）',exact:true}).click();await createScope('selected',1)
 await candidates();await p.getByRole('button',{name:'按当前筛选范围聊天',exact:true}).click();await createScope('filtered',3)
 await candidates();await p.getByTestId('candidate-card').filter({hasText:report.profiles[0].name}).getByRole('button',{name:'查看档案',exact:true}).click();await createScope('selected',1,true)
 await p.getByRole('button',{name:'档案聊天',exact:true}).click()
 await expect(p.getByRole('heading',{name:'档案聊天',exact:true})).toBeVisible()
 // 页面历史读取真实完整语义结果，逐人展开并点击受控引用。
 await p.locator('.el-select').first().click()
 await p.locator(`.el-select-dropdown__item`).filter({hasText:'3人'}).first().waitFor()
 // 历史按ID选择，避免依赖相同分钟的多个合成会话标签。
 await p.keyboard.press('Escape')
 const options=await p.locator('.el-select').first().locator('input').count()
 const history=await(await ctx.request.get('http://127.0.0.1:8000/api/chat/conversations?limit=100',{headers:{Authorization:'Bearer '+token}})).json()
 const selected=history.data.items.find(c=>c.id===report.conversation_id)
 if(!selected)throw new Error('缺少真实历史会话')
 const label=`${new Date(selected.created_at*1000).toLocaleString()} · 3人`
 await p.locator('.el-select').first().click()
 const matches=p.getByRole('option',{name:label,exact:true})
 const same=history.data.items.filter(c=>`${new Date(c.created_at*1000).toLocaleString()} · ${c.scope.ids.length}人`===label)
 await matches.nth(same.findIndex(c=>c.id===report.conversation_id)).click()
 await expect(p.getByTestId('chat-job')).toBeVisible();if(!(await p.getByTestId('chat-job').innerText()).includes(report.job_id))await p.locator(`[data-job-id="${report.job_id}"]`).getByRole('button',{name:'查看该轮进度、逐人证据与版本',exact:true}).click()
 await expect(p.getByTestId('chat-job')).toContainText(report.job_id)
 await expect(p.getByTestId('chat-answer')).toContainText('指定范围 3 人')
 await expect(p.getByTestId('chat-job')).toContainText('覆盖进度 3 / 3')
 await p.getByRole('button',{name:new RegExp(report.profiles[0].name)}).first().click()
 await p.getByRole('button',{name:/核对人工事实/}).first().click()
 await expect(p.getByRole('dialog',{name:'当前权限下核对来源'})).toContainText(report.profiles[0].name)
 await p.getByRole('dialog',{name:'当前权限下核对来源'}).getByRole('button',{name:/Close this dialog|关闭此对话框/,exact:true}).click()
 // 在同一入口自然语言发起真实新任务，观察SSE，无需切换技术模式。
 let streamSeen=false;p.on('response',r=>{if(r.url().includes('/events?')&&r.headers()['content-type']?.includes('text/event-stream'))streamSeen=true})
 await p.locator('textarea').fill('这些人有多少？只统计当前三个人，不扩大范围，不要求语义条件。')
 const sent=p.waitForResponse(r=>r.url().endsWith('/messages')&&r.request().method()==='POST')
 await p.getByRole('button',{name:'发送',exact:true}).click();const task=(await(await sent).json()).data
 await expect(p.getByTestId('chat-job')).toContainText(task.id)
 await expect(p.getByTestId('chat-job')).toContainText('已完成',{timeout:180000});if(await p.getByRole('button',{name:'确认上述范围与判据',exact:true}).count()){await p.getByRole('button',{name:'确认上述范围与判据',exact:true}).click()}
 await expect(p.getByTestId('chat-answer')).toContainText('完整授权快照范围 3 人',{timeout:180000})
 if(!streamSeen)throw new Error('未观察到真实SSE响应')
 await mkdir('../data/stage-four',{recursive:true});await p.screenshot({path:'../data/stage-four/chat-browser.png',fullPage:true})
 const fileReport=JSON.parse(await readFile('../data/stage-four/chat-file-live.json','utf8'))
 const fileConversation=(await(await ctx.request.get('http://127.0.0.1:8000/api/chat/conversations/'+fileReport.conversation_id,{headers:{Authorization:'Bearer '+token}})).json()).data
 await p.getByRole('button',{name:'刷新当前权限与记录',exact:true}).click()
 await p.locator('.el-select').first().click();await p.getByRole('option',{name:`${new Date(fileConversation.created_at*1000).toLocaleString()} · 1人`,exact:true}).first().click()
 await expect(p.getByTestId('chat-job')).toContainText(fileReport.job_id)
 await p.locator('.el-collapse-item__header').first().click();await p.getByRole('button',{name:/核对来源记录/}).first().click()
 const fileDialog=p.getByRole('dialog',{name:'当前权限下核对来源'});await expect(fileDialog).toContainText(fileReport.file_name)
 const downloaded=p.waitForEvent('download');await fileDialog.getByRole('button',{name:'下载原文件核对',exact:true}).click();const download=await downloaded
 if(download.suggestedFilename()!==fileReport.file_name)throw new Error('原文件名称不匹配')
 await download.saveAs('../data/stage-four/from-chat-source.docx')
 await p.screenshot({path:'../data/stage-four/chat-file-browser.png',fullPage:true,animations:'disabled'})
 await fileDialog.getByRole('button',{name:/Close this dialog|关闭此对话框/,exact:true}).click()
 console.log('真实聊天及原文件下载断言通过，切换管理员')
 const adm=await login('admin',adminPassword)
 await expect(adm.p.getByRole('button',{name:'档案聊天',exact:true})).toHaveCount(0)
 await adm.p.getByRole('button',{name:'操作审计',exact:true}).click()
 await expect(adm.p.getByRole('heading',{name:'操作审计与 AI 调用记录',exact:true})).toBeVisible()
 await adm.p.getByText('AI 调用记录',{exact:true}).click()
 await adm.p.getByPlaceholder('动作/调用类型包含',{exact:true}).fill('chat.');await adm.p.getByRole('button',{name:'查询',exact:true}).click()
 await expect(adm.p.locator('.el-table__body')).toContainText('chat.')
 await adm.p.screenshot({path:'../data/stage-four/ai-calls-browser.png',fullPage:true})
 await adm.p.getByRole('button',{name:'账号管理',exact:true}).click()
 await expect(adm.p.getByText('账号部门',{exact:true})).toBeVisible()
 await expect(adm.p.locator('.el-pagination')).toBeVisible()
 await adm.p.getByRole('button',{name:'角色与菜单权限',exact:true}).click()
 await expect(adm.p.getByText('菜单显示范围',{exact:true}).first()).toBeVisible()
 await adm.ctx.close()
 await ctx.close()
 if(errors.length)throw new Error(errors.join('\n'))
 await writeFile('../data/stage-four/chat-browser.json',JSON.stringify({passed:true,checks:['当前档案/勾选/筛选范围','真实历史语义覆盖','逐人引用','真实DOCX源段落/原文件下载','新问题SSE','管理员隔离','AI日志页','账号部门绑定及分页','菜单配置页']},null,2))
 console.log('真实聊天、SSE、引用及管理页面闭环通过')
}finally{await browser.close()}
