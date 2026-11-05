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
