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
| 快速回归 | `.venv/Scripts/python -m pytest -q -x --tb=short` | 初版 11 passed，50.97s；真实 HTTP TestClient + SQLite/Alembic；任务消费直接调用，投递失败为替身 |
| MySQL 回归 | `.venv/Scripts/python scripts/test-mysql.py` | 初版 11 passed，70.95s；MySQL 8.4.11 随机独立测试库，真实迁移、外键、唯一约束；任务执行仍为直接调用 |
| 前端类型/构建 | `cd frontend; npm run build` | 通过；提示 Element Plus 打包体积较大，当前阶段可运行，后续按需拆包 |
| 实际浏览器 | `cd frontend; node scripts/smoke.mjs` | Edge 无界面真实页面：HR 建档及编辑、员工仅本人/无建档按钮、管理员账号/基础资料/审计页面均通过；无 pageerror |
| 开发库迁移与合成数据 | `alembic ... upgrade head` / `scripts/init-demo.py` | 本项目新建 MySQL 库成功；未清空任何已有用户库；密码仅保留本机忽略文件 |

自动化覆盖：S1-02 外部人才约束；S1-03 人才/文件/任务越权；S1-04 管理员无业务正文；S1-05 当前禁用及撤权；S1-06 查看/编辑范围独立；S1-07 原子版本冲突；S1-08 文件真实格式、大小、下载、路径；S1-09 幂等复用与冲突；S1-10 补发、重复消费、过期恢复、执行版本屏障、失败重试；S1-11 审计不含正文密码；S1-13 不同部门同名岗位。

## 验证边界
- 没有 OCR、LLM、Embedding、Milvus 检索或岗位匹配验证，这些不在第一阶段。
- 模拟过期租约恢复证明数据库恢复机制；真实容器进程强杀/重启及 Broker 中断需单独集成记录，不以单元测试冒充。
- 完整系统管理界面未声称完成；阶段一授权配置可用受控 API 与合成种子。
- 没有负载/渗透测试；这是仅本机运行的阶段性交付。
