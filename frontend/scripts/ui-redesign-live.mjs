// 真实Edge/API/已有合成数据；不修改原业务档案。聊天调用真实Worker与模型。
import {chromium,expect} from '@playwright/test'
import {readFile,mkdir,writeFile} from 'node:fs/promises'
const access=await readFile('../data/local-access.txt','utf8'),password=access.match(/^demo.hr \/ demo.employee: (.+)$/m)?.[1]
const sample=JSON.parse(await readFile('../data/stage-four/chat-review-live.json','utf8'))
const browser=await chromium.launch({channel:'msedge',headless:true}),errors=[],checks=[]
await mkdir('../data/ui-redesign',{recursive:true})
async function login(user='demo.hr',width=1440,height=900){const p=await browser.newPage({viewport:{width,height}});p.on('pageerror',e=>errors.push(e.message));await p.goto('http://127.0.0.1:5173');await p.locator('input').nth(0).fill(user);await p.locator('input').nth(1).fill(password);await p.getByRole('button',{name:'登录',exact:true}).click();await expect(p.getByRole('heading',{name:'工作台',exact:true})).toBeVisible();return p}
try{
 const p=await login();await p.locator('nav').getByRole('button',{name:'候选人筛选',exact:true}).click()
 await p.getByPlaceholder('技能包含',{exact:true}).fill(sample.scope_tag);await p.getByRole('button',{name:'筛选',exact:true}).click();await expect(p.getByTestId('candidate-card')).toHaveCount(2)
 await p.getByText('应聘需求（仅显式关联者）',{exact:true}).click();await p.getByRole('option',{name:new RegExp(sample.requirement_title)}).click();await expect(p.getByTestId('candidate-card')).toHaveCount(1)
 await p.screenshot({path:'../data/ui-redesign/cards-1440.png',fullPage:true})
 const card=p.getByTestId('candidate-card');await card.locator('.el-checkbox').click();await expect(card.getByRole('checkbox')).toBeChecked();await expect(card).toHaveClass(/is-selected/)
 await p.getByPlaceholder('技能包含',{exact:true}).fill('未应用的合成输入')
 await p.getByRole('button',{name:'按当前筛选范围聊天',exact:true}).click()
 let panel=p.getByRole('dialog',{name:'人才范围问答'});await panel.locator('textarea').fill('毕业院校是什么？')
 const sent=p.waitForResponse(r=>r.url().endsWith('/chat/conversations')&&r.request().method()==='POST');await panel.getByRole('button',{name:'发送',exact:true}).click();const conv=(await(await sent).json()).data
 expect(conv.scope.filters.requirement_id).toBe(sample.requirement_id);expect(conv.scope.filters.skill).toBe(sample.scope_tag);expect(conv.scope.ids).toEqual([sample.profiles[0].id]);await expect(panel.getByTestId('chat-job')).toContainText('已完成',{timeout:240000});checks.push('requirement_id及未应用输入隔离，列表1=真实会话1')
 await panel.getByRole('button',{name:/Close this dialog|关闭此对话框/,exact:true}).click();await expect(p.getByPlaceholder('技能包含',{exact:true})).toHaveValue('未应用的合成输入')
 await card.getByRole('button',{name:'查看档案',exact:true}).click();panel=p.getByRole('dialog',{name:'人才详情'});await expect(panel.getByRole('heading',{name:sample.profiles[0].name,exact:true})).toBeVisible()
 await panel.locator('textarea').fill('毕业院校是什么？');await panel.getByRole('button',{name:'发送',exact:true}).click();await expect(panel.getByTestId('chat-job')).toContainText('已完成',{timeout:240000});await expect(panel.getByTestId('chat-answer')).toContainText('合成星河大学');await expect(panel.getByTestId('chat-answer')).not.toContainText('合成青山大学')
 await panel.getByRole('button',{name:/［1］.*核对来源/}).click();const citation=p.getByRole('dialog',{name:'当前权限下核对来源'});await expect(citation).toContainText('合成星河大学');await citation.getByRole('button',{name:/Close this dialog|关闭此对话框/,exact:true}).click()
 await panel.screenshot({path:'../data/ui-redesign/profile-ai-1440.png'});checks.push('详情首次发送建会话、真实学校答案和引用核对')
 await panel.getByRole('button',{name:'收起 AI 助手',exact:true}).click();await expect(panel.locator('.profile-ai')).toBeHidden();await panel.getByRole('button',{name:'打开 AI 助手',exact:true}).click();await expect(panel.getByTestId('chat-answer')).toContainText('合成星河大学')
 for(const [width,height] of [[1366,768],[800,900]]){await p.setViewportSize({width,height});await expect(panel.getByRole('button',{name:'发送',exact:true})).toBeVisible();expect(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await panel.screenshot({path:`../data/ui-redesign/profile-ai-${width}.png`})}checks.push('AI收起保留会话、1366/800宽无全页溢出')
 await panel.getByRole('button',{name:/Close this dialog|关闭此对话框/,exact:true}).click();await expect(card).toHaveClass(/is-selected/);await expect(p.getByPlaceholder('技能包含',{exact:true})).toHaveValue('未应用的合成输入');checks.push('关闭档案保留筛选与多选')
 await p.setViewportSize({width:1440,height:900});await p.locator('nav').getByRole('button',{name:'岗位需求',exact:true}).click();await expect(p.getByRole('heading',{name:'岗位需求',exact:true})).toBeVisible();await p.locator('.title-row').screenshot({path:'../data/ui-redesign/requirements.png'})
 const employee=await login('demo.employee');await expect(employee.locator('nav').getByRole('button',{name:'账号管理',exact:true})).toHaveCount(0);await expect(employee.locator('nav').getByRole('button',{name:'档案聊天',exact:true})).toHaveCount(0);checks.push('员工没有管理/聊天入口')
 if(errors.length)throw Error(errors.join('\n'));await writeFile('../data/ui-redesign/live.json',JSON.stringify({passed:true,checks},null,2));console.log(checks.join('\n'))
}catch(error){for(const context of browser.contexts())for(const page of context.pages())await page.screenshot({path:'../data/ui-redesign/failure.png',fullPage:true});throw error}finally{await browser.close()}
