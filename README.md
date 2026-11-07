# AI 数字化人才平台

面向企业招聘与员工发展的 AI 人才工作平台，将简历解析、人才画像、岗位匹配、档案问答和轻量测评连成一条可追溯的业务链。

HR 可以从简历导入开始，筛选人才、核对画像和来源、发起岗位匹配，再基于同一份资料进行问答与比较。员工查看本人档案并完成测评；管理员维护账号、角色和组织资料。各角色可见的数据由后端实时授权决定。

## 核心功能

| 能力 | 当前实现 |
|---|---|
| 简历导入与解析 | 支持 PDF、PNG、JPEG、DOCX；本地 OCR 与生成模型抽取结构化事实，保留原文依据、任务进度和失败原因 |
| 人才筛选与画像 | 姓名包含匹配、技能、身份、学历和经验筛选；独立画像页面、来源文件、人工修改保护与版本冲突检测 |
| 岗位与匹配 | 维护岗位条件，辅助提取 JD；固定需求及资料快照，展示满足、待核对、不满足与执行失败分组、规则证据和排序分 |
| 档案问答 | 单人问答、勾选比较、筛选范围问答；引用可追溯，人数查询区分结构化统计与语义核验 |
| 轻量测评 | 题库、试卷发布、员工分配与答题、客观规则评分、历史成绩及实测维度展示 |
| 工作台与管理 | 授权范围内的业务概览，账号、角色、菜单、组织资料、操作审计与 AI 调用日志 |
| 可靠后台任务 | 幂等、执行版本、事务 outbox、租约恢复及迟到结果隔离；解析历史按批次查看，任务按最近解析时间排序 |

匹配分用于排序参考，不是录用概率。资料未知不会被当作满足条件；人工维护的事实不会被迟到的解析结果覆盖。

## 技术架构

采用模块化单体，HTTP API 与后台任务进程独立运行、共享业务代码。

| 层次 | 技术与职责 |
|---|---|
| 前端 | Vue 3、TypeScript、Element Plus；工作区、表格、画像和问答交互 |
| API 与业务 | FastAPI、SQLAlchemy、Alembic、MySQL；鉴权、事务、版本和权威业务数据 |
| 后台任务 | Celery、Redis、dispatcher、indexer；投递、执行、恢复和索引补偿 |
| AI 流程 | LangGraph、生成模型 API、本地 PaddleOCR、Ollama bge-m3、Milvus |

MySQL 保存业务状态和成果，Redis 负责投递，Milvus 保存可重建的向量索引。模型通过受控业务服务读取数据，不能绕过权限执行任意 SQL；评分、权限、校验和持久化由代码负责。模块与调用链见[架构导航](docs/architecture.md)。

## 本机运行

当前验证环境为 Windows PowerShell、Python 3.13、Node.js 24 和 Docker Desktop Linux。API 与前端运行在 Windows，MySQL、Redis 和后台任务运行在本项目容器中；模型端点、Ollama 与 Milvus由本机配置提供。

**已经部署过本项目时**，先打开 Docker Desktop，等待引擎就绪，再在 PowerShell 执行（项目位于其他目录时替换路径）：

```powershell
Set-Location -LiteralPath 'D:\AI数字化人才平台\AI 数字化人才平台'
docker compose --project-name ai-talent-stage1 --env-file .env -f infra/compose.yml -f infra/compose.stage2.yml -f infra/compose.stage4.yml start mysql redis worker dispatcher indexer
./scripts/reload-local-api.ps1
npm.cmd --prefix frontend run dev
```

首次安装前端依赖或锁文件更新后，先执行 `npm.cmd --prefix frontend ci`。平时启动无需重复安装。上述命令必须在项目根目录执行；前端终端保持打开。

- 页面：[本机工作台](http://127.0.0.1:5173)
- API 契约：[OpenAPI](http://127.0.0.1:8000/docs)
- 当前本机账号：在忽略的 `data/local-access.txt` 查看，不随仓库分发。
- 新环境配置、安装和迁移：[部署与恢复](docs/deployment.md)。首次安装与已有环境恢复分别说明，已有数据库无需重新初始化。

本机自检：

```powershell
.venv/Scripts/python.exe scripts/check-local.py
```

健康接口仅表示 API 存活；自检还检查数据库、队列和模型相关依赖。停止与备份恢复步骤同见部署指南。

## 开发与验证

```powershell
$env:PYTHONPATH = Join-Path $PWD 'backend'
.venv/Scripts/python.exe -m pytest -q
npm.cmd --prefix frontend run build
```

后端常规测试使用独立临时 SQLite；真实 MySQL 回归使用随机隔离测试库。当前筛选和任务页面的真实只读检查在 `frontend` 目录运行 `node scripts/filter-task-review.mjs`，依赖现有本机场景账号和 Edge。

部分历史 live 脚本会新增资料或中断队列，不能直接作为当前业务环境的日常检查。测试类型、命令及边界见[验证指南](docs/testing.md)。

## 当前状态与边界

当前已实现上述业务链并完成多轮本机集成验证。第一至四阶段已验收，第五阶段综合验证及最近界面调整待用户验收。现有演示业务资料为虚构场景，解析、匹配、问答及测评成绩由实际服务和规则执行；数据量会随本机操作变化。

少量合成样本的效果不代表总体准确率。复杂简历、JD 漏抽和语义判据仍需人工核对；跨主机安装、公网部署、长期稳定性及大规模负载尚未全面验证。依赖与模型版本固定，不为启动项目自动升级其他已有服务。

## 项目导航

| 内容 | 入口 |
|---|---|
| 文档总览 | [文档目录](docs/README.md) |
| 当前进度与接手 | [项目进度](docs/progress.md)、[交接说明](docs/handoff.md)、[接手入口](START_HERE.md) |
| 产品与范围 | [冻结 PRD](docs/prd-v1.0-20261104.md)、[已确认决定](docs/decisions.md) |
| 技术参考 | [架构](docs/architecture.md)、[接口](docs/api.md)、[数据结构](docs/schema.md) |
| 运行与验证 | [部署恢复](docs/deployment.md)、[测试指南](docs/testing.md) |

目录职责：`frontend/` 为界面；`backend/app/` 为 API、业务、权限及 AI 流程；`tests/` 为自动化回归；`scripts/` 为本机运维与验证；`infra/` 为容器配置；`docs/` 为说明和证据；`prototypes/` 为离线设计参考。

`.env`、账号、上传文件、数据库备份、日志和模型不进入 Git。
