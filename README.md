# AI 数字化人才平台

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
cd frontend
npm run build
npm run test:browser
```

快速回归使用独立临时 SQLite；MySQL 回归创建随机 `talent_test_*` 测试库，结束只删除该库，绝不清空开发库。任务单元用例直接调用消费者和模拟失败投递器，不能替代真实 Celery 验证。浏览器回归依赖本机 Edge、已启动 API/前端及合成账号，会新增带“浏览器合成”前缀的演示人才，截图仅存本机 data。详细实际结果与集成验证入口见 `docs/verification.md`。

## 代码与业务链

`backend/app/main.py` 接收请求 → `api/routes.py` 校验 HTTP 入参和响应 → `services/application.py` 编排业务与事务 → `repositories/access.py` 统一授权查询；`core/security.py` 每次重新加载当前授权。人工档案通过原子版本更新，修改与历史同事务保存。文件访问跟随人才的当前权限，不提供静态文件地址。

创建测试任务时，同事务写入 `tasks/outbox` → 独立 dispatcher 投递 Redis → Linux Celery Worker 条件领取 → `attempts` 记录执行 → 当前授权及执行版本校验后保存结果。投递失败保留 outbox；过期运行由 dispatcher 恢复或明确失败；重复消息和旧执行无法再次提交成果。

设计见 `docs/schema.md`、`docs/api.md`；交接入口 `docs/progress.md`、`docs/handoff.md`。前端为 Vue 3 / TypeScript / Element Plus。完整 V1 规划仍见 `docs/plan.md`，不自动进入第二阶段。
