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

## 第二阶段审查补充
repositories/access.current_task_file统一核对Task与File当前归属，原文读取/执行/提交/重试/核对及索引引用均不能沿用已失效文件关联。business.save_talent保存独立类别确认（含空集合），resume_tasks.apply_extraction据此只给更新建议。resume_index以到期时间公平领取，持久化退避和领取版本，不在Embedding/Milvus期间持锁。详细复现和本轮验证见stage-two-review.md。


## 第三阶段首批入口（2026-11-06）
需求人工闭环：schemas/requirements.py定义薪资与条件；services/requirements.py负责部门范围与动作鉴权、幂等、原子版本、草稿及不可变快照；models/entities.py新增RecruitmentRequirement/RequirementVersion；api/routes.py承接HTTP；frontend/src/RequirementWorkspace.vue为统一表单与历史；tests/test_requirements.py验证权限、版本、状态、幂等及迁移。JD辅助与匹配已完成，见stage-three.md；f084aa25c006和g195bb36d007已应用开发库，Worker新增独立匹配入口。


S3-02：jd_assist.py编排需求鉴权、无长事务的模型请求、建议证据校验与返回前复查；resume_providers.generate_json集中配置/超时/安全错误，简历抽取委托同入口；RequirementWorkspace处理原文、自动粘贴提取、合并差异、建议采纳与迟到响应。JD没有业务持久任务，受90秒同步超时保护；匹配已使用下述独立可靠任务。


## 第三阶段完整链路

HTTP routes → requirements/jd_assist → HR确认RequirementVersion → match_tasks.start固定授权范围/资料/规则/需求快照 → MySQL match_outbox → 现有cli dispatcher → 同一Celery Worker的talent.match → match_rules三态检查及本地Embedding/BM25/RRF → 执行版本与当前权限屏障 → MatchEntry结果 → 当前授权下分组/证据/历史。

match_tasks.py负责业务快照、授权、可靠执行和短事务；match_rules.py为可测试的纯规则/排序；schemas/matching.py为启动、权重与关联契约；worker.py只注册队列入口，cli.py统一轮询既有解析与新匹配outbox/恢复。RequirementWorkspace为同表单需求与JD，MatchWorkspace为独立匹配交互；CandidateWorkspace呈现显式关联和所选需求已有分数，原文跳转仍走受控解析接口。

没有新增微服务或检查点数据库；固定流程及MySQL执行状态已满足恢复，无须为本阶段引入LangGraph。索引继续供后续检索使用；全范围匹配从业务权威快照实时Embedding，不用Milvus top-k代替全集，也不依赖异步索引是否就绪。重启/配置及真实验证见stage-three.md和stage-three-verification.md。


年限审查后：year_evidence.py集中YearClaim/YearEvidence区间、否定/模糊、总与技能归属及JD引用数值位置；match_rules和jd_assist共享它，不再各自截取裸数字。规则v3通过match_tasks/candidates/MatchWorkspace显示历史失效；无需新增表或依赖。实际回归/部署见stage-three-review.md。
