// 只读真实旧合成结果，验证规则失效提示；不改写历史，不使用API替身。
import {chromium,expect} from '@playwright/test'
import {readFile,mkdir} from 'node:fs/promises'
const old=JSON.parse(await readFile('../data/stage-three-evaluation/browser.json','utf8'))
const credentials=await readFile('../data/local-access.txt','utf8')
const password=credentials.match(/^demo.hr \/ demo.employee: (.+)$/m)?.[1]
if(!password)throw new Error('缺少本机合成账号')
const browser=await chromium.launch({channel:'msedge',headless:true})
const context=await browser.newContext({viewport:{width:1440,height:1050}})
const page=await context.newPage()
try{
  await page.goto(process.env.FRONTEND_URL||'http://127.0.0.1:5173')
  await page.locator('input').nth(0).fill('demo.hr');await page.locator('input').nth(1).fill(password)
  const logged=page.waitForResponse(r=>r.url().endsWith('/auth/login'))
  await page.getByRole('button',{name:'登录',exact:true}).click()
  const token=(await(await logged).json()).data.token
  const headers={Authorization:'Bearer '+token}
  const requirement=await(await context.request.get('http://127.0.0.1:8000/api/requirements/'+old.requirement_id,{headers})).json()
  const historic=await(await context.request.get('http://127.0.0.1:8000/api/matches/'+old.run_id,{headers})).json()
  if(!historic.data.rules_stale)throw new Error('测试需要旧规则合成记录')
  await page.getByRole('heading',{name:'候选人筛选',exact:true}).waitFor()
  await page.getByRole('button',{name:'岗位需求',exact:true}).click()
  await expect(page.locator('.el-table__body tbody tr').first()).toBeVisible()
  const target=page.getByRole('cell',{name:requirement.data.draft.title,exact:true})
  for(let i=0;i<20&&!(await target.count());i++){
    const previous=await page.locator('.el-table__body tbody tr').first().innerText()
    const next=page.locator('.el-pagination .btn-next').first()
    if(await next.isDisabled())break
    await next.click()
    await expect(page.locator('.el-table__body tbody tr').first()).not.toHaveText(previous)
  }
  await target.click()
  await page.getByTestId('match-history').locator('.el-table__body tbody tr').first().click()
  await expect(page.getByText('这是已失效规则生成的历史结果，请发起新匹配；不要将旧分组和分数当成当前结论',{exact:true})).toBeVisible()
  await mkdir('../data/screenshots',{recursive:true})
  await page.getByTestId('match-detail').screenshot({path:'../data/screenshots/year-review-old-rule.png'})
  console.log('Real browser: previous-rule synthetic history is clearly marked stale; historical result retained.')
}finally{await context.close();await browser.close()}
