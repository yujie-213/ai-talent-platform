# 第五阶段验证记录

2026-11-07（北京时间）。用户已验收第四阶段并授权第五阶段；本轮实现及下列验证已完成，待用户验收。分支 `codex/stage-five-acceptance`，基线 `8943d6e`，启动文档 `6f4a174`，代码提交 `2259b35`；最终文档HEAD以git log为准。报告、截图、备份仅保存在忽略的data目录，不含入Git的真实资料或凭据。

## 本次修复和业务链

- 同键并发首次建档：两个请求均未查到幂等记录时，原实现第二个提交遇唯一冲突返回409。新增 `business.commit_or_replay`，在唯一冲突后结束原事务，再查同用户/动作/键并核对内容，返回原成果；非幂等冲突仍抛出。接入建档、文件上传及机制任务；上传败方只删除自己刚写的临时文件。关键测试强制同步首次查询，使用真实数据库，不用假成功结果。
- 聊天指代：`其他条件`中的`他`被误判成单人指代。修正限定条件，仍对多成员范围中的单人`他`要求澄清；`他们`和`其他条件`不误拦。真实Redis恢复脚本首先暴露该问题，修复后完整恢复通过。
- 工作台性能：历史聊天逐轮查询当前会话/成员权限，测评两次读取全部明细，产生大量重复SQL。`chat_access.visible_conversations`在一次请求内批量核验所有固定成员的talent.read/chat.use交集及筛选岗位读权，不保存跨请求授权缓存；会话列表和工作台共用。测评列表与统计共用 `visible_assignment_clause`，本人当前绑定和测评/人才读权规则保持一致，数据库分页/分组。不把部分可见会话算作完整可见，撤权后立即重算。
- 旧向量清理：新增本机 `app.cli index-cleanup`，只对权威人才ID删除严格小于读取时版本的向量；不删除当前/未来版本、业务事实、集合或模型。分批游标、逐人失败和非零退出可核对，重试幂等。真实Milvus验证v1已清理、v2仍可查询。
- 运维：API重载等待health200后才报告就绪；停止脚本检查端口进程确属本项目；自检分别验证数据库迁移、队列、API/前端代理、容器、Embedding和Milvus。新增离线备份及随机隔离库恢复演练，完整说明见deployment.md。
- 旧恢复脚本修正为第四阶段配置，并以start恢复已存在容器，避免故障测试把Worker降级为第二阶段镜像。界面仅增加会话ID定位属性，无视觉或业务交互重构；聊天浏览器脚本按ID定位，并正确读取折叠诊断中的任务编号。

没有新增数据库迁移、依赖、评分规则或权限语义，没有重seed或删除用户数据，没有公开部署或合并main。

## 环境和回归

沿用Windows项目Python3.13.5、Node24.21.0、Vite6.0.5、Playwright1.65.0/本机Edge，已有Docker Linux/MySQL/Redis/Milvus/Ollama及第四阶段后台镜像。`pip check`无依赖问题。完整测试使用临时SQLite或随机 `talent_test_*` MySQL库，每例真实迁移；模型/Embedding替身的边界用例与真实模型脚本分开记录。

| 命令（项目根目录） | 实际结果 | 本机证据 |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m pytest -q --tb=short -p no:cacheprovider` | 基线177通过，601.02秒；最终变更另做相关模块回归，不将轮次累加为全套数量 | `data/stage-five/pytest-sqlite-normal.log` |
| `.venv/Scripts/python.exe scripts/test-mysql.py` | 基线177通过，1702.09秒；随机隔离库已清理 | `data/stage-five/pytest-mysql.log` |
| `pytest -q tests/test_stage_five.py tests/test_additional.py tests/test_stage_one.py --tb=short -p no:cacheprovider`（使用项目Python） | SQLite21通过/131.80秒；同参数test-mysql.py真实MySQL21通过/369.75秒，之后还补充了上传清理/批量授权/指代用例 | `fixes-sqlite.log`、`fixes-mysql.log` |
| `pytest -q tests/test_stage_five.py tests/test_assessments.py tests/test_frontend_rebuild.py tests/test_archive_chat.py tests/test_chat_review.py --tb=short -p no:cacheprovider`（使用项目Python） | 最终相关模块SQLite43通过/264.39秒；同参数真实MySQL43通过/577.50秒；最后清理响应校验后定向SQLite2通过/12.89秒 | `final-boundaries-sqlite.log`、`final-boundaries-mysql.log`、`cleanup-final.log` |
| `npm.cmd --prefix frontend run build` | 首轮及最终定位属性变更后重跑均通过，最终Vite构建13.54秒 | `build.log`、`build-final.log` |
| `.venv/Scripts/python.exe scripts/check-local.py` | 数据库迁移、Redis、API、前端代理、容器、真实Embedding、Milvus及OCR解释器检查均成功；生成API仅检查配置，真实调用另列 | `readiness.json` |

最初受限环境SQLite无法打开临时测试库，得到81通过/96个fixture错误；这是执行环境失败，正常权限重跑177通过，不把首轮冒充成功。`starlette.testclient`存在既有AnyIO弃用告警；前端构建存在既有大包告警，均未隐藏。

## 真实异常恢复

故障开始前，开发库Task/MatchRun/ChatJob的queued/running计数均为0。以下脚本按顺序执行，只停止本项目Redis或强杀本项目Worker，finally恢复原容器；不同时运行其他故障脚本。

| 命令（使用项目Python） | 结果 |
| --- | --- |
| `scripts/test-worker-live.py` | 真实共享文件机制任务、重复消息不重复尝试、失败重试、Redis停机outbox补投、SIGKILL租约恢复v2及旧成果屏障通过；机制任务明确不声称OCR |
| `scripts/verify-stage-three-live.py` | 真实JD模型建议、筛选外部5人逐人分组、含内部6人/排除目标部门、真实bge-m3/BM25/RRF、应聘关联、Redis补投、匹配强杀恢复v2、重复/旧执行、资料/需求历史及空范围通过 |
| `scripts/test-resume-recovery-live.py` | 真实OCR/生成模型解析期间强杀，租约恢复run_version2，原尝试expired，新抽取可读，旧消息不新增尝试通过 |
| `scripts/verify-chat-recovery-live.py` | 首轮被`其他`指代误判阻止，修复后真实Redis补投、LangGraph检查点后强杀、租约恢复v2、原尝试expired、新尝试succeeded、3条唯一成果、旧finish和重复消息拒绝均通过 |

日志在 `data/stage-five/*live.py.log` 和 `chat-recovery-fixed.log`；聊天恢复结构报告在 `data/stage-four/chat-recovery.json`。没有把通过恢复等同于大规模故障或长时间稳定性证明。

模型不可用新增验证使用实际HTTP连接拒绝（仅测试进程将生成入口指向本机不可达地址），不替换模型函数，不修改运行中API/Worker配置。解析明确 `LLM_INVALID_RESPONSE` 失败且档案版本/事实不改；答案整理仅回退已核验证据并保留引用。单测中的其他模型/Embedding替身用于确定性权限和并发边界，不能代替上述真实HTTP或真实模型验证。

## AI实际效果基线

命令依次为：隔离OCR解释器运行 `scripts/evaluate-ocr.py`；项目Python运行 `scripts/evaluate-resumes.py`、`scripts/verify-chat-live.py`、`scripts/verify-chat-review-live.py`、`scripts/verify-chat-file-live.py`、`scripts/evaluate-jd.py`、`scripts/verify-stage-three-live.py`、`scripts/evaluate-matching.py`，最后运行 `scripts/summarize-stage-five-ai.py`。其中verify-stage-three-live含真实故障，不能与其他故障脚本并行。报告记录来源修改时间，重跑汇总前必须先重跑所需来源脚本，避免引用陈旧报告。

全部为合成资料，8种格式重复使用少数原文，不是8份独立真实人群样本；标注项是类别+具体原文目标，命中采用同类别连续文字包含，不能当作整份简历完全正确率。

| 能力 | 本轮实际结果 | 边界 |
| --- | --- | --- |
| OCR | 1张清晰合成中文图，4/4行精确一致；去空白后51字符编辑距离0 | 未代表低清、手写、复杂多栏或真实扫描件 |
| 字段抽取 | 8格式、41个固定标注项命中40个；各格式读取及模型调用完成 | text.pdf中`Python Engineer`头衔未抽成Python技能，仍作为漏项保留；不可通过改标注或补固定答案抹平 |
| 引用约束 | 已接纳字段均满足原文引用校验，本轮无校验拒绝项 | 这是后置校验的可追溯性，不是原始模型精确率或零幻觉证明 |
| 结构人数/年限 | 3人范围中本科且至少3年/Python声明=1；后续超过3年=0；技能年限明确为0支持/3不足 | 解释性否定问题一次保守澄清，另用明确正向问题验证独立技能年限；不把未知当0年 |
| 语义人数 | 人工判据支持1人；覆盖3/3，模型核对支持1，其余按不足/相反证据区分 | 必须先确认完整判据，样本仅3人 |
| 语义检索 | 同3人标注范围，支持结果TP/FP/FN=1/0/0 | 仅当前找到，不将top-k数量当全库人数 |
| 直接问答/比较 | 2份学校/技能合成档案，学校直接答案、具体共同点/差异及逐人引用通过 | 不是开放领域问答准确率 |
| DOCX原文件链 | 真实导入/解析→档案→聊天→来源位置→下载SHA-256一致 | 仅合成文档，不代表所有版式 |
| JD | 3份样本；完整样本9项建议，漏任职要求正文description；稀疏样本未编企业岗位/地点/薪资/福利，技能年限样本命中 | 继续要求人工确认，未虚构100%抽取率 |
| 匹配 | 3份文本排序为relevant/partial/unrelated；5份硬条件标注分组全部一致；真实无附加筛选外部范围73人，65完成评分，8条PROFILE_EMPTY明确失败，pending0 | 全范围outcome=partial，不能说73人全部成功评分；8条是已有合成空档案，不能给无资料档案编分数 |

统一报告 `data/stage-five/ai-baseline.json`。匹配分数仍为规则/证据/语义排序参考，不是录用概率；测评成绩不加入匹配。

## 浏览器与性能

本机Edge：`npm.cmd --prefix frontend run test:frontend-rebuild`、`test:task-pagination`使用明确合成API验证布局/边界，均通过；不能作为真实后端/模型证据。

真实API/数据库/Worker/模型页面依次完成 `test:browser`、`test:assessment-live`、`test:management-live`、`test:resume-live`、`test:stage-three-live`、`test:chat-live`、`test:chat-review-live`、`test:chat-late-response`。迟到响应脚本只延迟真实传输，不伪造模型成果。最后 `test:frontend-rebuild-live` 验证筛选范围/学校/来源/返回、数值条件及最近匹配直达通过。最终聊天日志使用 `browser-test-*-final.log`，早期失败/重试日志保留，不冒称一次全部通过。

聊天浏览器首轮失败不是丢失历史：任务编号位于折叠诊断，旧脚本用innerText看不到编号，误去点击当前轮次不存在的“查看本轮”按钮；改为textContent，并按会话ID定位/核验读取ID后通过。上传清理新增用例首轮错误地把此前用例遗留的临时文件也计入，已改成只统计本次新增文件，保留先前文件不删。

真实 `scripts/verify-stage-five-live.py` 经前端代理验证同键2并发只产生一个人才、同键不同内容409、同版本2并发为200/409、管理员/员工读取新外部人才404。工作台各20次串行和4并发，结果如下，均为本机有其他回归负载时的观测，不是容量/生产压力测试：

| 指标 | 优化前 | 优化后 |
| --- | ---: | ---: |
| 串行p50 | 3615.24ms | 223.37ms |
| 串行p95 | 4195.69ms | 284.88ms |
| 4并发p50 | 9007.71ms | 533.07ms |
| 4并发p95 | 11172.32ms | 590.01ms |

报告 `api-performance-before.json` / `api-concurrency-performance.json`。改变的是重复数据访问方式，权限语义通过原单会话逐个鉴权与新批量结果的等价、局部撤权、岗位读权撤销、全部聊天撤权测试核对，没有牺牲鉴权换时延。

## 持久化与恢复演练

真实离线停止本项目API/worker/dispatcher/indexer，MySQL/Redis保留；`scripts/backup-local.py backup`导出数据库和原文件并验证SHA-256后生成manifest；finally恢复服务。`restore-test --backup 实际目录`在随机 `talent_restore_*` 库及独立恢复目录导入，验证42张表行数、34个文件SHA-256和隔离登录/工作台/候选人读取，通过后仅删除随机恢复库。源库和原文件未覆盖。备份目录在忽略的 `data/backups`，恢复报告在 `data/stage-five/restore-test.json`。

恢复测试的业务读取使用本机已有合成HR账号；不声称它可直接验证任意不含该账号的生产备份。备份不包括.env、模型/缓存或镜像，它们需安全单独保存；本机同盘副本不是异地灾备。没有自动删除历史记录、资料或备份；数据保留、清理游标和恢复流程见deployment.md。

## 尚未验证与验收步骤

尚未验证跨主机全新部署、公网TLS/反向代理、长时间运行、磁盘损坏、规模负载及代表性真实人群AI准确率。前端聊天历史选择器当前载入最近100条，长期会话很多时需完善分页导航；后台仍分页鉴权，历史没有删除。前端大包/AnyIO弃用警告仍保留。上述边界不以单机通过或合成命中率掩盖。

第五阶段本轮工作已完成、待用户验收，未自行标记用户已验收。前端5173/API8000及五个项目容器已恢复，最终自检再次通过，随机测试/恢复库已由脚本清理。用户可先按README启动、自检；再核对HR筛选→画像/问答/来源、岗位→匹配/解释/返回、员工测评、管理员管理隔离；按deployment.md执行已有环境重启与不覆盖的恢复演练。任何失败凭追踪编号查忽略日志，不粘贴账号、密钥或真实资料。
