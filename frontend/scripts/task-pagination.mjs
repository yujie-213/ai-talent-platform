// UI 回归使用合成 API 替身；真实权限、分页与计数由后端数据库测试验证。
import { chromium, expect } from '@playwright/test'

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage()
const errors = []
page.on('pageerror', error => errors.push(error.message))
const tasks = Array.from({ length: 61 }, (_, i) => ({id: `synthetic-task-${String(i).padStart(3, '0')}`, state: 'succeeded', run_version: 1, result: '合成机制测试结果', error_code: null, attempts: []}))
const talent = {id:'synthetic-talent',kind:'external',name:'分页合成人才',phone:'',email:'',department_id:null,department_position_id:null,owner_id:'synthetic-user',pool_id:null,version:1,facts:[],history:[]}
const newId = 'zz-new-task-outside-first-page'
const listRequests = []
await page.route('**/api/**', async route => {
  const url = new URL(route.request().url()), path = url.pathname
  let data
  if (path === '/api/auth/login') data = {token:'synthetic-ui-token'}
  else if (path === '/api/auth/me') data = {id:'synthetic-user',username:'synthetic.hr',grants:['talent.read','file.read','task.run'].map(action => ({action,scope:'external_all',scope_id:null}))}
  else if (path === '/api/workbench') data = {people:{},parse_tasks:{},match_entries:{},assessments:{},definitions:{}}
  else if (path === '/api/catalog') data = {departments:[],positions:[],department_positions:[],pools:[]}
  else if (path === '/api/candidates') data = {items:[{...talent,tags:[],index_state:'ready'}],total:1}
  else if (path === '/api/imports/summary') data = {items:[]}
  else if (path === '/api/imports') data = []
  else if (path === '/api/assessments/assignments') data = {items:[],total:0}
  else if (path.endsWith('/extraction')) data = null
  else if (path === '/api/talents') data = {items:[talent],total:1}
  else if (path === `/api/talents/${talent.id}`) data = talent
  else if (path === `/api/talents/${talent.id}/files`) data = [{id:'synthetic-file',original_name:'synthetic.png',size:100}]
  else if (path === '/api/files/synthetic-file/parse') {
    data = {id:newId,state:'queued',run_version:1,result:null,error_code:null,attempts:[]}
    tasks.push(data)
  } else if (path === '/api/tasks') {
    const offset = Number(url.searchParams.get('offset')), limit = Number(url.searchParams.get('limit'))
    listRequests.push({offset,limit})
    if (limit !== 20) throw new Error('任务列表未明确传入分页参数')
    data = {items:tasks.slice(offset,offset+limit),total:tasks.length}
  } else if (path.startsWith('/api/tasks/')) {
    data = tasks.find(t => t.id === path.slice('/api/tasks/'.length))
    if (!data) throw new Error('UI 查询了错误的任务编号')
  } else throw new Error(`未预期的接口: ${path}`)
  await route.fulfill({json:{data,request_id:'synthetic-ui-request'}})
})

try {
  await page.goto(process.env.TASK_UI_BASE_URL || 'http://127.0.0.1:5173')
  await page.locator('input').nth(0).fill('synthetic.hr')
  await page.locator('input').nth(1).fill('synthetic-ui-password')
  await page.getByRole('button',{name:'登录',exact:true}).click()
  await page.getByRole('heading',{name:'工作台',exact:true}).waitFor()
  await page.getByRole('button',{name:'解析任务',exact:true}).click()
  const table = page.getByTestId('task-table'), pager = page.getByTestId('task-pagination')
  await expect(page.getByTestId('task-total')).toHaveText('共 61 条任务')
  await expect(table.locator('.el-table__body tbody tr')).toHaveCount(20)
  await pager.locator('.btn-next').click()
  await expect(table).toContainText('synthetic-task-020')
  await pager.locator('.btn-next').click()
  await expect(table).toContainText('synthetic-task-040')
  await pager.locator('.btn-next').click()
  await expect(table.locator('.el-table__body tbody tr')).toHaveCount(1)
  await table.getByRole('button',{name:'查看',exact:true}).click()
  await expect(page.getByTestId('focused-task-id')).toHaveText('synthetic-task-060')

  for(let i=0;i<3;i++)await pager.locator('.btn-prev').click();await expect(table).toContainText('synthetic-task-000')
  await page.getByRole('button',{name:'人才画像',exact:true}).click()
  await page.getByRole('button',{name:'查看画像',exact:true}).click();await page.getByRole('tab',{name:'来源文件',exact:true}).click()
  await page.locator('.profile-workspace').getByRole('button',{name:'解析简历',exact:true}).click()
  await expect(page.locator('.profile-workspace')).toBeHidden()
  await expect(page.getByTestId('task-total')).toHaveText('共 62 条任务')
  await expect(page.getByTestId('focused-task-id')).toHaveText(newId)
  await expect(table).not.toContainText(newId)
  // 当前页没有新任务，但详情仍轮询它；模拟后台完成后检查显示更新。
  Object.assign(tasks.find(t => t.id === newId), {state:'succeeded',result:'新任务合成完成'})
  await expect(page.getByTestId('task-detail')).toContainText('新任务合成完成',{timeout:10000})
  if (![0,20,40,60].every(offset => listRequests.some(r => r.offset === offset))) throw new Error('分页未覆盖第 50 条之后的记录')
  if (errors.length) throw new Error(errors.join('; '))
  console.log('Task UI regression passed: 61-item pagination, off-page new-task detail and polling (synthetic API).')
} finally {
  await context.close()
  await browser.close()
}
