// 真实Edge/API/MySQL/Worker/生成模型，无API或模型替身；先运行verify-chat-review-live.py。
import {chromium,expect} from '@playwright/test'
import {readFile,writeFile} from 'node:fs/promises'
const sample=JSON.parse(await readFile('../data/stage-four/chat-review-live.json','utf8'))
const credentials=await readFile('../data/local-access.txt','utf8')
const password=credentials.match(/^demo.hr \/ demo.employee: (.+)$/m)?.[1]
if(!password)throw new Error('缺少本机合成账号')
const browser=await chromium.launch({channel:'msedge',headless:true}),errors=[]
try{
 const context=await browser.newContext({viewport:{width:1440,height:1100}}),p=await context.newPage()
 p.on('pageerror',e=>errors.push(e.message))
 await p.goto('http://127.0.0.1:5173');await p.locator('input').nth(0).fill('demo.hr');await p.locator('input').nth(1).fill(password)
 await p.getByRole('button',{name:'登录',exact:true}).click();await expect(p.getByRole('heading',{name:'工作台',exact:true})).toBeVisible()
 await p.getByRole('button',{name:'简历筛选',exact:true}).click()
 await p.getByPlaceholder(/技能关键词/).fill(sample.scope_tag)
 await p.getByRole('button',{name:'查询',exact:true}).click();await expect(p.locator('.candidate-table .el-table__body tr')).toHaveCount(2)
 await p.locator('.el-form-item').filter({has:p.getByText('应聘岗位（已关联）',{exact:true})}).locator('.el-select').click()
 await p.getByRole('option',{name:new RegExp(sample.requirement_title)}).click()
 await expect(p.locator('.candidate-table .el-table__body tr')).toHaveCount(1)
 await expect(p.locator('.candidate-table .el-table__body tr')).toContainText(sample.profiles[0].name)
 // 编辑但未应用的输入不能冒充当前列表筛选；聊天仍继承上次成功请求的全部条件。
 await p.getByLabel('技能关键词',{exact:true}).fill('未应用的合成输入')
 await p.getByRole('button',{name:'按筛选范围问答',exact:true}).click()
 await p.getByRole('dialog',{name:'人才范围问答'}).getByRole('button',{name:/Close this dialog|关闭此对话框/,exact:true}).click()
 await p.locator('nav').getByRole('button',{name:'问答与历史',exact:true}).click()
 const created=p.waitForResponse(r=>r.url().endsWith('/chat/conversations')&&r.request().method()==='POST')
 await p.getByRole('button',{name:'新建会话',exact:true}).click()
 const conv=(await(await created).json()).data
 if(conv.scope.filters.requirement_id!==sample.requirement_id||conv.scope.filters.skill!==sample.scope_tag||conv.scope.ids.length!==1||conv.scope.ids[0]!==sample.profiles[0].id)throw new Error('聊天与当前列表范围不一致')
 await expect(p.getByText('范围筛选条件：',{exact:false})).toContainText('应聘岗位')
 async function send(question){await p.locator('textarea').fill(question);const sent=p.waitForResponse(r=>r.url().endsWith('/messages')&&r.request().method()==='POST');await p.getByRole('button',{name:'发送',exact:true}).click();const job=(await(await sent).json()).data;await expect(p.getByTestId('chat-job')).toContainText(job.id);await expect(p.getByTestId('chat-job')).toContainText('已完成',{timeout:240000});return job.id}
 await send('毕业院校是什么？')
 await expect(p.getByTestId('chat-answer')).toContainText('合成星河大学')
 await expect(p.getByTestId('chat-answer')).not.toContainText('合成青山大学')
 await p.getByRole('button',{name:new RegExp('［1］'+sample.profiles[0].name+' · 核对来源')}).click()
 const dialog=p.getByRole('dialog',{name:'当前权限下核对来源'})
 await expect(dialog).toContainText('合成星河大学');await expect(dialog).toContainText(sample.profiles[0].name)
 await dialog.getByRole('button',{name:/Close this dialog|关闭此对话框/,exact:true}).click();await expect(dialog).toBeHidden()
 await p.screenshot({path:'../data/stage-four/chat-review-single-browser.png',fullPage:true,animations:'disabled'})
 // 比较使用同一聊天入口，打开真实模型已经完成的本轮合成比较，核对具体内容及引用。
 const historyResponse=p.waitForResponse(r=>r.url().includes('/chat/conversations?limit=100'))
 await p.getByRole('button',{name:'刷新当前权限与记录',exact:true}).click()
 const history=(await(await historyResponse).json()).data.items
 const target=history.find(c=>c.id===sample.compare.conversation_id)
 if(!target)throw new Error('缺少真实比较会话')
 const label=`${new Date(target.created_at*1000).toLocaleString()} · 2人`
 const same=history.filter(c=>`${new Date(c.created_at*1000).toLocaleString()} · ${c.scope.ids.length}人`===label)
 await p.locator('.el-select').first().click();await p.getByRole('option',{name:label,exact:true}).nth(same.findIndex(c=>c.id===target.id)).click()
 await expect(p.getByTestId('chat-job')).toContainText(sample.compare.job_id)
 await expect(p.getByTestId('chat-answer')).toContainText('共同点')
 await expect(p.getByTestId('chat-answer')).toContainText('差异')
 await expect(p.getByTestId('chat-answer')).toContainText('合成星河大学')
 await expect(p.getByTestId('chat-answer')).toContainText('合成青山大学')
 await p.screenshot({path:'../data/stage-four/chat-review-compare-browser.png',fullPage:true,animations:'disabled'})
 if(errors.length)throw new Error(errors.join('\n'))
 await writeFile('../data/stage-four/chat-review-browser.json',JSON.stringify({passed:true,requirement_scope_preserved:true,unapplied_form_not_used:true,school_answer_and_citation:true,concrete_comparison:true},null,2))
 console.log('真实页面审查复测通过：岗位筛选1人、范围继承、学校直接回答/来源、具体比较。')
}finally{await browser.close()}
