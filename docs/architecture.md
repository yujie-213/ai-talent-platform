# 原型对齐补充（2026-11-06）

本轮用户参考R2覆盖上一轮蓝色视觉。App人才详情从drawer改为居中el-dialog，左档案/右embedded ChatWorkspace独立滚动，来源弹窗append-to-body；CandidateWorkspace新增筛选/导入页签。Workbench使用同一真实API呈现四格业务概览及原型双栏布局。接口、授权和任务机制不变；设计差异/验证见ui-prototype-alignment.md。

# UI 重构导航补充（2026-11-06）

App.vue按日常工作/招聘成长/系统管理分组当前菜单和动作权限交集，桌面人才详情采用ProfileFacts.vue＋embedded ChatWorkspace双栏，收起AI保留会话；列表多人/筛选问答使用独立drawer。CandidateWorkspace保持真实分页与成功筛选快照，CandidateCard.vue/candidate.ts负责展示与多选事件；KeepAlive保留列表。AppIcon统一SVG，style.css统一tokens及Element Plus映射/中文系统字体/响应式/焦点。未改后端API及权限，不新增岗位聊天服务；功能入口和验证见ui-redesign.md。

# 模块导航

## 第四阶段交付入口（待用户验收）

assessment_routes.py → schemas/assessment.py → services/assessments.py：客观题校验、不可变试卷快照、当前员工绑定、草稿版本更新、原子提交、独立事务规则评分及唯一成绩。AssessmentWorkspace.vue提供题库/发布/分配/本人答题/历史，人才详情复用测评历史；AssessmentRadar.vue只显示本试卷实测维度，不跨试卷推断能力。未改匹配算法及其历史。

workbench.py从当前授权查询真实人才/解析/本人匹配/测评及聊天统计；Workbench.vue为默认入口。RoleWorkspace.vue复用已有角色与授权接口，菜单显示配置与当前功能权限取交集；App.vue基础资料支持新增、改名和启停，不删除历史归属。ChatWorkspace.vue与LogWorkspace.vue提供统一档案聊天及安全日志页面。四条新增迁移均已应用开发库，完整链路见本页末节，验收步骤见stage-four-verification.md。

模块化单体；Windows API / Vue 前端，Linux Celery Worker、dispatcher 和 indexer 共用后端代码。MySQL 为业务权威源，Redis仅投递；第二阶段接入隔离CPU PaddleOCR、生成模型API、本地Ollama bge-m3和既有Milvus。第二、三阶段固定流水线保持原有任务机制；第四阶段统一聊天使用LangGraph及现有MySQL检查点，不增加数据库服务。

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


## 第四阶段完整业务链

审查增量：repositories/candidate_filters.py统一列表/聊天的五项筛选，包含requirement_id及原需求访问鉴权；CandidateWorkspace仅使用最近成功筛选上下文。ai/chat_answer.py接收原问题及已核验逐人证据，模型返回受约束原文片段参数，代码组织直接答案/共同记录/差异和编号引用。archive_graph在事务外调用，返回保存前重新检查权限和执行版本；失败明确回退原文。详见stage-four-review.md。
ChatWorkspace（档案/勾选/筛选上下文与同入口追问）→chat_routes（HTTP/SSE）→archive_chat（范围/版本/幂等/持久成果及引用）→repositories/chat_access固定授权范围查询→chat_jobs（outbox/attempt/租约/执行版本）→既有Celery talent.chat→archive_graph（意图、受控准备、检索/证据评估、回答）→MySQLChatSaver原生LangGraph检查点。模型仅生成Plan或逐人证据参数，不接触SQL执行器/写工具。

chat_queries复用match_rules/year_evidence的学历、技能与年限纯规则并校验逐人引用；普通结构人数走完整MySQL人才ID范围。语义检索用实时授权事实快照、本地bge-m3与BM25，最多10人证据核验，仅报告当前找到；完整语义人数确认判据后逐人核验全部明确范围。MySQL是权威源，不等待Milvus异步索引，也不以向量召回数量代替总人数；既有Milvus索引保持运行与更新。

ai_logging为生成/OCR/Embedding共享安全元数据入口；management提供菜单、绑定最小元数据、账号分页和审计/AI分页，LogWorkspace/RoleWorkspace/App提供实际操作。Workbench同时显示真实授权人才、解析、本人匹配、测评和聊天任务。后台使用ai-talent-stage4-backend:0.4.0及compose.stage4.yml，沿用独立OCR环境、MySQL/Redis/已有向量与生成配置。
