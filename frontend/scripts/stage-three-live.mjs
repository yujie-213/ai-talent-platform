// 真实浏览器→API→MySQL→生成模型与Linux Worker/本地Embedding；无API替身。
import { chromium,expect } from '@playwright/test'
import { readFile,mkdir,writeFile } from 'node:fs/promises'
const base=process.env.FRONTEND_URL||'http://127.0.0.1:5173'
const live=JSON.parse(await readFile('../data/stage-three-evaluation/live.json','utf8'))
const browserTitle='第三阶段页面合成 '+live.tag+' '+Date.now().toString().slice(-6)
const credentials=await readFile('../data/local-access.txt','utf8')
const demoPassword=credentials.match(/^demo.hr \/ demo.employee: (.+)$/m)?.[1]
const adminPassword=credentials.match(/^admin: (.+)$/m)?.[1]
if(!demoPassword||!adminPassword)throw new Error('缺少本机合成账号')
const browser=await chromium.launch({channel:'msedge',headless:true})
const errors=[]
let created,runId
const context=await browser.newContext({viewport:{width:1440,height:1050}})
const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
const formItem=label=>page.locator('.el-form-item').filter({has:page.locator('.el-form-item__label').filter({hasText:label})})
const input=label=>formItem(label).locator('input,textarea').first()
async function firstOption(label){const select=formItem(label).locator('.el-select');await select.click();const controls=await select.getByRole('combobox').getAttribute('aria-controls');if(!controls)throw new Error('下拉框缺少受控列表');await page.locator(`[id="${controls}"]`).getByRole('option').first().click()}
async function option(label,text){await formItem(label).locator('.el-select').first().click();await page.getByRole('option',{name:text,exact:true}).click()}
async function login(p,username,password){await p.goto(base);await p.locator('input').nth(0).fill(username);await p.locator('input').nth(1).fill(password);const response=p.waitForResponse(r=>r.url().endsWith('/auth/login')&&r.request().method()==='POST');await p.getByRole('button',{name:'登录',exact:true}).click();const value=await(await response).json();await p.getByRole('heading',{name:'工作台',exact:true}).waitFor();return value.data.token}
try{
  await login(page,'demo.hr',demoPassword)
  await page.getByRole('button',{name:'岗位需求',exact:true}).click()
  await page.getByRole('button',{name:'新建需求',exact:true}).click()
  await firstOption(/^部门$/)
  await firstOption(/^部门岗位$/)
  const source=`岗位名称：第三阶段页面合成Python工程师。地点：北京。岗位职责：开发Python接口服务。任职要求：必备Python，本科及以上，3年工作经验。薪资：20000-30000人民币元/月。${live.tag}`
  const jd=page.locator('[data-testid="jd-source"] textarea, textarea[data-testid="jd-source"]')
  await jd.fill(source)
  const assistedResponse=page.waitForResponse(r=>r.url().endsWith('/requirements/assist'),{timeout:120000})
  await jd.dispatchEvent('paste')
  const assisted=await(await assistedResponse).json()
  if(!assisted.data?.suggestions.length)throw new Error('真实JD辅助未返回可用建议')
  await expect(page.getByText('JD建议已返回，请核对差异并保存草稿',{exact:true})).toBeVisible()
  await expect(jd).toHaveValue(source)
  // HR核对后明确填写最终条件；模型漏抽可继续手工完成，不伪装模型生成。
  await input(/^需求名称$/).fill(browserTitle)
  await input(/^工作地点/).fill('北京')
  await option(/^薪资$/,'面议')
  await input(/^岗位职责$/).fill('开发Python接口和检索服务')
  await input(/^任职要求正文$/).fill('必备Python，本科及以上，至少3年工作经验；Docker加分')
  await input(/^必备技能/).fill('Python')
  await input(/^加分技能/).fill('Docker')
  await option(/^最低学历$/,'本科')
  await input(/^最低工作年限/).fill('3')
  await input(/^需求名称$/).click()
  const saveResponse=page.waitForResponse(r=>r.url().endsWith('/requirements')&&r.request().method()==='POST')
  await page.getByRole('button',{name:'保存草稿',exact:true}).click()
  created=(await(await saveResponse).json()).data
  if(!created||created.draft.jd_text!==source||created.status!=='draft')throw new Error('草稿/原文保存不正确')
  await expect(page.getByRole('button',{name:'发起新的全范围匹配',exact:true})).toBeDisabled()
  await page.locator('.el-checkbox').filter({hasText:'我已核对已保存草稿'}).click()
  await expect(page.getByRole('checkbox',{name:/我已核对已保存草稿/})).toBeChecked()
  const activeResponse=page.waitForResponse(r=>r.url().endsWith('/activate'))
  await page.getByRole('button',{name:'确认生效为新版本',exact:true}).click()
  const active=(await(await activeResponse).json()).data
  if(active.status!=='active'||active.active_version!==1)throw new Error('生效版本错误')
  await page.getByPlaceholder('额外筛选：技能原文包含').fill(live.tag)
  const matchResponse=page.waitForResponse(r=>r.url().endsWith('/matches')&&r.request().method()==='POST')
  await page.getByRole('button',{name:'发起新的全范围匹配',exact:true}).click()
  const started=(await(await matchResponse).json()).data;runId=started.id
  if(started.total!==5)throw new Error('页面启动的固定范围不正确')
  await expect(page.getByTestId('match-detail').getByRole('heading').first()).toContainText('已完成 / 全部处理完成',{timeout:420000})
  const table=page.getByTestId('match-results')
  await expect(table.locator('.el-table__body tbody tr')).toHaveCount(5)
  await expect(table).toContainText('待核对');await expect(table).toContainText('不满足')
  const declared=table.locator('.el-table__body tbody tr').filter({hasText:'declared'})
  await declared.click()
  await expect(page.getByTestId('match-evidence')).toContainText('必备技能：Python：满足')
  await expect(page.getByTestId('match-evidence')).toContainText('Python、Docker')
  const project=table.locator('.el-table__body tbody tr').filter({hasText:'project'})
  const association=page.waitForResponse(r=>r.url().includes('/talents/')&&r.request().method()==='PUT')
  await project.getByRole('button',{name:'标记应聘',exact:true}).click()
  if((await association).status()!==200)throw new Error('页面显式应聘关联失败')
  await mkdir('../data/screenshots',{recursive:true})
  await page.getByTestId('match-evidence').scrollIntoViewIfNeeded()
  await page.screenshot({path:'../data/screenshots/stage-three-evidence.png',fullPage:true})
  await page.locator('.el-dialog__headerbtn').click()
  await page.getByRole('button',{name:'候选人筛选',exact:true}).click()
  await page.getByText('应聘需求（仅显式关联者）',{exact:true}).click()
  await page.getByRole('option').filter({hasText:browserTitle}).click()
  await expect(page.locator('.el-table__body tbody tr')).toHaveCount(1)
  await expect(page.locator('.el-table__body tbody tr')).toContainText('project')
  await expect(page.locator('.el-table__body tbody tr')).toContainText('满足')
  await expect(page.locator('.el-table__body tbody tr .el-table__cell').last().locator('p')).toHaveCount(1)
  await expect(page.locator('.el-table__body tbody tr')).toContainText(browserTitle)
  await page.screenshot({path:'../data/screenshots/stage-three-candidates.png',fullPage:true})
  for(const [username,password] of [['demo.employee',demoPassword],['admin',adminPassword]]){
    const ctx=await browser.newContext(),p=await ctx.newPage()
    const token=await login(p,username,password)
    await expect(p.getByRole('button',{name:'岗位需求',exact:true})).toHaveCount(0)
    for(const path of [`/requirements/${created.id}`,`/matches/${runId}`,`/matches/${runId}/results`]){
      const response=await ctx.request.get('http://127.0.0.1:8000/api'+path,{headers:{Authorization:'Bearer '+token}})
      if(response.status()!==404)throw new Error('真实页面账号权限隔离失败')
    }
    await ctx.close()
  }
  if(errors.length)throw new Error(errors.join('; '))
  await writeFile('../data/stage-three-evaluation/browser.json',JSON.stringify({requirement_id:created.id,run_id:runId,jd_suggestions:assisted.data.suggestions.length,checks:['real-jd','manual-review','draft-blocks-match','confirmed-version','real-worker','evidence','association','candidate-score','employee-admin-isolation']},null,2))
  console.log('Stage three REAL browser/API/MySQL/model/Worker verification passed, including employee/admin isolation.')
}catch(error){throw error}
finally{await context.close();await browser.close()}
