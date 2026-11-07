# 本机部署、备份与恢复

适用Windows学习电脑，服务只监听本机。第五阶段验证覆盖现有环境启停、锁定依赖检查、真实数据库/文件备份和隔离恢复；不等同于已验证公网生产部署或另一台机器全新安装。版本及实际结果见stage-five-verification.md。

## 运行组成与数据位置

API和Vue在Windows运行；MySQL、Redis、Worker、dispatcher、indexer由既有 `ai-talent-stage1` Compose项目管理。Milvus/Ollama沿用本机已有部署，不在本项目创建第二套。MySQL是人才/账号/权限/任务/历史/检查点/评分的权威源；Redis只投递任务，Milvus只存可重建向量。

- `.env`：本机连接和秘密配置，另行保存在安全位置，不入Git，不贴聊天。
- MySQL命名卷：权威数据库；`data/files`：默认受保护原文件，实际以本机FILE_ROOT配置为准，两者必须一起备份。
- OCR命名卷/本机缓存与Ollama模型：模型资产，不包含在业务备份中；保留既有版本和摘要，不自行升级。
- `data/backups`：数据库导出、原文件副本和校验清单，均被Git忽略；本机同盘副本不具备防磁盘损坏能力，应按自己的保密要求保管离线副本。
- `data/stage-five`：本轮报告和隔离恢复文件；它们不是业务权威源。

部署复现应同时固定Git提交、`backend/requirements.lock.txt`、OCR锁文件、`frontend/package-lock.json`及镜像。基础Python/MySQL/Redis在infra中固定摘要，后台沿用 `ai-talent-stage4-backend:0.4.0` 的既有依赖。Compose挂载当前backend源码，切换分支后需要重载API和本项目后台进程，不能只凭镜像标签认为代码相同。`Dockerfile.stage4`依赖本地0.2.1基础镜像，另一台机器必须先按 `Dockerfile.stage2` 构建基础，再构建stage4；本轮没有重新拉取/升级基础服务或声称验证了全新主机。

## 已有环境启动与检查

先打开Docker Desktop并等待引擎就绪。PowerShell从任意目录开始均先执行完整路径，路径不同则替换：

```powershell
Set-Location -LiteralPath 'D:\AI数字化人才平台\AI 数字化人才平台'
docker compose --project-name ai-talent-stage1 --env-file .env -f infra/compose.yml -f infra/compose.stage2.yml -f infra/compose.stage4.yml start mysql redis worker dispatcher indexer
./scripts/reload-local-api.ps1
npm.cmd --prefix frontend run dev
```

首次或依赖锁文件变动后先 `npm.cmd --prefix frontend ci`；Python依赖变动后才安装锁文件。本阶段没有依赖或数据库迁移变化，不需重装依赖、迁移、bootstrap或seed。API重载脚本只停止能确认属于当前项目的进程，并等待health200才报告就绪；日志在忽略目录 `data/frontend-rebuild`。前端保持终端打开，停止用Ctrl+C。浏览器访问 <http://127.0.0.1:5173>。

另开PowerShell，切换项目根目录后运行：

```powershell
.venv/Scripts/python.exe scripts/check-local.py
```

逐项检查真实数据库及迁移head、Redis、API、前端代理、五个项目容器、真实Embedding维度/摘要、Milvus集合和本机OCR解释器。生成API只报告是否配置，不以自检宣称模型可用；真实OCR/抽取/问答效果使用本阶段评测。完整自检输出到 `data/stage-five/readiness.json`，任一必需项失败会非零退出。`/api/health`仅表示API存活，不代替数据库或业务检查。

新环境安装/增量升级仍按README第四阶段部署步骤显式执行Alembic；先备份，在维护窗口运行，不在应用启动时自动迁移。生成模型端点、凭据、Ollama摘要和已有Milvus部署均需由本机配置提供，不能从公开仓库恢复秘密。Windows隔离OCR环境按OCR锁文件安装；容器已包含 `/opt/ocr` 独立环境。

## 离线备份

先暂停本项目操作，确认没有排队/运行中的解析、匹配和聊天任务。停止所有连接此库的写入脚本；下面只停止本项目API及三个后台进程，数据库和Redis保留。命令均在项目根目录，失败也要执行finally恢复。

```powershell
try {
    ./scripts/stop-local-api.ps1
    docker stop ai-talent-stage1-worker-1 ai-talent-stage1-dispatcher-1 ai-talent-stage1-indexer-1
    if ($LASTEXITCODE -ne 0) { throw '停止后台失败' }
    .venv/Scripts/python.exe scripts/backup-local.py backup
    if ($LASTEXITCODE -ne 0) { throw '备份未完成，请检查' }
} finally {
    docker start ai-talent-stage1-worker-1 ai-talent-stage1-dispatcher-1 ai-talent-stage1-indexer-1
    ./scripts/reload-local-api.ps1
}
```

备份脚本发现8000仍监听或项目后台仍运行会拒绝继续。离线期间导出MySQL、复制原文件，核对前后行数及原文件SHA-256，成功才写manifest。密码仅在容器内使用已有环境变量，不进入宿主命令参数或输出。失败留下的无manifest目录不能当成成功备份。

业务备份不包含`.env`、OCR/Embedding权重、容器镜像。它们须单独保管，尤其数据库密码、JWT密钥和模型配置；避免把配置或真实资料提交Git。没有自动删除历史备份或自动覆盖旧备份。

## 隔离恢复演练

把路径换成上一命令实际返回的备份目录：

```powershell
.venv/Scripts/python.exe scripts/backup-local.py restore-test --backup 'D:\AI数字化人才平台\AI 数字化人才平台\data\backups\实际备份目录'
```

先校验导出和文件哈希，再创建随机 `talent_restore_*` 隔离库，导入全部表；文件恢复到新的 `data/stage-five/restore/UUID` 路径。验证表行数、每个文件SHA-256，以及隔离应用真实登录/工作台/候选人读取。finally仅删除刚生成的随机演练库，保留恢复文件作证据；绝不覆盖开发库或原文件。脚本识别恢复库中的当前`zhou.yan`或原`demo.hr`，从本机私有凭据读取密码；本轮只改名保留密码，因此可验证替换前的备份。不含上述账号的其他数据库仍需另行适配授权验证账号，不能照搬并宣称验证通过。

真实灾难恢复须在确认目标、备份完整性和配置可用后另行实施，本工具只提供无覆盖演练。MySQL/文件可恢复后，按当前版本重建向量；Redis丢失不丢权威任务，dispatcher从MySQL outbox补投。禁止 `down -v`、删卷、对已有库重seed或直接复制未停写的MySQL卷冒充一致性备份。

## 索引清理与数据保留

原文件、历史任务、匹配快照、会话、检查点、审计和测评成绩保留，不自动清除业务资料。停用账号/基础资料也不删除人才历史。建立个人/组织的数据保留期限后再单独设计授权删除流程，当前版本不提供无差别清空。

向量可以清理已过时版本。项目根目录执行：

```powershell
$env:PYTHONPATH = Join-Path $PWD 'backend'
.venv/Scripts/python.exe -m app.cli index-cleanup --limit 100
```

仅按权威库当前人才ID删除严格小于读取时资料版本的向量，不删除当前/未来版本、集合、模型或业务记录。返回examined/cleaned_profiles/failed_profiles及next_after。存在失败会非零退出，应从原游标重试；整批成功后才用 `--after 上一批next_after` 继续。清理按人幂等；它不是权限撤销机制，检索仍必须实时校验权限和当前版本。索引补偿、清理失败均不应掩盖为已就绪。

## 限制

本轮是单机开发部署和恢复演练，未验证跨主机迁移、长期运行、灾备切换、磁盘故障、TLS公网入口或大规模负载。API和Vite开发服务器不是公开生产入口。备份演练可读不等同于恢复时间承诺；效果与性能数字只对应本轮合成数据及当时机器负载。
