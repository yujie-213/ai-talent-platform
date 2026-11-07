// 真实Edge交互 + 明确的合成API替身。权限和模型业务由后端另测。
import { chromium, expect } from '@playwright/test'
const browser = await chromium.launch({channel:'msedge',headless:true})
const context = await browser.newContext({viewport:{width:1440,height:1000}})
const page = await context.newPage(), errors=[]
page.on('pageerror',e=>errors.push(e.message))
let pending, requestCount=0, fail=false, saved
const item={id:'synthetic-jd',status:'draft',version:1,active_version:null,versions:[],draft:{
  department_position_id:'dp',title:'人工岗位名称',location:'',salary:null,responsibilities:'',description:'',benefits:'',conditions:null,jd_text:''}}
await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname
  let data
  if(path==='/api/auth/login')data={token:'synthetic-jd-ui-token'}
  else if(path==='/api/auth/me')data={id:'synthetic-user',username:'synthetic.hr',grants:['requirement.read','requirement.write'].map(action=>({action,scope:'global'}))}
  else if(path==='/api/workbench')data={people:{},parse_tasks:{},match_entries:{},assessments:{},definitions:{}}
  else if(path==='/api/catalog')data={departments:[{id:'d',name:'合成研发部'}],positions:[{id:'p',name:'合成工程师'}],department_positions:[{id:'dp',department_id:'d',position_id:'p'}],pools:[]}
  else if(path==='/api/talents'||path==='/api/candidates')data={items:[],total:0}
  else if(path==='/api/imports')data=[]
  else if(path==='/api/requirements/assist') {
    requestCount++
    if(fail)return route.fulfill({status:503,json:{error:{code:'LLM_TIMEOUT',message:'JD辅助暂不可用，原文与已填内容保留'},request_id:'synthetic-timeout'}})
    data=await new Promise(resolve=>{pending=resolve})
  }
  else if(path==='/api/requirements')data={items:[item],total:1}
  else if(path==='/api/requirements/synthetic-jd/matches')data={items:[],total:0}
  else if(path==='/api/requirements/synthetic-jd') {
    if(route.request().method()==='PUT') {saved=route.request().postDataJSON();item.draft=saved;item.version++}
    data=item
  }
  else throw new Error('Unexpected synthetic API route: '+path)
  await route.fulfill({json:{data,request_id:'synthetic-ui'}})
})
const findInput=(label)=>page.locator('.el-form-item').filter({has:page.locator('.el-form-item__label').filter({hasText:label})}).locator('input,textarea').first()
try {
  await page.goto(process.env.FRONTEND_URL||'http://127.0.0.1:5173')
  await page.locator('input').nth(0).fill('synthetic.hr')
  await page.locator('input').nth(1).fill('synthetic-ui-password')
  await page.getByRole('button',{name:'登录',exact:true}).click()
  await page.getByRole('button',{name:'岗位与匹配',exact:true}).click()
  await page.getByRole('cell',{name:'人工岗位名称',exact:true}).click()
  await page.getByRole('tab',{name:'编辑 / JD 辅助',exact:true}).click()
  const jd=page.locator('[data-testid="jd-source"] textarea, textarea[data-testid="jd-source"]')
  const title=findInput(/^需求名称$/), responsibilities=findInput(/^岗位职责$/), location=findInput(/^工作地点/)
  await jd.fill('合成JD：模型岗位名称。北京。开发Python服务。必备Python。')
  await jd.dispatchEvent('paste')
  await expect.poll(()=>requestCount).toBe(1)
  // 推理期间继续输入；迟到结果必须保留人工内容并展示差异。
  await responsibilities.fill('模型处理中人工填写的职责')
  const description=findInput(/^任职要求正文$/)
  await description.fill('临时人工输入')
  await description.fill('')
  pending({suggestions:[
    {field:'title',value:'模型岗位名称',quote:'模型岗位名称',source:'jd'},
    {field:'location',value:'北京',quote:'北京',source:'jd'},
    {field:'responsibilities',value:'开发Python服务',quote:'开发Python服务',source:'jd'},
    {field:'description',value:'必备Python',quote:'必备Python',source:'jd'},
    {field:'conditions.required_skills',value:['Python'],quote:'必备Python',source:'jd'},
  ],issues:[]})
  await expect(location).toHaveValue('北京')
  await expect(title).toHaveValue('人工岗位名称')
  await expect(responsibilities).toHaveValue('模型处理中人工填写的职责')
  await expect(description).toHaveValue('')
  await expect(page.getByTestId('jd-suggestion')).toHaveCount(4)
  await page.getByTestId('jd-suggestion').filter({hasText:'必备技能'}).getByRole('button',{name:'采纳此项'}).click()
  await expect(findInput(/^必备技能/)).toHaveValue('Python')
  await page.getByTestId('jd-suggestion').filter({hasText:'需求名称'}).getByRole('button',{name:'保留当前'}).click()
  await page.getByRole('button',{name:'保存草稿',exact:true}).click()
  await expect.poll(()=>saved?.jd_text).toBe('合成JD：模型岗位名称。北京。开发Python服务。必备Python。')
  expect(saved.title).toBe('人工岗位名称')
  expect(saved.salary).toBeNull()
  fail=true
  await page.getByRole('button',{name:'提取JD / 重试',exact:true}).click()
  await expect(page.getByText('JD辅助暂不可用，原文与已填内容保留（synthetic-timeout）',{exact:true})).toBeVisible()
  await expect(jd).toHaveValue(saved.jd_text)
  await expect(title).toHaveValue(saved.title)
  fail=false
  await page.getByRole('button',{name:'AI辅助完善',exact:true}).click()
  await expect.poll(()=>requestCount).toBe(3)
  pending({suggestions:[{field:'description',value:'AI建议的可维护性要求',quote:'',source:'proposal'}],issues:[]})
  await expect(findInput(/^任职要求正文$/)).toHaveValue('')
  await expect(page.getByTestId('jd-suggestion')).toContainText('AI提议，需确认')
  await page.getByTestId('jd-suggestion').getByRole('button',{name:'采纳此项'}).click()
  await expect(findInput(/^任职要求正文$/)).toHaveValue('AI建议的可维护性要求')
  await expect(page.getByRole('button',{name:'确认生效为新版本'})).toBeDisabled()
  // 关闭表单后到达的模型结果不能重开旧需求。
  await page.getByRole('button',{name:'AI辅助完善',exact:true}).click()
  await expect.poll(()=>requestCount).toBe(4)
  await page.getByRole('button',{name:'← 返回岗位列表',exact:true}).click();await page.getByRole('button',{name:'放弃修改并返回',exact:true}).click()
  pending({suggestions:[{field:'description',value:'迟到建议',quote:'',source:'proposal'}],issues:[]})
  await expect(page.locator('.job-workspace-detail')).toHaveCount(0)
  if(errors.length)throw new Error(errors.join('; '))
  console.log('JD UI passed: automatic paste extraction, safe merge, manual edits during inference, explicit adoption, source save, failure fallback, late response (synthetic API).')
} finally {await context.close();await browser.close()}
