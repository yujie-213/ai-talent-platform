# AI 数字化人才平台


当前交付（2026-11-06）：第一至三阶段已由李玉杰验收。**第四阶段已实现并完成本机部署和验证，待用户验收**：统一档案聊天/引用/人数与持久语义任务、轻量测评、真实工作台及管理页面。本机页面 http://127.0.0.1:5173 、API http://127.0.0.1:8000 。当前规则、验证、限制及操作步骤见 [第四阶段清单](docs/stage-four.md) / [第四阶段验证与验收步骤](docs/stage-four-verification.md)。现有环境勿重新bootstrap/seed、勿删除库/卷/模型。未进入第五阶段，不发布公网服务。


## 历史阶段启动与验证说明

以下第一至三阶段段落保留历史实现与启动记录，阶段状态以本页顶部及第四阶段文档为准。
第二阶段请直接看本页末尾的“第二阶段启动与页面验收”、[逐项验证](docs/stage-two-verification.md)及[进度](docs/progress.md)。本页第一阶段说明保留为底座操作与历史记录。


李玉杰负责的分阶段学习项目。当前仅第一阶段：登录及当前授权 → 人工人才档案 → 受控来源文件 → 明确标识的后台机制测试。没有真实 OCR、LLM、Embedding 或匹配能力；不需要模型密钥。服务只绑定本机，不是公开部署。

## 本机启动（PowerShell，项目根目录）

已验证 Python 3.13.5 / Node 24.21.0 / Docker Desktop Linux；依赖在项目 `.venv` 内，未修改现有 Conda 环境。也可在自己新建的 Conda Python 3.13 环境执行同样命令。

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.lock.txt
.venv/Scripts/python scripts/setup-local.py
docker compose --env-file .env -f infra/compose.yml up -d mysql redis
$env:PYTHONPATH='backend'
.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
.venv/Scripts/python scripts/init-demo.py
docker compose --env-file .env -f infra/compose.yml up -d --build worker dispatcher
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开 PowerShell：

```powershell
cd frontend
npm ci
npm run dev
```

打开 <http://127.0.0.1:5173>；接口契约 <http://127.0.0.1:8000/docs>。首次启动 Docker Desktop 后等 Linux 引擎就绪。初次镜像下载/构建可能较慢，启动 Worker 前先完成迁移。

首次空库初始化生成的随机密码仅保存在本机 `data/local-access.txt`，请在本机打开，不要提交或粘贴到聊天。账号：`admin`（只管系统）、`demo.hr`（合成全范围 HR）、`demo.employee`（只读本人）。`init-demo.py` 遇到已有账号会停止，不会重置数据。自己初始化生产式空库用 `python -m app.cli bootstrap --username 自选账号`，密码隐藏输入；合成数据为可选 `python -m app.cli seed-demo`。两命令需设置 `PYTHONPATH=backend`。

本项目 Compose 名称 `ai-talent-stage1`，数据库 `talent`，独立卷，端口 MySQL 13306 / Redis 16379；不会复用 Dify 的 Redis、修改 Milvus 或运行 OCR。MySQL 8.4.11、Redis 6.2.24 采用本机核实后的镜像摘要固定；Python 镜像固定版本。API 从 `.env` 读取主机连接，Worker 使用 Compose 网络地址，文件共享 `data/files` 且数据库仅存相对标识。

停止本项目后台服务：`docker compose --env-file .env -f infra/compose.yml stop`。不使用 `down -v`，不删除已有卷。API/前端终端 Ctrl+C。修改数据库先做备份，再显式执行 Alembic；应用启动不会迁移。

## 页面验收

1. 用 HR 登录，在人才档案新建外部候选人；无内部部门，联系方式和教育/经历/项目/技能/证书可人工维护。
2. 保存后打开详情，查看人工确认标记、版本、修改摘要；两个窗口基于相同版本编辑，后提交应收到冲突，刷新后重新确认。
3. 上传 PDF/PNG/JPEG/DOCX（≤10 MiB，PDF ≤50 页），下载检查原字节。内容与扩展名不符、损坏或加密应拒绝。本阶段不进行解析。
4. 文件旁发起“测试成功/测试失败”，到任务记录查看；失败可最多重试至第 3 个执行版本。这些任务没有 OCR 成果。
5. 员工登录只有本人，不能新建档案；管理员人才列表为空。管理员可创建/启停账号、分配现有角色、按人才编号绑定账号，维护部门/岗位/部门岗位/人才库，查看审计。
6. 角色创建与动作范围配置通过 `/docs` 中受控管理端点完成：先获取角色 `version`，再 `PUT /api/admin/roles/{id}/grants` 提交 `{version,grants:[{action,scope,scope_id}]}`。完整角色管理界面属于后续补齐项。管理员可以配置业务授权但不因身份自动读取业务正文。

## 验证命令

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/python scripts/test-mysql.py
# 无其他本项目作业时执行：会临时停止项目 Redis 并强杀/恢复项目 Worker
.venv/Scripts/python scripts/test-worker-live.py
cd frontend
npm run build
npm run test:browser
npm run test:task-pagination
```

快速回归使用独立临时 SQLite；MySQL 回归创建随机 `talent_test_*` 测试库，结束只删除该库，绝不清空开发库。任务单元用例直接调用消费者和模拟失败投递器，不能替代真实 Celery 验证。浏览器回归依赖本机 Edge、已启动 API/前端及合成账号，会新增带“浏览器合成”前缀的演示人才，截图仅存本机 data。详细实际结果与集成验证入口见 `docs/verification.md`。

`test:task-pagination` 只需前端（默认5173）和本机 Edge，使用合成 API 替身验证61条任务翻页、新任务不在当前页时仍能直达详情并持续轮询，不修改开发库。后端真实权限与分页计数由 SQLite/MySQL 回归覆盖。任务页每页20条，可翻页、查看执行尝试；新建任务会直接展开详情。`test:browser` 另会真实上传合成图片并验证 Worker 完成后的详情更新。

## 代码与业务链

`backend/app/main.py` 接收请求 → `api/routes.py` 校验 HTTP 入参和响应 → `services/application.py` 编排业务与事务 → `repositories/access.py` 统一授权查询；`core/security.py` 每次重新加载当前授权。人工档案通过原子版本更新，修改与历史同事务保存。文件访问跟随人才的当前权限，不提供静态文件地址。

创建测试任务时，同事务写入 `tasks/outbox` → 独立 dispatcher 投递 Redis → Linux Celery Worker 条件领取 → `attempts` 记录执行 → 当前授权及执行版本校验后保存结果。投递失败保留 outbox；过期运行由 dispatcher 恢复或明确失败；重复消息和旧执行无法再次提交成果。

设计见 `docs/schema.md`、`docs/api.md`；交接入口 `docs/progress.md`、`docs/handoff.md`。前端为 Vue 3 / TypeScript / Element Plus。完整 V1 规划仍见 `docs/plan.md`，不自动进入第二阶段。


## 第二阶段启动与页面验收

复用已有.env、MySQL/Redis卷和用户账号，不重新运行初始化脚本，不删除容器/卷/模型。生成模型已在本机配置，禁止把密钥发到聊天或提交Git。

在项目根目录PowerShell执行（Python/Node等底座安装仍见上文）：

```powershell
$env:PYTHONPATH='backend'
.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
docker compose --env-file .env -f infra/compose.yml -f infra/compose.stage2.yml build worker
docker compose --env-file .env -f infra/compose.yml -f infra/compose.stage2.yml up -d
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另一个终端：

```powershell
npm --prefix frontend ci
npm --prefix frontend run dev
```

打开 http://127.0.0.1:5173 。本机账号仍从data/local-access.txt查看，不要把该文件提交或贴聊天。Worker使用隔离CPU OCR环境，indexer使用本地Ollama与既有Milvus；都不改变Dify服务。

配置：RESUME_LLM_BASE_URL（含供应商要求的/v1前缀）、RESUME_LLM_MODEL、RESUME_LLM_API_KEY。需兼容chat/completions和json_object；生成请求90秒超时。Ollama已有bge-m3，实测1024维；本机模型摘要锁在EMBEDDING_EXPECTED_DIGEST，权重变更会拒绝旧空间写入，应另建索引重建。容器地址已用host.docker.internal，若模型API实际在Windows本地，容器BASE_URL也需使用该主机地址；配置变化后重新执行compose up -d以载入环境，不用重置数据库。

页面验收：
1. HR登录，默认“候选人筛选”，按身份/技能/教育原文/经历原文组合筛选、排序、翻页，核对授权范围总数。员工/管理员不会因此扩大业务范围。
2. “导入简历”选择1至20份授权或合成文件，上传并解析。页面明确显示10 MiB/50页/批次20份及读取限额；同一选择重试保留原批次，另一次导入点击“新建另一批”。
3. 点击“进度与结果”，逐文件查看技术状态、执行次数/失败原因、资料状态、异常/缺失、原文定位与引用。失败文件不拖累同批其他文件；批次历史可逐份对账，损坏文件的失败也保留。
4. 正常初次解析可入档；疑似重复只展示当前授权内联系方式和对比，HR显式关联或排除。姓名相同不自动合并；明确关联时身份冲突拦截更新。
5. 打开“核对当前人才档案”，查看当前事实来源/确认状态。保存表单会将基础字段（含空值）与事实确认；再解析同一材料，原确认内容保持，差异进入建议。解析期间编辑也不会被迟到结果覆盖。
6. 回候选人页按技能找人并打开画像。索引状态独立显示；更新后等待后台补偿（30秒周期，耗时视本机），失败不会伪报就绪。需要时在详情点“重建检索索引”。
7. 不验收岗位匹配/档案聊天：本阶段显示未匹配，不产生分数，也不自动进入第三阶段。

重跑验证：

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/test-mysql.py
.venv/Scripts/python.exe scripts/test-index-live.py
.venv/Scripts/python.exe scripts/test-worker-live.py
.venv/Scripts/python.exe scripts/test-resume-recovery-live.py
npm --prefix frontend run build
```

真实浏览器在frontend目录运行 `npm run test:browser` 和 `npm run test:resume-live`；`npm run test:task-pagination`使用明确API替身。故障脚本仅操作本项目服务，并在finally恢复；不要与同项目其他故障脚本同时运行。

合成样本评测可选安装：项目.venv安装backend/requirements-evaluation.txt；单独建立.tools/ocr-venv并安装backend/requirements-ocr.lock.txt，再运行scripts/evaluate-ocr.py和scripts/evaluate-resumes.py。样本生成目录data/stage-two-evaluation均被忽略。真实简历不得用作公开测试样本。

已知限制与实际漏抽请看docs/stage-two-verification.md：小样本不代表总体准确率；复杂版式/手写/低清未测；DOCX页眉页脚等未完整覆盖；筛选为显式原文包含，不把未知当0年或擅自解释为“本科及以上”。


## 第三阶段增量交付记录（2026-11-06）
第二阶段已验收。第三阶段先交付岗位需求基础，随后交付JD辅助，现已完成全范围匹配/历史/证据并部署本机待验收。执行清单、接口、授权及验证见docs/stage-three.md与stage-three-verification.md。没有依赖升级或数据重置。

首批定向验证：`.venv/Scripts/python.exe -m pytest -q tests/test_requirements.py --tb=short -p no:cacheprovider`；真实隔离MySQL：`.venv/Scripts/python.exe scripts/test-mysql.py tests/test_requirements.py`；前端：`npm --prefix frontend run build`。定向测试验证真实API和数据库业务，不调用JD/匹配模型。


第三阶段S3-02已接JD辅助：岗位需求同一表单粘贴纯文本，自动提取、冲突核对或AI完善；原文保存、模型失败可手工继续。API/权限/部署前提仍见docs/stage-three.md（现已部署开发库）。`npm --prefix frontend run test:jd-assist`需独立前端5175，使用真实Edge+合成API；`.venv/Scripts/python.exe scripts/evaluate-jd.py`真实调用已配置模型评测三份合成JD，报告保存在忽略的data目录。完整样本目前有任职要求正文漏抽，不宣称整体准确率。


## 第三阶段完成后的启动与复核

复用现有.env和服务。已有数据先显式迁移，再重载API与本项目后台；不要重跑初始化或删除卷。合成HR授权准备脚本仅用于现有demo.hr/合成HR角色，不替换旧授权；真实账号通过现有管理接口按部门授权。

```powershell
$env:PYTHONPATH='backend'
.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
.venv/Scripts/python.exe scripts/prepare-stage-three-demo.py
docker compose --env-file .env -f infra/compose.yml -f infra/compose.stage2.yml up -d
docker compose --env-file .env -f infra/compose.yml -f infra/compose.stage2.yml restart worker dispatcher
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开终端`npm --prefix frontend run dev`。已运行的8000/5173不重复启动。固定镜像/锁定依赖复用，无新增安装要求。HR进入岗位需求，可按部门区分同名需求；JD辅助失败或漏抽时可手填。草稿不能匹配；确认后手动发起，默认外部全范围，可选内部排除目标部门现任。先看满足/待核对/不满足/执行失败分组，再看证据与排序；分数不是录用概率。总工作年限与某技能年限分别填写；无依据不编造。

重跑：完整`.venv/Scripts/python.exe -m pytest -q`，隔离MySQL用`.venv/Scripts/python.exe scripts/test-mysql.py`；真实集成`.venv/Scripts/python.exe scripts/verify-stage-three-live.py`，真实排序/全范围`.venv/Scripts/python.exe scripts/evaluate-matching.py`，技能年限`.venv/Scripts/python.exe scripts/verify-skill-years-live.py`。这些脚本创建合成记录，故障脚本只操作本项目并finally恢复，不要同时运行本项目其他故障脚本。完整真实浏览器在frontend目录运行`npm run test:stage-three-live`（先运行真实集成脚本生成本机报告）。报告/截图在忽略的data目录，不提交。限制和准确验证命令见验证文档。


第三阶段年限审查已修复为规则v3；旧规则结果会提示过期，先核对已保存需求条件再新建匹配，旧结果不会被自动覆盖。上下界/否定和总/技能年限分开处理，JD按完整原文归属校验。详细复现、命令和实际结果见docs/stage-three-review.md。


## 第四阶段：聊天、测评与管理

第四阶段两项审查修复已完成：按筛选聊天保留应聘需求条件，单人/多人问答直接展示具体记录及编号引用。复核见[审查修复及步骤](docs/stage-four-review.md)。旧会话缺失的需求条件不可回填，请从筛选页新建会话。

登录默认工作台（或该角色配置的首个可见菜单）。数字均按当前授权实时计算，包括人才、解析、本人匹配、测评及本人聊天任务。合成账号仍在data/local-access.txt，不贴聊天、不入Git。

统一聊天：可在人才详情点击“与当前人才档案对话”，或在候选人列表勾选后聊天、按当前筛选聊天。也可从档案聊天新建明确的全部授权范围会话。直接表达找人、单人问答、多人比较、结构化人数和追问，不选SQL/RAG模式。范围/条件/资料版本可核对；空选择不查全库，扩大范围或松开条件需确认。语义全范围人数先确认判据，任务卡片展示逐人覆盖、支持、未知和失败；普通语义检索只报告当前找到结果。来源按钮再次鉴权，人工事实不伪造文件。断线用原任务重连/历史恢复，不自动重问。

测评：HR题库维护→发布不可变版本→分配绑定员工；员工保存草稿→提交锁定→查看规则成绩和实测维度。HR在测评任务及人才详情查看授权历史。未答零分、多选完全正确得分，评分失败保留原始提交，通过原任务恢复评分。测评分数不加入岗位匹配，少于三个实测维度用条形图。

管理：账号分页、启停、部门、角色及按姓名绑定；部门/公司岗位/部门岗位/人才库新增、改名或停用；角色功能及独立数据范围；角色菜单显示；操作审计和AI调用分页筛选。菜单与功能授权取交集，隐藏菜单不代替功能撤权。管理员仅为绑定提供最小人才身份元数据，无默认正文、联系方式、聊天和测评内容权。HR授权内完整联系方式规则不变。

本机已应用h206cc47e008、i317dd58f009、j428ee69a010、k539ff70b011，后台镜像ai-talent-stage4-backend:0.4.0。LangGraph与新增传递依赖已锁定，沿用0.2.1基础镜像及原独立OCR环境；未升级MySQL/Redis/Milvus/Ollama等已有服务。

已有阶段三环境的增量部署（PowerShell，项目根目录）：
```powershell
.venv/Scripts/python -m pip install -r backend/requirements.lock.txt
.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
docker build -f infra/Dockerfile.stage4 -t ai-talent-stage4-backend:0.4.0 .
docker compose --project-name ai-talent-stage1 --env-file .env -f infra/compose.yml -f infra/compose.stage2.yml -f infra/compose.stage4.yml up -d --no-deps worker dispatcher indexer
$env:PYTHONPATH = "$PWD/backend"
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
如8000已有API，先确认并停止本项目旧API，再启动新进程；不要重复启动。页面继续使用frontend下`npm run dev`的5173本机入口，生产构建`npm --prefix frontend run build`。以上不重置库、卷或账号，不重复seed。

验证入口：`.venv/Scripts/python -m pytest -q --tb=short`；真实隔离库`.venv/Scripts/python scripts/test-mysql.py`；合成真实模型`.venv/Scripts/python scripts/verify-chat-live.py`；真实恢复`.venv/Scripts/python scripts/verify-chat-recovery-live.py`；页面`npm --prefix frontend run test:chat-live`、`test:assessment-live`、`test:browser`。故障脚本只操作本项目并finally恢复，不要同时运行其他本项目故障脚本。精确结果、替身和未验证项以验证文档为准，样本/截图/报告仅在忽略data目录。

真实DOCX来源链使用`.venv/Scripts/python scripts/verify-chat-file-live.py`，需要已安装的评测依赖`backend/requirements-evaluation.txt`；聊天页面脚本依次读取verify-chat-live与verify-chat-file-live生成的本机合成报告。真实管理写操作为`npm --prefix frontend run test:management-live`，新合成账号最终禁用解绑；`test:chat-late-response`仅注入网络延时，后端响应真实。浏览器工具已锁定Playwright1.65.0以兼容本机Edge原文件下载，更新已有前端依赖执行`npm --prefix frontend ci`，不重装或升级已有浏览器/后台服务。


## UI重构试用（2026-11-06）
当前分支codex/ui-ux-redesign，状态“UI整改待用户试用”。本机打开 http://127.0.0.1:5173，使用既有本机账号（data/local-access.txt，不入Git）；不需要重新seed或迁移。人才卡片→查看档案→右侧AI首次发送→核对来源→关闭回到原筛选。多人/筛选问答在列表旁打开，历史仍在“档案聊天”；岗位JD与匹配仍在同一需求表单。详细映射、命令、替身与限制见[UI重构记录](docs/ui-redesign.md)。
