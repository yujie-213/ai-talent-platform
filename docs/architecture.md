# 模块导航

模块化单体；Windows API / Vue 前端，Linux Celery Worker、dispatcher 和 indexer 共用后端代码。MySQL 为业务权威源，Redis仅投递；第二阶段接入隔离CPU PaddleOCR、生成模型API、本地Ollama bge-m3和既有Milvus。固定流水线无须LangGraph或新的持久化服务。

| 入口 | 职责 |
|---|---|
| backend/app/main.py | API 启动、统一错误/追踪、安全日志 |
| backend/app/api/routes.py | HTTP 契约、依赖注入、响应及下载 |
| backend/app/core/security.py | 当前身份、独立动作范围、默认拒绝 |
| backend/app/core/config.py、db.py | 本机配置、会话；无启动建表 |
| backend/app/services/application.py | 账号/基础资料/人才/文件/任务业务编排及事务 |
| backend/app/services/business.py | 档案约束、原子版本、历史、幂等、审计 |
| backend/app/repositories/access.py | 当前授权、人才分页/事实/历史读取 |
| backend/app/services/files.py | 类型/大小校验、路径规范化 |
| backend/app/models/entities.py、schemas/inputs.py | 实体、约束与入参 |
| backend/app/tasks/worker.py | Celery入口、领取/成果屏障、续租、投递/恢复 |
| backend/app/cli.py | 引导/合成数据、补偿器 |
| backend/alembic/versions/ | 初始建表与角色版本迁移 |
| frontend/src/App.vue、style.css | 人工档案/最小管理；CandidateWorkspace.vue 筛选/批次，ExtractionResult.vue 证据与核对，api.ts统一请求 |
| infra/compose.yml、Dockerfile | 隔离 MySQL/Redis/Worker/dispatcher |
| tests/test_stage_one.py、test_additional.py、test_review_fixes.py | 权限、文件、任务、并发/分页等 18 项回归 |
| scripts/test-mysql.py | 随机独立库真实迁移回归，不清空开发库 |
| scripts/test-worker-live.py | 真正 Broker 中断、容器强杀恢复验证 |
| frontend/scripts/smoke.mjs | 本机 Edge 真实页面/上传/新任务详情与Worker轮询验收 |
| frontend/scripts/task-pagination.mjs | Edge + 合成API：超过50条任务翻页、列表外新任务详情/轮询 |

首版应用服务部分简单管理读写仍直接使用 SQLAlchemy 会话；关键范围查询集中在 Repository，路由不持有业务 SQL。后续相关模块扩展时按职责提取，避免空架构抽象。

表关系见 schema.md，端点见 api.md；接手先读 progress.md / handoff.md。修改公共权限时同时检查业务、文件与任务调用方。

## 第二阶段实现入口
resume_reader.py 按页/段落读取；resume_providers.py 统一模型/Embedding与隔离OCR入口；resume_validation.py 校验引用、结构、联系方式与时间；resume_tasks.py 业务编排与短事务成果屏障；candidates.py 授权组合筛选；resume_index.py 可重建索引事件补偿。tasks/worker.py 只作队列入口/领取/恢复，不内嵌格式读取。前端 CandidateWorkspace/ExtractionResult 和统一 api.ts 分开。逐项真实验证与限制见 stage-two-verification.md。
