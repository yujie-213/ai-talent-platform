// 明确合成API：验证发送区域几何位置与真实鼠标可点击，不代表模型效果。
import {chromium,expect} from '@playwright/test'
import {mkdir,writeFile} from 'node:fs/promises'
const browser=await chromium.launch({channel:'msedge',headless:true});await mkdir('../data/ui-composer-fix',{recursive:true});const checks=[]
const dimensions=[{name:'user-150-percent',width:1272,height:596,deviceScaleFactor:1.5},{name:'1366-768',width:1366,height:768},{name:'1440-900',width:1440,height:900},{name:'short-desktop',width:1100,height:500},{name:'narrow',width:800,height:650}]
try{for(const size of dimensions){const context=await browser.newContext({viewport:{width:size.width,height:size.height},deviceScaleFactor:size.deviceScaleFactor||1});const page=await context.newPage();let sent=0,conversation=false;const scope={kind:'selected',ids:['synthetic-person']};const job={id:'synthetic-job',state:'succeeded',run_version:1,error_code:null,scope,coverage:{total:1,processed:1},answer:{text:'合成回答。'.repeat(300),confirmation_required:false,citations:[]},entries:[]};const conv=()=>({id:'synthetic-conversation',version:1,scope,conditions:{},messages:conversation?[{id:'synthetic-message',question:'合成问题',answer:job.answer,job,scope}]:[],created_at:1})
await page.route('**/api/**',async route=>{const path=new URL(route.request().url()).pathname;let data
if(path==='/api/auth/login')data={token:'synthetic-token'}
else if(path==='/api/auth/me')data={id:'synthetic-user',username:'合成布局验证',grants:['talent.read','chat.use'].map(action=>({action,scope:'global'}))}
else if(path==='/api/catalog')data={departments:[],positions:[],department_positions:[],pools:[]}
else if(path==='/api/workbench')data={people:{external:1},definitions:{}}
else if(path==='/api/candidates')data={items:[{id:'synthetic-person',name:'合成缩放验证',kind:'external',quality:'manual',index_state:'ready',tags:[]}],total:1}
else if(path==='/api/imports')data=[]
else if(path==='/api/talents/synthetic-person')data={id:'synthetic-person',name:'合成缩放验证',kind:'external',phone:'',email:'',version:1,facts:[{category:'experience',content:'合成长履历。'.repeat(300)}]}
else if(path==='/api/assessments/assignments')data={items:[],total:0}
else if(path==='/api/chat/conversations'&&route.request().method()==='POST')data=conv()
else if(path==='/api/chat/conversations/synthetic-conversation/messages'){sent++;conversation=true;data=job}
else if(path==='/api/chat/conversations/synthetic-conversation')data=conv()
else if(path==='/api/chat/jobs/synthetic-job')data=job
else if(path.endsWith('/events'))return route.fulfill({contentType:'text/event-stream',body:'event: done\ndata: {}\n\n'})
else throw Error('未定义合成接口 '+path)
await route.fulfill({json:{data}})})
await page.goto('http://127.0.0.1:5173');await page.locator('input').nth(0).fill('synthetic');await page.locator('input').nth(1).fill('synthetic');await page.getByRole('button',{name:'登录',exact:true}).click();await page.locator('nav').getByRole('button',{name:'简历筛选',exact:true}).click();await page.locator('.candidate-table .el-table__body tr').first().locator('.el-checkbox').click();await page.getByRole('button',{name:'比较 / 问答（1）',exact:true}).click();const dialog=page.getByRole('dialog',{name:'人才范围问答'}),send=dialog.getByRole('button',{name:'发送',exact:true}),input=dialog.getByRole('textbox',{name:'向当前范围提问',exact:true});await expect(dialog).toBeVisible()
// 窄屏为上下布局，先将AI面板滚入视口；其内部不能裁切底部发送区。
if(size.width<=1050)await send.scrollIntoViewIfNeeded()
async function assertUnclipped(){await expect(send).toBeInViewport({ratio:1});const result=await send.evaluate(el=>{const r=el.getBoundingClientRect();let parent=el.parentElement;while(parent){const css=getComputedStyle(parent);if(/auto|scroll|hidden|clip/.test(css.overflowY)){const p=parent.getBoundingClientRect();if(r.top<p.top-1||r.bottom>p.bottom+1)return false}parent=parent.parentElement}return true});expect(result,'发送按钮必须完整处于所有滚动/裁切容器内').toBeTruthy();await send.click({trial:true})}
await page.screenshot({path:`../data/ui-composer-fix/${size.name}.png`,animations:'disabled'});await input.fill('合成问题');await assertUnclipped();await send.click();await expect.poll(()=>sent).toBe(1);await expect(dialog.getByTestId('chat-answer')).toContainText('合成回答');await input.fill('合成追问');await assertUnclipped();await send.click();await expect.poll(()=>sent).toBe(2);checks.push(size.name);await context.close()}
await writeFile('../data/ui-composer-fix/result.json',JSON.stringify({passed:true,checks},null,2));console.log('发送区域验证通过：'+checks.join('、')+'；初始/长回答后完整可见，实际鼠标连续发送两次')
}finally{await browser.close()}
