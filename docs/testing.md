# 测试与验证指南

所有命令在项目根目录执行，另有说明除外。验证报告应区分真实服务、测试替身、静态检查和未验证项；历史通过记录不等于当前提交重新通过。

## 常规检查

```powershell
$env:PYTHONPATH = Join-Path $PWD 'backend'
.venv/Scripts/python.exe -m pytest -q
npm.cmd --prefix frontend run build
```

pytest默认使用独立临时SQLite，并覆盖该测试库的结构；不操作开发库。真实MySQL回归使用 `scripts/test-mysql.py` 创建随机 `talent_test_*` 库，需已有服务可用。测试内模型/向量替身验证确定性边界，不代表真实模型效果。

## 最新改动的定向检查

```powershell
$env:PYTHONPATH = Join-Path $PWD 'backend'
.venv/Scripts/python.exe -m pytest tests/test_filter_task_ui.py tests/test_review_fixes.py -q
Set-Location frontend
node scripts/filter-task-review.mjs
```

第一条覆盖姓名字面包含、员工隔离、任务元数据及时间分页、既有权限回归。浏览器脚本使用真实Edge、前端5173及API8000，只读现有业务资料；从本机忽略账号文件读取凭据，依赖已安装的虚构场景并要求存在姓名含杨的资料。它不是通用空库测试，不会主动补造记录；任意环境应改用独立合成API/测试库验证。截图仅存忽略data目录。

最近一次实际结果与限制见[调整记录](filter-task-adjustment.md)：定向5 passed、生产构建及真实页面检查通过。没有将它们累计为全套177项回归。

## 集成与故障测试

阶段二至五验证文档保留真实OCR/生成模型/Embedding、任务恢复、备份恢复及效果基线。旧live脚本可能依赖demo账号、历史ID、固定资料数或旧按钮，并可能写入记录、停止Redis或强杀Worker。不要直接在当前业务环境批量执行；另建隔离环境并按对应记录准备，故障脚本不得并行运行。

日常依赖状态使用 `scripts/check-local.py`，它不宣称生成模型效果通过。当前虚构场景核对脚本也包含固定初始数量，用户新增资料后不能为了让断言通过删除数据。后续应按实际需求升级测试，不改写历史证据。
