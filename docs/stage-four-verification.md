# 第四阶段最终验证与页面验收

2026-11-06，北京时间。第三阶段已由李玉杰验收；第四阶段授权范围为统一档案聊天、轻量测评、真实工作台及管理页面。下方旧“仅子项”记录保留为历史，本节为最终真实结果入口。阶段完成后待李玉杰验收，不代替负责人确认，不进入第五阶段。

## 最终自动化与真实集成

| 实际命令（项目根，页面脚本另注明） | 实际结果及性质 |
|---|---|
| `.venv/Scripts/python -m pytest -q --tb=short` | 完整SQLite 164 passed /457.88秒，API、数据库、LangGraph与关键权限/恢复回归；模型和Embedding在确定性测试中明确使用替身 |
| `.venv/Scripts/python scripts/test-mysql.py` | 真实随机独立MySQL完整164 passed /1041.06秒；迁移及业务持久化真实，未清空开发库 |
| `.venv/Scripts/python -m pytest -q tests/test_archive_chat.py tests/test_stage_four_management.py tests/test_assessments.py tests/test_jd_assist.py --tb=short` | 定向31 passed /192.82秒，包含最终条件继承/澄清、授权、测评及管理 |
| `.venv/Scripts/python scripts/test-mysql.py tests/test_archive_chat.py tests/test_stage_four_management.py tests/test_assessments.py tests/test_jd_assist.py` | 真实独立MySQL定向30 passed /506秒，当时尚无最后一项代词澄清回归 |
| `.venv/Scripts/python -m pytest -q tests/test_archive_chat.py --tb=short` | 末轮15 passed /62.50秒，包含旧轮次保护、独立技能年限、语义条件继承/取消确认及已验证源段落引用 |
| `.venv/Scripts/python scripts/test-mysql.py tests/test_archive_chat.py` | 独立技能年限版13 passed /115.12秒；旧轮次拒绝为随后补充，另见下一项 |
| `.venv/Scripts/python scripts/test-mysql.py tests/test_archive_chat.py::test_count_graph_checkpoints_scope_and_stream tests/test_archive_chat.py::test_empty_scope_expansion_confirmation_and_idempotency tests/test_archive_chat.py::test_semantic_full_coverage_evidence_and_cross_person_rejected tests/test_archive_chat.py::test_old_failed_turn_cannot_retry_after_new_context` | 最终MySQL 4 passed /57.95秒，验证条件更新匹配行数、空范围确认、已确认语义追问及旧上下文拒绝 |
| `.venv/Scripts/python -m pytest -q tests/test_archive_chat.py tests/test_resume_reading.py tests/test_resume_tasks.py --tb=short` | 23 passed /65.90秒；最终Repository职责整理与调用元数据包装不影响原解析 |
| `npm --prefix frontend run build` | TypeScript与生产构建通过；保留大包提示，无类型错误 |
| `.venv/Scripts/python scripts/verify-chat-live.py` | 真实API/MySQL/Redis/Celery/LangGraph原生MySQL检查点/生成API/本地bge-m3，三份合成档案，无模型/向量替身；结果见下表 |
| `.venv/Scripts/python scripts/verify-chat-recovery-live.py` | 真实Redis停机补投、Worker SIGKILL及45秒租约恢复到执行版本2、旧提交拒绝、旧/重复消息不新增尝试和条目，通过；finally已恢复 |
| `.venv/Scripts/python scripts/verify-chat-file-live.py` | 真实合成DOCX导入→Worker/模型提取→档案→聊天→受控来源段落与版本→下载原文件字节一致，通过；不使用解析/模型替身 |
| `npm --prefix frontend run test:chat-live` | 最终锁定Playwright1.65.0的真实Edge+API+MySQL+Worker/模型+SSE；当前档案/勾选/筛选范围、历史语义覆盖、逐人引用、真实DOCX源段落/原文件下载、管理员隔离及管理页面通过，退出码0，无API替身 |
| `npm --prefix frontend run test:management-live` | 真实页面创建合成角色、保存本人功能范围/菜单、创建账号、设置角色与按姓名绑定；新账号只见本人且跨人404，finally禁用解绑并核对旧JWT401，通过 |
| `npm --prefix frontend run test:chat-late-response` | 真实后端响应，仅对旧任务注入明确2秒传输延时；切换1人新会话后迟到旧范围不覆盖当前视图，通过。此项不是模型效果评测 |
| `npm --prefix frontend run test:assessment-live` | 真实题库创建、发布、分配、员工草稿/提交/确定评分、标准答案隔离及管理页；首轮及最终Playwright1.65.0重跑均通过，脚本可重跑 |
| `npm --prefix frontend run test:browser` | 最终Playwright1.65.0三账号真实页面及既有文件/Worker机制链通过；本轮未重做OCR复杂文档效果评测 |
| `npm --prefix frontend run test:task-pagination`、`$env:FRONTEND_URL='http://127.0.0.1:5173'; npm --prefix frontend run test:jd-assist` | 最终Playwright1.65.0重跑均通过；明确合成API替身的分页及JD人工保护UI回归，不算真实模型效果。JD脚本默认5175未运行时曾连接失败，指定现有5173后通过 |

完整回归执行后又补充旧轮次屏障等小范围行为，采用对应定向验证；不把各轮测试数相加当准确率或伪称同一版本的总测试数。所有MySQL测试均由scripts/test-mysql.py创建受限名称随机库后删除该一次性库，开发库只增量迁移。

## 小规模真实效果基线（3份合成资料）

甲：本科、总经验3年、Python声明，RAG设计开发/生产部署/评估监控/10万用户有原文。乙：硕士、总经验4年、Python声明，只写RAG组件，未提供生产及规模。丙：本科、总经验2年、Python声明，明确没有RAG生产上线经验。先人工定义判据及预期，再运行真实模型；无固定答案替换。

| 问题 | 人工口径与实际结果 |
|---|---|
| 本科（不含更高学历）、总经验至少3年、Python声明的外部人才 | 实际1人，按Talent ID去重；超过3年追问实际0人，符合手工条件 |
| Python使用经验至少3年 | 三人都无技能专属时间依据，实际0符合、3信息不足；不借用总经验3/4/2年 |
| 完整RAG落地人数，确认设计开发/部署/评估监控判据 | 覆盖3/3；支持1、未知1、明确不支持1、失败0，与手工标注一致 |
| 单人完整落地/规模问答、两人比较 | 逐人引用核对通过，原文及来源属于本人；人工事实被明确标为人工依据 |
| 自然语言找RAG落地人才 | 真实本地Embedding+BM25及逐人证据核验，仅报告“当前找到”，没有冒充全量语义人数 |

详细结果保留data/stage-four/chat-live.json，仅合成样本；来源逐条通过受控引用接口核对。仅3份资料，不能宣称总体准确率、企业级能力或吞吐。

实际限制：带“不是总工作年限”的解释性否定整句会被共享保守边界校验澄清；记录该限制后，改用明确正向“Python使用经验至少3年”得到0符合/3未知。未悄悄用总年限回答。上界/区间、复杂逻辑与指代不明也保守澄清。结构条件目前支持最高学历eq/ge、总/技能年限ge/gt等白名单，不支持的表达不得转成任意SQL。

普通语义检索每人最多取前12000字符用于向量排序，最多10人证据核验，未检索者不计为已完成语义评估；完整语义人数不使用这一截断，按明确范围逐人评估全部当前有效事实，未知/失败单列。尚未评测大规模并发、长期运行、复杂自然语言总体效果。

## 故障、失败与恢复的真实记录

- 镜像源缺少锁定的SDK0.4.14，改用官方PyPI构建相同固定依赖；Windows和Linux pip check通过，未升级OCR或既有数据库/向量服务。
- 真实模型把“先确认判据”分成普通clarify，并凭空加internal；已修正路由，未提身份不接受模型加身份限制，重跑真实样本通过。
- Redis补投后一次模型JSON计划不合schema，业务任务明确失败、没有生成错误人数。加入一次受控schema修复，仍执行完整白名单校验；再跑故障恢复通过。非法SQL计划替身始终不能执行。
- 真实Redis停机时outbox tries=1、业务queued；恢复后同一任务成功。Worker强杀后同一业务任务run_version=2，attempts为expired/succeeded；旧finish返回False，旧/重复Broker消息未产生新attempt，唯一3条人才成果。报告data/stage-four/chat-recovery.json。
- 单测注入评分失败、模型异常/禁用/撤权/跨人引用；单测文件来源是明确合成持久化替身。另有verify-chat-file-live真实DOCX/模型/文件链通过，两者不混称。复杂OCR效果仍以前阶段记录为准，本轮未重做总体评测。
- 真实DOCX将技能提取为“Python”，验证过的来源段落为“技能：Python、RAG。”；旧引用校验仅接受提取值内部片段而误拒绝原文。修正为还可引用已核验Task/File来源段落中包含提取值的原文，新增跨人/无来源拒绝测试；真实解析、聊天引用、版本和原文件字节核对重跑通过。
- 真实页面发现筛选前旧请求迟到会覆盖新筛选结果，已增加请求序号与加载状态，确保聊天继承当前页面范围；会话切换、来源弹窗和SSE也有旧视图屏障，2秒延时注入验证通过。
- Edge脚本隐藏checkbox定位及“历史会话最新轮次已变化”断言曾失败，改用可见checkbox及明确历史任务选择后通过。基础三账号脚本曾在数据加载前立即数行，改用等待1行的断言，未修改业务答案。
- Playwright1.49.1在真实原文件下载后所有业务断言通过，但关闭浏览器时发生内部TargetClosedError。只将相关测试驱动及其两项传递包锁定1.65.0（Node24兼容），不升级业务Vue/Vite/浏览器或后台服务；相同下载及全部聊天/管理断言重新执行，正常退出0。升级依据为官方[浏览器兼容说明](https://playwright.dev/docs/browsers)及npm实际版本查询，不隐藏或吞掉驱动异常。

## 部署与数据边界

新增迁移h206cc47e008/i317dd58f009/j428ee69a010/k539ff70b011已应用开发库；LangGraph1.2.20/core1.7.6/checkpoint4.3.1及传递依赖锁定，原生MySQL JSON检查点，不增加数据库服务。后台镜像ai-talent-stage4-backend:0.4.0基于既有0.2.1（构建基线摘要d3d09d6f39c23530d38dafc2fe9c1fd0619db6b0e0eedeee754707c17f605431），原独立OCR环境不变。精确启动命令见README第四阶段节。

API8000/页面5173保留本机运行；仅本项目Worker/dispatcher/indexer重载，原MySQL/Redis/Milvus/Ollama及其他应用不升级、不删库/卷/模型、不重seed。合成HR只显式追加测评和chat.use授权，管理员无默认正文权。账号绑定仅account.manage必需最小身份元数据，不泄漏联系方式/事实；菜单隐藏不代替功能撤权。审计和调用记录只留必要元数据，简历/聊天/密钥不裸记。报告、原文件、账号和截图仍在忽略data，不入Git。

最终执行`docker build -f infra/Dockerfile.stage4 -t ai-talent-stage4-backend:0.4.0 .`及README中的三文件compose `up -d --no-deps worker dispatcher indexer`成功。最终镜像摘要sha256:d23c77714544cb33c7e4540ef76675b61e1bec2154d2ee02d5f6b11c314b92fd；Windows与Worker `python -m pip check`均返回No broken requirements found，`alembic -c backend/alembic.ini current`返回k539ff70b011(head)。API健康地址是`/api/health`，非`/health`；前者返回正常，页面5173返回200。最终前端构建通过，保留约1MB主包提示，不宣称已做性能优化。

## 负责人页面验收顺序

1. 打开本机5173，使用data/local-access.txt已有合成账号。HR/员工/管理员分别登录，工作台应展示各自当前范围的真实数字；管理员看不到人才、聊天和测评正文入口。
2. HR在人才详情进入聊天；或候选人勾选两人聊天、按筛选聊天。核对范围人数及筛选原文条件。空勾选问“这些人有多少”应澄清，不能全库。
3. 同一入口问“本科、3年以上Python外部候选人有多少”，核对最高学历eq/ge和年限含边界；追问“超过3年的呢”。技能专属年限不借用总年限。
4. 单人问RAG落地并核对来源；多人比较逐人展开。人工事实显示人工来源。更新某合成档案后，旧轮次显示来源版本/过期，不回写历史。
5. 问“完整RAG落地的有多少”，先确认可核验判据，再看逐人覆盖/支持/未知/失败。断线后打开历史或连接原任务，任务号不变。松开条件或要求全部授权范围需明确确认；有后续轮次的旧失败任务不能重试改写新上下文。
6. HR题库维护单选/多选/判断、维度及分值，发布试卷版本，分配绑定员工。员工保存草稿，未答提示后提交；答案锁定，成绩及实测维度入档。修改题库发布新版本不影响旧任务。HR从人才详情查看授权历史，测评不进入岗位匹配分。
7. 管理员账号页创建/启停、配置部门/角色和姓名绑定；角色页配置动作/独立数据范围及菜单，确认权限/菜单版本冲突。基础资料新建、改名、停用后历史归属保留；新归属拒绝停用对象。
8. 管理员审计页与AI调用页分页筛选，查看时间/状态/耗时/安全错误码，无聊天/简历正文。撤销权限或禁用后，旧JWT、历史会话、引用和任务读取应被拒绝。

测评评分恢复目前为保留提交后由授权页面/API显式重试，不宣称自动Celery评分补偿。雷达图只展示本试卷实际维度得分比例，不证明总体能力或跨卷量尺可比性；未测维度不从简历推算。第二阶段整体体验/“未确认”标签优化仍按已批准决定暂缓。

---

以下为前轮子项验证历史；状态与完整验收入口以本节为准。

# 第四阶段验证记录（进行中，非阶段验收报告）

2026-11-06，北京时间。当前只完成测评、工作台和部分管理。聊天、持久语义任务、AI调用日志页面及完整管理交付仍未完成；不标待用户验收，不进入第五阶段。

## 基线与运行环境

- 起始分支codex/stage-three-requirements，HEAD与远端均7c322a3，工作区干净；c384b97..7c322a3只有文档差异。新分支codex/stage-four-chat-assessment，从该HEAD创建，main未动。
- 普通权限运行pytest首次无法打开临时SQLite，不能算业务失败或通过。使用正常本机权限重跑。首次完整回归期间添加了新迁移，进程旧metadata未包含新表，后续fixture出现重复建表错误；该次91 passed/50 errors无效，未作为基线。
- 为消除开发中变更干扰，git archive导出7c322a3至忽略的data/stage-four-baseline，使用项目.venv及该目录backend执行`python -m pytest -q --tb=short`：**141 passed /244.70秒**，真实隔离SQLite，原始基线未修改。
- 现有Python3.13项目.venv、Windows API、真实MySQL13306/Redis16379、现有Linux Worker；没有升级既有服务、删库或清空账号。

## 实际命令与结果

| 命令 | 结果/性质 |
|---|---|
| `.venv/Scripts/python -m pytest -q tests/test_assessments.py` | 首批4 passed /10.14秒，真实API及隔离SQLite；故障评分为显式异常替身 |
| `.venv/Scripts/python scripts/test-mysql.py tests/test_assessments.py` | 首批4 passed /23.24秒，真实随机隔离MySQL；不碰开发库 |
| `.venv/Scripts/python -m pytest -q tests/test_assessments.py tests/test_stage_four_management.py --tb=short` | 6 passed /21.59秒，含工作台/停用/角色授权 |
| `.venv/Scripts/python scripts/test-mysql.py tests/test_assessments.py tests/test_stage_four_management.py` | 6 passed /43.03秒，含两条迁移及唯一成绩并发 |
| `.venv/Scripts/python -m pytest -q --tb=short` | 147 passed /290.09秒；之后增加两项测评测试及停用归属检查，另见下一项 |
| `.venv/Scripts/python -m pytest -q tests/test_assessments.py tests/test_stage_four_management.py tests/test_requirements.py --tb=short` | 最新14 passed /62.60秒，含撤权/禁用、试卷新版本、隔离库迁移升降级及第三阶段需求回归 |
| `.venv/Scripts/python scripts/test-mysql.py` | 最终149 passed /626.53秒，真实随机独立MySQL完整回归，含最新两项测评测试和基础资料校验 |
| `npm --prefix frontend run build` | 类型及生产构建通过；保留原有大包提示 |
| `node frontend/scripts/assessment-live.mjs`（实际cwd=frontend，命令`node scripts/assessment-live.mjs`） | 真实Edge→API→MySQL，无API/评分替身；HR页面题库创建、发布、分配，员工草稿、提交并得到10/10，标准答案隔离，管理员无业务入口，角色页面通过 |
| `npm --prefix frontend run test:browser` | 三账号真实Edge/实际API/MySQL/上传/Worker机制任务通过，无OCR或模型效果宣称 |
| `npm --prefix frontend run test:task-pagination` | 61条分页、页外新任务直达与轮询通过；明确合成API替身 |
| `$env:FRONTEND_URL='http://127.0.0.1:5173'; npm --prefix frontend run test:jd-assist` | JD粘贴、人工防覆盖、显式采纳、失败和迟到保护通过；明确合成API替身 |
| `.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head`及`current` | 开发库已至i317dd58f009；h206cc47e008/i317dd58f009增量应用，无历史迁移改写或重置 |

真实页面首次在提交确认框等待中文“确定”失败，产品默认按钮是英文；已显式配置中文确定/继续答题并重跑通过。原任务分页替身测试发现隐藏测评抽屉造成多匹配，改为仅有详情时挂载抽屉，重新通过。没有掩盖这些失败。

## 覆盖及限制

测试覆盖标准答案投影隔离、旧快照、非法题目/选项、草稿、原子锁定、重复/并发提交唯一成绩、评分故障保留原提交并恢复、非本人拒绝、换绑/禁用/撤权、试卷新版本不影响历史、迁移往返、按权限工作台及停用历史保留。评分异常由monkeypatch注入，不代表真实生产故障。

真实Edge脚本使用既有合成账号；通过既有管理员API为合成HR显式追加测评manage(global)、assign/read(internal_all)，不赋予管理员业务正文权限，不重新seed。新建题目/试卷/任务均有合成标签。报告和截图在忽略目录data/stage-four，未提交账号、原文件或敏感正文。

测评恢复当前为页面/API显式恢复评分，不是Celery自动补偿；大规模并发/负载和长期运行未测。题库/试卷/员工选择列表目前未分页；任务历史分页，工作台按当前授权实时计算。基础资料支持新增和启停，尚不宣称完整组织管理/菜单配置/日志管理交付。雷达图仅本试卷实际可归一化维度，少于三个维度用条形图，缺失为未测评；不跨试卷推断可比性。

LangGraph仅做Windows兼容性预检：`pip index versions langgraph`、`pip install --dry-run langgraph==1.2.20`、项目.venv实际安装1.2.20及`pip check`通过；核心1.7.6、checkpoint4.3.1。未改requirements/Worker镜像，未实现图流程/MySQL检查点，未验证Linux运行，不能算聊天交付。持久化候选依据官方[自定义检查点文档](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/checkpointers.mdx)，具体方案和依赖仍须实现并锁定验证。

## 本机页面核验步骤

1. 打开本机5173并使用data/local-access.txt已有合成账号登录；工作台无固定演示数字。管理员应无人才/测评正文入口。
2. 管理员→角色与菜单权限创建角色，配置功能/范围；账号管理设置启停、角色、人才绑定。指定部门/人才库使用下拉选择。
3. HR→轻量测评→新增题目：设置题型、选项、正确选项、维度、分值；发布试卷，选择题目后发布不可变版本，分配给绑定合成员工。
4. 员工→轻量测评→答题/查看，保存草稿，再提交确认；提交后不可改答案，查看总分与实测维度。HR人才详情可看授权结果历史。
5. 编辑题库答案并发布试卷新版本，旧任务的题目/版本和成绩保持原样；新分配才使用新版本。
6. 管理员基础资料停用某对象，已有归属保留；停用对象不可用于新建归属。启停及权限编辑陈旧版本应冲突。

这些步骤仅核验已实现子项，不等于负责人对第四阶段整体验收。


## 当前提交与部署
代码提交821aeef，已正常推送origin/codex/stage-four-chat-assessment，未合并main。最终API已重载并健康检查通过，页面5173保留。原有Worker/dispatcher/indexer正常重载，其他服务未动。最后文档提交通过git log核对；当前整体状态仍进行中，统一聊天及未完成管理范围不得视为交付。
