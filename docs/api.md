# 阶段一 API

前缀 /api；JWT 仅含 sub/exp，受保护请求重新查询账号、角色及授权。密码 PBKDF2-SHA256 随机盐，登录失败不透露账号是否存在。令牌默认 60 分钟。响应 {data, request_id}；错误 {error:{code,message},request_id}；HTTP 401/403/404/409/422/413。OpenAPI /docs 为完整字段契约。

| 方法/路径 | 输入/输出 | 当前权限 |
|---|---|---|
| POST /auth/login | username/password -> token | 无；审计成功/失败 |
| GET /auth/me | 当前账号、角色和授权（无密码） | 有效账号 |
| GET/POST /admin/users | 账号列表 / username,password,department_id | account.manage |
| PATCH /admin/users/{id} | version,enabled,role_ids,talent_id | account.manage；绑定唯一；不能禁用最后管理入口由运维负责 |
| GET/POST /admin/roles | 角色及动作范围授权 | account.manage |
| PUT /admin/roles/{id}/grants | 完整替换 grants | account.manage；范围校验；即时生效 |
| GET /catalog | 部门、公司岗位、部门岗位、人才库 | 有效账号；仅组织基础数据 |
| POST /catalog/{kind} | departments/positions/pools:name；department_positions:两个 FK | catalog.manage |
| GET /talents | offset/limit（<=100） -> 范围内记录及 total | talent.read |
| POST /talents | 类型、姓名、归属、联系方式、分类 facts | talent.write；Idempotency-Key 必填 |
| GET /talents/{id} | 当前档案、facts、history | talent.read 当前范围 |
| PUT /talents/{id} | 完整人工资料 + version | talent.write 旧范围及新范围；冲突 409 |
| POST /talents/{id}/files | multipart file | file.write；Idempotency-Key；校验前鉴权 |
| GET /talents/{id}/files | 文件元信息 | file.read |
| GET /files/{id}/download | attachment 字节 | file.read；禁止路径参数 |
| POST /files/{id}/test-tasks | mode success/fail | task.run；Idempotency-Key；202，仅验证机制 |
| GET /tasks /tasks/{id} | 当前授权内任务/attempt | talent.read；读取时重新授权 |
| POST /tasks/{id}/retry | version | task.run；failed 且版本匹配；202 |
| GET /admin/audit | 分页元数据 | audit.read |
| GET /health | 存活状态 | 无，不泄露连接信息 |

Idempotency-Key 最长 128 字符，按账号+动作+key 唯一；摘要覆盖业务内容（上传包含原名和内容哈希）；同键同内容复用资源，同键异内容 409，复用仍重新鉴权。并发唯一键冲突由客户端安全重试，不能重复记录。版本冲突 VERSION_CONFLICT，幂等冲突 IDEMPOTENCY_CONFLICT，权限不足 FORBIDDEN，未认证 UNAUTHORIZED，资源不存在 NOT_FOUND，格式校验 VALIDATION_ERROR，唯一/关联冲突 CONSTRAINT_CONFLICT。
