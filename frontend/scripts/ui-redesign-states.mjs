// 合成API替身：只验证前端分页、状态、交互与迟到响应，不代表真实权限/模型能力。
import {chromium,expect} from '@playwright/test'
import {mkdir} from 'node:fs/promises'
const b=await chromium.launch({channel:'msedge',headless:true});const p=await b.newPage({viewport:{width:1366,height:768}});const calls=[],errors=[];let fail=false,delayProfile=false
p.on('pageerror',e=>errors.push(e.message));await mkdir('../data/ui-redesign',{recursive:true})
const people=Array.from({length:42},(_,i)=>({id:'synthetic-'+i,name:i===20?'合成长姓名与长履历压力检查人才'.repeat(3):'合成人才'+i,kind:'external',quality:i===20?'version_conflict':'complete',index_state:'ready',tags:[{category:'experience',content:'合成经历。'.repeat(100),confirmed:false},...Array.from({length:12},(_,j)=>({category:'skill',content:j===0?'合成长技能标签'.repeat(15):'合成技能'+j,confirmed:false}))],requirements:[]}))
await p.route('**/api/**',async route=>{const u=new URL(route.request().url()),path=u.pathname;let data
if(path==='/api/auth/login')data={token:'synthetic-ui'}
else if(path==='/api/auth/me')data={id:'synthetic-user',username:'合成UI测试',grants:['talent.read','talent.write','chat.use'].map(action=>({action,scope:'global'}))}
else if(path==='/api/catalog')data={departments:[],positions:[],department_positions:[],pools:[]}
else if(path==='/api/workbench')data={people:{external:42},definitions:{}}
else if(path==='/api/candidates'){calls.push({offset:u.searchParams.get('offset'),limit:u.searchParams.get('limit')});if(fail)return route.fulfill({status:503,json:{error:{code:'SYNTHETIC_UNAVAILABLE',message:'合成加载失败，请重试'}}});const offset=Number(u.searchParams.get('offset')||0);data={items:people.slice(offset,offset+20),total:42}}
else if(path==='/api/assessments/assignments')data={items:[],total:0}
else if(path==='/api/imports')data=[]
else if(path==='/api/chat/conversations')data={items:[]}
else if(path.startsWith('/api/talents/')){const id=path.split('/').at(-1);if(route.request().method()==='PUT')return route.fulfill({status:409,json:{error:{code:'VERSION_CONFLICT',message:'合成版本冲突，请刷新后核对修改'}}});if(delayProfile&&id==='synthetic-21')await new Promise(r=>setTimeout(r,1500));data={...people.find(t=>t.id===id),phone:'',email:'',version:1,department_id:null,department_position_id:null,owner_id:'synthetic-user',pool_id:null,facts:[{category:'experience',content:'合成完整长履历'.repeat(120),source_type:'file',source_version:1}]}}
else throw Error('未定义的合成接口 '+path)
await route.fulfill({json:{data}})})
try{
await p.goto('http://127.0.0.1:5173');await p.locator('input').nth(0).fill('synthetic');await p.locator('input').nth(1).fill('synthetic');await p.getByRole('button',{name:'登录',exact:true}).click();await p.locator('nav').getByRole('button',{name:'简历筛选',exact:true}).click();await expect(p.locator('.candidate-table .el-table__body tr')).toHaveCount(20)
await p.locator('.el-pagination .btn-next').click();await expect(p.locator('.candidate-table .el-table__body tr').first()).toContainText(people[20].name);expect(calls.at(-1)).toEqual({offset:'20',limit:'20'})
let card=p.locator('.candidate-table .el-table__body tr').first();await card.locator('.el-checkbox').click();await expect(card.locator('.skill-list .el-tag')).toHaveCount(12);await expect(card).toContainText('档案已更新，需核对');expect(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await p.screenshot({path:'../data/ui-redesign/synthetic-long-tags.png'})
await card.getByRole('button',{name:'查看画像',exact:true}).click();let drawer=p.locator('.profile-workspace');await expect(drawer.locator('.profile-document')).toContainText('合成完整长履历');await drawer.getByRole('button',{name:'编辑档案',exact:true}).click();await drawer.locator('input').first().fill('合成未保存修改');await drawer.getByRole('button',{name:'保存档案',exact:true}).click();await expect(p.getByText(/合成版本冲突/)).toBeVisible();await expect(drawer.locator('input').first()).toHaveValue('合成未保存修改');await drawer.getByRole('button',{name:'← 返回筛选结果',exact:true}).click();await p.getByRole('button',{name:'放弃修改并返回',exact:true}).click();await expect(card.getByRole('checkbox')).toBeChecked();await expect(p.locator('.el-pager .is-active')).toHaveText('2')
// 先点乙再点丙，真实网络延迟注入在合成响应上：乙晚到不能覆盖丙。
delayProfile=true;await p.locator('.candidate-table .el-table__body tr').nth(1).getByRole('button',{name:'查看画像',exact:true}).click();await p.locator('.candidate-table .el-table__body tr').nth(2).getByRole('button',{name:'查看画像',exact:true}).click();await expect(drawer.getByRole('heading',{name:people[22].name,exact:true})).toBeVisible();await p.waitForTimeout(1800);await expect(drawer.getByRole('heading',{name:people[22].name,exact:true})).toBeVisible();await drawer.getByRole('button',{name:'← 返回筛选结果',exact:true}).click()
fail=true;await p.getByRole('button',{name:'筛选',exact:true}).click();await expect(p.locator('.el-alert').filter({hasText:'合成加载失败'})).toBeVisible();fail=false;await p.getByRole('button',{name:'重新加载',exact:true}).click();await expect(p.locator('.el-alert').filter({hasText:'合成加载失败'})).toHaveCount(0)
if(errors.length)throw Error(errors.join('\n'));console.log('合成API UI回归通过：20条真实请求分页、42条总数、多选、多标签/长文本、异常标记、409保留输入、详情迟到隔离、返回第2页、失败重试')
}catch(e){await p.screenshot({path:'../data/ui-redesign/states-failure.png',fullPage:true});throw e}finally{await b.close()}
