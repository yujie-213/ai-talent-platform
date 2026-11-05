import { chromium, expect } from '@playwright/test'
import { readFile, mkdir } from 'node:fs/promises'
const credentials = await readFile('../data/local-access.txt', 'utf8')
const adminPassword = credentials.match(/^admin: (.+)$/m)?.[1]
const demoPassword = credentials.match(/^demo.hr \/ demo.employee: (.+)$/m)?.[1]
if (!adminPassword || !demoPassword) throw new Error('需要先初始化本机合成账号')
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const failures = []
try {
  for (const [username, password] of [['demo.hr', demoPassword], ['demo.employee', demoPassword], ['admin', adminPassword]]) {
    const context = await browser.newContext({ viewport: {width:1440,height:1000} })
    const page = await context.newPage()
    page.on('pageerror', e => failures.push(e.message))
    await page.goto('http://127.0.0.1:5173')
    await page.locator('input').nth(0).fill(username)
    await page.locator('input').nth(1).fill(password)
    await page.getByRole('button', {name:'登录',exact:true}).click()
    await page.getByRole('heading', {name:'候选人筛选',exact:true}).waitFor()
    await page.getByRole('button', {name:'人才档案',exact:true}).click()
    await page.getByRole('heading', {name:'人才档案',exact:true}).waitFor()
    if (username === 'demo.hr') {
      await page.getByRole('button', {name:'新建人才',exact:true}).click()
      const drawer = page.locator('.el-drawer')
      await drawer.locator('input').nth(0).fill('浏览器合成候选人')
      await drawer.getByRole('button', {name:'添加事实',exact:true}).click()
      await drawer.locator('textarea').fill('合成 Python 技能声明')
      await drawer.getByRole('button', {name:'保存档案',exact:true}).click()
      await drawer.getByRole('heading', {name:'来源文件',exact:true}).waitFor()
      await drawer.getByRole('button', {name:'编辑',exact:true}).click()
      await drawer.locator('input').nth(0).fill('浏览器合成候选人（已编辑）')
      await drawer.getByRole('button', {name:'保存档案',exact:true}).click()
      await drawer.getByRole('heading', {name:'来源文件',exact:true}).waitFor()
      await drawer.getByRole('button', {name:'Close this dialog',exact:true}).click()
      await drawer.waitFor({state:'hidden'})
      await mkdir('../data/screenshots', {recursive:true})
      await page.screenshot({path:'../data/screenshots/hr-workspace.png',fullPage:true})
      // 真实 API + MySQL + Linux Worker：上传合成图片并从创建响应直达任务详情。
      await page.locator('.el-table__body tbody tr').filter({hasText:'浏览器合成候选人（已编辑）'}).first().click()
      await drawer.locator('input[type=file]').setInputFiles({name:'synthetic-browser.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAADElEQVR4nGNgGB4AAADIAAGtQHYiAAAAAElFTkSuQmCC','base64')})
      await drawer.getByRole('button',{name:'上传',exact:true}).click()
      const fileRow = drawer.locator('.file-row').filter({hasText:'synthetic-browser.png'}).last()
      const createdResponse = page.waitForResponse(response => response.url().endsWith('/test-tasks') && response.request().method() === 'POST')
      await fileRow.getByRole('button',{name:'测试成功',exact:true}).click()
      const created = (await (await createdResponse).json()).data
      await expect(drawer).toBeHidden()
      await expect(page.getByTestId('focused-task-id')).toHaveText(created.id)
      await expect(page.getByTestId('task-detail')).toContainText('仅测试任务机制：未执行 OCR 或字段抽取',{timeout:20000})
      await page.screenshot({path:'../data/screenshots/task-detail.png',fullPage:true})
    }
    if (username === 'demo.employee') {
      if (await page.locator('.el-table__body tbody tr').count() !== 1) throw new Error('员工页面范围不正确')
      if (await page.getByRole('button', {name:'新建人才',exact:true}).count()) throw new Error('员工出现未授权入口')
    }
    if (username === 'admin') {
      await page.getByRole('button', {name:'账号管理',exact:true}).click()
      await page.getByRole('heading', {name:'账号管理',exact:true}).waitFor()
      await page.getByRole('button', {name:'基础资料',exact:true}).click()
      await page.getByRole('heading', {name:'基础资料',exact:true}).waitFor()
      await page.getByRole('button', {name:'操作审计',exact:true}).click()
      await page.getByRole('heading', {name:'操作审计',exact:true}).waitFor()
    }
    await context.close()
    console.log(username + ': browser smoke passed')
  }
  if (failures.length) throw new Error('页面异常: ' + failures.join('; '))
} finally {
  await browser.close()
}
