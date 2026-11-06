// 真实本机页面/API/Worker/OCR/生成模型；仅上传合成样本。
import { chromium, expect } from '@playwright/test'
import { readFile, mkdir } from 'node:fs/promises'
const credentials = await readFile('../data/local-access.txt','utf8')
const password = credentials.match(/^demo.hr \/ demo.employee: (.+)$/m)?.[1]
if (!password) throw new Error('缺少本机合成账号')
const browser = await chromium.launch({channel:'msedge',headless:true})
try {
  const page = await browser.newPage({viewport:{width:1440,height:1000}})
  const failures=[];page.on('pageerror',e=>failures.push(e.message))
  await page.goto('http://127.0.0.1:5173')
  await page.locator('input').nth(0).fill('demo.hr');await page.locator('input').nth(1).fill(password)
  await page.getByRole('button',{name:'登录',exact:true}).click()
  await page.getByRole('heading',{name:'工作台',exact:true}).waitFor();await page.getByRole('button',{name:'候选人筛选',exact:true}).click();await page.getByRole('heading',{name:'候选人筛选',exact:true}).waitFor()
  await page.locator('input[type=file]').setInputFiles('../data/stage-two-evaluation/synthetic-resume.png')
  const accepted = page.waitForResponse(r=>r.url().includes('/api/imports/') && r.request().method()==='POST')
  await page.getByRole('button',{name:'上传并解析',exact:true}).click()
  const response=await accepted
  if (response.status()!==202) throw new Error('真实导入未被接受')
  const task=(await response.json()).data
  await page.getByRole('button',{name:'进度与结果',exact:true}).click()
  const detail=page.getByTestId('task-detail')
  await expect(detail).toContainText(task.id)
  await expect(detail).toContainText('状态：成功',{timeout:240000})
  await expect(detail).toContainText('原文依据')
  await expect(detail).toContainText('Python')
  if (await detail.getByRole('button',{name:'排除重复，按新人入档',exact:true}).isVisible()) { await detail.getByRole('button',{name:'排除重复，按新人入档',exact:true}).click(); await expect(detail).not.toContainText('疑似重复人才：') }
  await detail.getByRole('button',{name:'核对当前人才档案',exact:true}).click()
  const drawer=page.locator('.el-drawer')
  await expect(drawer.locator('input').first()).toHaveValue('李测试')
  await drawer.getByRole('button',{name:'编辑',exact:true}).click()
  await drawer.locator('input').first().fill('页面合成候选人（人工确认）')
  await drawer.getByRole('button',{name:'保存档案',exact:true}).click()
  await expect(drawer.getByRole('button',{name:'保存档案',exact:true})).not.toBeVisible()
  await drawer.getByRole('button',{name:'Close this dialog',exact:true}).click()
  await drawer.waitFor({state:'hidden'})
  await page.getByRole('button',{name:'候选人筛选',exact:true}).click()
  await page.getByPlaceholder('技能包含',{exact:true}).fill('Python')
  await page.getByRole('button',{name:'筛选',exact:true}).click()
  await expect(page.locator('.el-table')).toContainText('页面合成候选人（人工确认）')
  // 再次解析同一原文件，真实验证人工确认姓名不会被抽取覆盖。
  await page.getByRole('button',{name:'任务记录',exact:true}).click()
  await detail.getByRole('button',{name:'核对当前人才档案',exact:true}).click()
  const reparsed=page.waitForResponse(r=>r.url().endsWith('/parse') && r.request().method()==='POST')
  await drawer.getByRole('button',{name:'解析简历',exact:true}).click()
  const second=(await (await reparsed).json()).data
  await expect(detail).toContainText(second.id)
  await expect(detail).toContainText('状态：成功',{timeout:240000})
  await detail.getByRole('button',{name:'核对当前人才档案',exact:true}).click()
  await expect(drawer.locator('input').first()).toHaveValue('页面合成候选人（人工确认）')
  await drawer.getByRole('button',{name:'Close this dialog',exact:true}).click()
  await drawer.waitFor({state:'hidden'})
  await page.getByRole('button',{name:'候选人筛选',exact:true}).click()
  await mkdir('../data/screenshots',{recursive:true})
  await page.screenshot({path:'../data/screenshots/stage2-candidate.png',fullPage:true})
  if(failures.length) throw new Error(failures.join('\n'))
  console.log('真实上传 → OCR/模型 → 任务证据 → 入档 → 人工确认 → 筛选通过；task',task.id)
} finally { await browser.close() }
