# 第一阶段验证记录

2026-11-05，北京时间。所有数据为合成数据。以下记录后续验证会持续更新。

## 环境
- Windows；Python 3.13.5（Anaconda 基础解释器创建项目 `.venv`）；Node 24.21.0 / npm 11.19.0。
- Git 初始不存在，现已初始化。Git Credential Manager 已有 yujie-213 认证，无须用户重新登录；未安装 gh，使用 Git 和 GitHub REST 创建公开仓库。
- Docker 初始 Linux 引擎未启动；已启动 Docker Desktop 4.93.0 / Engine 29.8.1。
- 已有 Dify、Milvus、Neo4j 等容器；本项目独立端口/卷/网络，不执行删除/升级。MySQL 本地镜像实际 8.4.11；Redis 本地镜像实际 6.2.24，均按摘要锁定。
- 普通执行权限曾导致 Conda/venv、SQLite 临时文件访问失败；在正常本机执行权限下重新执行成功，没有将该环境故障误算为业务通过。

## 已执行
| 验证 | 命令 | 结果与性质 |
|---|---|---|
| 快速回归 | `.venv/Scripts/python -m pytest -q -x --tb=short` | 最终兼容锁定后 15 passed，55.87s；真实 HTTP TestClient + SQLite/Alembic；任务消费直接调用，投递失败为替身 |
| MySQL 回归 | `.venv/Scripts/python scripts/test-mysql.py` | 最终兼容锁定后 15 passed，91.56s；MySQL 8.4.11 随机独立测试库，真实迁移、外键、唯一约束；任务执行仍为直接调用 |
| 前端类型/构建 | `cd frontend; npm run build` | 通过；提示 Element Plus 打包体积较大，当前阶段可运行，后续按需拆包 |
| 实际浏览器 | `cd frontend; node scripts/smoke.mjs` | Edge 无界面真实页面：HR 建档及编辑、员工仅本人/无建档按钮、管理员账号/基础资料/审计页面均通过；无 pageerror |
| 开发库迁移与合成数据 | `alembic ... upgrade head` / `scripts/init-demo.py` | 本项目新建 MySQL 库成功；未清空任何已有用户库；密码仅保留本机忽略文件 |

自动化覆盖：S1-02 外部人才约束；S1-03 人才/文件/任务越权；S1-04 管理员无业务正文；S1-05 当前禁用及撤权；S1-06 查看/编辑范围独立；S1-07 原子版本冲突；S1-08 文件真实格式、大小、下载、路径；S1-09 幂等复用与冲突；S1-10 补发、重复消费、过期恢复、执行版本屏障、失败重试；S1-11 审计不含正文密码；S1-13 不同部门同名岗位。

## 验证边界
- 没有 OCR、LLM、Embedding、Milvus 检索或岗位匹配验证，这些不在第一阶段。
- 单元场景使用替身与直接调用；另已完成下方独立真实 Redis / Linux Worker 故障集成，二者分开计入。
- 完整系统管理界面未声称完成；阶段一授权配置可用受控 API 与合成种子。
- 没有负载/渗透测试；这是仅本机运行的阶段性交付。

## 集成排错记录
- 官方 Python 镜像首次下载发生 EOF，重试成功；未改用不明镜像。
- 首次真实 Worker 启动失败：间接依赖 Kombu 5.7.0 与 Redis 客户端 5.2.1 不兼容。固定 Kombu 5.4.2，更新完整依赖锁；本机 pip check 通过，容器重建后继续真实验证。该失败不计为集成通过。
- 角色授权增加独立 version（第二条 Alembic 迁移），完整替换授权也能检测冲突。

补强验证：两个均有业务权限的账号使用同一 Idempotency-Key，生成各自资源；定向测试 1 passed，4.26s。前端最终 build/test:browser 再次通过。

## 最终真实集成（已验证）
命令：`.venv/Scripts/python scripts/test-worker-live.py`，退出码 0。真实 MySQL 8.4.11 / Redis 6.2.24 / Linux Python 3.13.1 / Celery 5.4.0 / Kombu 5.4.2 / redis-py 5.2.1，API 在 Windows。

1. Worker 通过共享挂载读取原文件并核对 SHA-256，成功；重复发送相同任务两次，仍只有一次 attempt 和成果。
2. fail_once 首次明确失败，API 显式重试后第二版本成功。
3. 真实停止本项目 Redis，API 仍保存任务及 outbox，未标投递且 tries 增加；启动 Redis 后 dispatcher 补发成功。
4. recover_once 进入 running 后对本项目 Worker 发 SIGKILL，再启动；过期租约恢复到执行版本 2，旧 attempt 标 expired，最终成功；旧版本 finish 被拒绝。

全部场景通过，Redis/Worker 已恢复运行。未操作原有其他项目容器或卷。代码仓库公开不代表服务公开部署。阶段状态：待用户验收。

## 本轮验收反馈修复（2026-11-05）
状态：已验证，待用户验收。代码提交 dd2f141；未进入第二阶段。

| 验证 | 实际命令 | 结果与边界 |
|---|---|---|
| 修复前复现 | `.venv/Scripts/python -m pytest -q tests/test_review_fixes.py --tb=short` | 2 failed / 1 passed：空绑定 self 放行、新任务分页返回缺少 items/total；已绑定正向场景通过 |
| 修复后全量快速回归 | `.venv/Scripts/python -m pytest -q --tb=short` | 18 passed，64.75s；真实 TestClient + 独立 SQLite/Alembic |
| 修复后 MySQL 回归 | `.venv/Scripts/python scripts/test-mysql.py` | 18 passed，94.88s；随机隔离库，用后仅删除该测试库 |
| 类型与生产构建 | `cd frontend; npm run build` | 通过；保留已有包体较大提示 |
| 任务页面回归 | `cd frontend; npm run test:task-pagination` | 真实 Edge，合成 API 替身：61条四页、最后一条详情、第62条新建任务不在首页仍直达、详情独立轮询；不计作真实 Worker 验证 |
| 真实页面集成 | `cd frontend; npm run test:browser` | 无 API 替身，HR 实际上传合成 PNG、创建测试任务、直达返回编号详情、轮询至 Linux Worker 成功；员工本人范围与管理员页面通过 |

后端分页样本为61条外部+7条内部合成任务，仅用于查询测试、不投递；分别检查 HR 全范围68条、员工本人7条、管理员0条，总数与列表范围一致。self 回归同时检查未绑定和已绑定账号、无效建档403且无新增人才/幂等记录、原本人权限保留。

GET /tasks 的 data 契约从数组更新为 {items,total}；无迁移/依赖变更。API与Worker/dispatcher已载入最新代码；独立5175测试服务已关闭。本轮未重新执行 Redis 故障或 Worker 强杀测试，历史结果保留在上节。

## 第二阶段开发中实际记录（2026-11-05）
- 安全快进 main 到7dbdb86；分支codex/stage-two-resume。
- `.venv/Scripts/python.exe -m pytest tests/test_resume_reading.py -q`：7 passed；实际PDF渲染/文字提取、DOCX XML/图片读取；OCR为替身，只证明分流/定位。
- `.venv/Scripts/python.exe -m pytest -q --tb=short`：25 passed / 68.11s（当时18旧测试+7新读取测试）。普通权限首次运行18个fixture因临时库不可访问报错；以可访问独立临时库的权限重跑通过，未将初次错误算通过。
- `.venv/Scripts/python.exe -m pytest tests/test_resume_tasks.py -q --tb=short`：2 passed / 8.80s，模型替身验证并发编辑、证据隔离、幂等、超时。
- `.venv/Scripts/python.exe scripts/test-mysql.py`：27 passed /110.71s，随机独立MySQL库，真实迁移及回归，结束删除该随机测试库，开发库不清空。
- `npm --prefix frontend run build`：通过，包体提示仍在；普通执行曾因spawn EPERM失败，正常子进程权限重跑成功。`pip check`通过。
- 用户本机模型合成短文本：name/email/skill三类引用通过，缺失教育/经历标needs_review。没有输出凭据。
- `.tools/ocr-venv/Scripts/python.exe scripts/evaluate-ocr.py`：CPU Paddle3.2.0/PaddleOCR3.3.2，PP-OCRv5 mobile，合成图片4行预期/实际逐行一致。仅一个清晰样本，不外推准确率。HuggingFace下载SSL EOF后ModelScope回退成功；服务器大模型下载仍未确认成功，运行选择移动版。
- Ollama真实/api/embed，已有bge-m3返回1024维。Milvus索引写入及容器连通尚待验证。六格式实际模型评测与Worker构建进行中。

第二阶段最终逐项证据、样本错误与页面验收映射见 [stage-two-verification.md](stage-two-verification.md)。上方“开发中”段落为过程记录，当前状态以progress.md和本次最终报告为准。

## 第二阶段本轮审查修复
646a562的3项反馈修复前均复现。完整SQLite46 passed /162.30s、真实隔离MySQL46 passed /254.73s，真实Ollama/Milvus索引验证通过；细分替身、时钟和迁移证据见[stage-two-review.md](stage-two-review.md)。第二阶段仍待用户验收。
