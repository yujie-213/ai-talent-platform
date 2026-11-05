# 阶段一 API

前缀 /api；JWT 仅含 sub/exp，受保护请求重新查询账号、角色及授权。密码 PBKDF2-SHA256 随机盐，登录失败不透露账号是否存在。令牌默认 60 分钟。响应 {data, request_id}；错误 {error:{code,message},request_id}；HTTP 401/403/404/409/422/413。OpenAPI /docs 为完整字段契约。

| 方法/路径 | 输入/输出 | 当前权限 |
|---|---|---|
| POST /auth/login | username/password -> token | 无；审计成功/失败 |
| GET /auth/me | 当前账号、角色和授权（无密码） | 有效账号 |
| GET/POST /admin/users | 账号列表 / username,password,department_id | account.manage |
| PATCH /admin/users/{id} | version,enabled,role_ids,talent_id | account.manage；绑定唯一；不能禁用最后管理入口由运维负责 |
| GET/POST /admin/roles | 角色及动作范围授权 | account.manage |
| PUT /admin/roles/{id}/grants | version + 完整替换 grants | account.manage；原子版本冲突；范围校验；即时生效 |
| GET /catalog | 部门、公司岗位、部门岗位、人才库 | 有效账号；仅组织基础数据 |
| POST /catalog/{kind} | departments/positions/pools:name；department_positions:两个 FK | catalog.manage |
| GET /talents | offset/limit（<=100） -> 范围内记录及 total | talent.read |
| POST /talents | 类型、姓名、归属、联系方式、分类 facts | talent.write；Idempotency-Key 必填 |
| GET /talents/{id} | 当前档案、facts、history | talent.read 当前范围 |
| PUT /talents/{id} | 完整人工资料 + version | talent.write 旧范围及新范围；冲突 409 |
| POST /talents/{id}/files | multipart file | file.write；Idempotency-Key；校验前鉴权 |
| GET /talents/{id}/files | 文件元信息 | file.read |
| GET /files/{id}/download | attachment 字节 | file.read；禁止路径参数 |
| POST /files/{id}/test-tasks | mode success/fail/fail_once/recover_once | task.run；Idempotency-Key；202，仅验证机制；fail_once 首次失败，recover_once 首版本等待 12 秒用于强杀验证 |
| GET /tasks | offset/limit（默认50、最大100） -> {items,total}；UUID 稳定排序 | talent.read；先按当前范围过滤再分页/计数 |
| GET /tasks/{id} | 当前授权内任务及 attempts；可独立于列表页读取 | talent.read；读取时重新授权 |
| POST /tasks/{id}/retry | version | task.run；failed 且版本匹配；202 |
| GET /admin/audit | 分页元数据 | audit.read |
| GET /health | 存活状态 | 无，不泄露连接信息 |

Idempotency-Key 最长 128 字符，按账号+动作+key 唯一；摘要覆盖业务内容（上传包含原名和内容哈希）；同键同内容复用资源，同键异内容 409，复用仍重新鉴权。并发唯一键冲突由客户端安全重试，不能重复记录。版本冲突 VERSION_CONFLICT，幂等冲突 IDEMPOTENCY_CONFLICT，权限不足 FORBIDDEN，未认证 UNAUTHORIZED，资源不存在 NOT_FOUND，格式校验 VALIDATION_ERROR，唯一/关联冲突 CONSTRAINT_CONFLICT。

2026-11-05 验收修复：GET /tasks 的 data 从数组调整为 {items,total}，前端及现有调用方同步；前端每页20条，创建任务后按返回编号直接读取详情，并独立轮询尚在处理的详情。self 授权仅在账号已绑定非空人才 ID 且目标 ID 匹配时成立；无绑定的 self 不能授权建档。

## 第二阶段接口增量
- POST /api/imports/{batch_uuid}：单文件multipart，Idempotency-Key；普通上传先建待解析占位，任务完成后入档。每用户批次最多20份。接口返回逐文件task；无效上传返回明确HTTP失败。
- POST /api/files/{id}/parse：指定已有档案解析；需要该人才的task.run/file.read/talent.write；202返回task。幂等独立于机制测试。
- GET /api/tasks/{id}/extraction：重新检查人才及原文件查看范围，返回原文定位、抽取字段/异常/缺失、资料状态、启动版本。技术任务状态不等于资料完整状态。
- POST /api/tasks/{id}/resolve：action=link/exclude、target_id、version；疑似重复人工核对，关联再次检查目标权限、版本及身份冲突。
- GET /api/candidates：offset/limit、kind、skill/education/experience原文包含条件（转义SQL通配符）；授权范围先过滤再分页/计数，按name/id稳定排序。教育/经验筛选为原文包含，尚未实现数值年限筛选。

### 第二阶段补充契约
- GET /api/imports：当前用户且当前可读范围内批次ID，稳定排序最多50个（不宣称按时间最近50个）；GET /api/imports/{uuid}：当前上传者、人才/文件授权均成立的逐文件tasks及本人失败元数据和total。
- 每批20份包含失败上传，批次并发通过用户行锁和当前锁定读计数；普通导入和指定解析按用户/动作幂等。前端重试同一选择复用批次和请求键；新一批需显式新建。
- POST /api/talents/{id}/reindex，{version}：talent.write与file.read，202 pending；版本冲突409，无范围404。事件可重放，后台写入后Strong可见确认才ready。
- 候选人筛选新增sort=name_asc/name_desc/version_desc白名单；items返回tags（category/content/source_type/source_version/confirmed）、quality和当前版本index_state。分页与计数始终同范围AND条件；skill/education/experience为原文包含，SQL通配符转义。经验不是自动估算的数值年限，学历包含不是“本科及以上”语义条件。
- 解析错误包括LLM_NOT_CONFIGURED/LLM_TIMEOUT/LLM_INVALID_RESPONSE/OCR_NOT_INSTALLED/OCR_TIMEOUT/OCR_UNAVAILABLE/FILE_HASH_MISMATCH/NO_READABLE_TEXT/DOCUMENT_TEXT_LIMIT/DOCUMENT_SEGMENT_LIMIT/DOCUMENT_IMAGE_LIMIT/IMAGE_PIXEL_LIMIT/AUTHORIZATION_REVOKED。技术失败不返回供应商正文、地址或凭据；异常字段与更新建议在extraction中独立显示。
- 文件加密PDF返回PDF_ENCRYPTED，PDF页数返回PDF_PAGE_LIMIT；其他损坏/不支持为INVALID_FILE并有中文说明。10 MiB、50页、20份、2500万像素、DOCX解压50 MiB/1000条目；读取12万字符/500个片段/100张图。OCR120秒、生成模型90秒，单任务30分钟，最多3次执行。
- 指定档案解析姓名/电话/邮箱冲突标identity_conflict且不自动更新；普通导入仅按授权内联系方式提示重复，提供link/exclude人工决策。确认字段不自动覆盖；确认类别中的差异保存suggestions。解析期间人工编辑触发version_conflict，不用迟到结果回写。

任务GET列表/详情增加retryable。读取/文档限额、文件哈希冲突及撤权类永久失败拒绝直接重试（TASK_NOT_RETRYABLE，409），需要按原因重新上传或重新发起解析；模型/配置等可恢复失败在当前权限下最多3次执行。返回的解析结果包含对应run_version，重试处理中不把旧执行结果假称为新结果。
