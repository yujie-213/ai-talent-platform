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

## 第二阶段审查修复（646a562后）
原文接口先验证当前档案范围和Task/File归属一致，再加载JSON；关联后不一致的旧任务返回统一NOT_FOUND/404，不允许继续执行、重试或核对。批次统计/历史过滤同一当前来源边界。field_states现在也返回5个事实类别确认记录，空集合保留；本轮无请求体结构变更。索引重建接口响应不变，重建会重排到期时间并使旧领取失效。


## 第三阶段首批：岗位需求（2026-11-06）
- GET /api/requirements：offset/limit，返回{items,total}，按requirement.read当前范围过滤。
- POST /api/requirements：完整或不完整草稿；必须选department_position_id；Idempotency-Key必需，201。
- GET /api/requirements/{id}：当前草稿、状态、编辑/有效版本及完整versions快照。
- PUT /api/requirements/{id}：完整草稿及version，只改草稿，部门岗位不可更换，冲突409。
- POST /api/requirements/{id}/activate：{version,confirmed:true}；验证必填、追加独立快照并切换有效版本，不自动创建匹配。
- POST /api/requirements/{id}/disable：{version}，只允许当前有效状态，保留历史。
新增requirement.read/write独立动作，global或department范围；管理员不默认授权。新建及变更同时要求目标需求读写权限，不从人才权限借权。字段、示例、部署和剩余范围见stage-three.md。JD辅助与匹配接口已在后续条目补齐。


S3-02：POST /api/requirements/assist接受{mode:extract|improve,draft,requirement_id?,version?}，已保存需求必须同时传ID/版本。draft新增可选jd_text（≤20000）。返回{suggestions:[{field,value,quote,source:jd|proposal}],issues,mode,version}；仅建议，不保存。前后两次当前鉴权/版本校验；模型不可用503安全错误，手工流程继续。详细字段白名单和校验限度见stage-three.md。


## 第三阶段完整匹配接口（2026-11-06）

- POST /requirements/{id}/matches（202，Idempotency-Key）：{version,include_internal:false,selected_ids:null,skill:"",rules:{evidence_weight:50,preferred_weight:20,semantic_weight:30}}。[]为空范围，默认全授权外部，可选内部排除目标部门；需求当前读写及人才read/task.run交集，任务同事务建立独立匹配outbox。
- GET /requirements/{id}/matches：历史{items,total}，offset/limit默认20最多100。GET /matches/{id}：状态/业务结果/当前可见进度/attempts/需求状态与过期/规则和需求快照。
- GET /matches/{id}/results：同样分页，group为pass/unknown/fail/failed/pending或空；逐人才当前talent.read过滤；结果含快照、检查/证据、真实分数、profile_stale。原文引用另查当前file.read及文件/任务归属。执行失败不冒充完整分数。
- POST /matches/{id}/retry（202）：{version}为执行版本，仅发起人且当前需求读写；保持快照与成功条目，仅重试可恢复失败，最多3次执行。
- PUT /requirements/{id}/talents/{talent_id}：{talent_version,linked}，读写两侧、冲突409；幂等显式应聘关联，匹配不自动关联。
- GET /candidates新增requirement_id，仅筛选显式关联者，requirements数组只显示所选需求；默认仍含未关联人才。每项含score/group/state、需求版本、生成时间、过期和当前需求状态。
- Conditions新增skill_experience_years，例如{"Python":3}，只能引用必备技能。它与minimum_experience_years（总年限）分开；缺时间不推断。JD辅助白名单同样支持该字段，须明确技能时间引用。

详情、错误规则、可靠恢复和示例语义见stage-three.md；实际验证见stage-three-verification.md。需求状态/编辑冲突/幂等冲突均409；缺字段/优先级矛盾422，CONDITION_CONFLICT会提示统一正文与结构；越权记录404；JD外部模型失败503且保留原文/手工流程。


第三阶段年限审查补充：规则v3，GET /matches/{id}及/results新增rules_stale，候选人requirements同样标rules_stale/stale；旧规则任务重试409 RULE_VERSION_CHANGED。旧结果不回写，需核对旧需求后新建。JD年限引用必须在完整原文中核对总/技能归属、边界及引用数值；上界/区间/严格下界不能悄悄压成整型最小值。见stage-three-review.md。


## 第四阶段测评及管理增量
所有路径前缀/api。新增动作assessment.manage仅global（题库/试卷）；assessment.assign与assessment.read沿用人才范围并与talent.read取交集；管理员不因身份自动获得上述动作。chat.use遵守人才范围，已实现接口见下一节。

- GET/POST /assessments/questions；PUT /questions/{id}带version，维护题干、kind(single/multiple/boolean)、选项{id,text}、correct选项ID集合、dimension、points(1~100)、enabled。管理投影含答案，非管理员工拒绝。
- GET/POST /assessments/papers：发布{title,question_ids,paper_id?,version?}，POST带Idempotency-Key，旧快照不可修改；再次发布产生新版本。
- GET /assessments/published-choices：仅分配动作可用，只返回版本ID/标题/版本号，无标准答案；GET /employees：仅当前人才读权及分配范围内已启用绑定内部员工。
- GET /assessments/assignments?offset=0&limit=20&talent_id=可选：{items,total}，本人当前绑定或HR测评读权与人才读权交集。POST带幂等键及{paper_version_id,employee_id}。
- GET /assessments/assignments/{id}：题目公开投影、草稿/已锁定答案、状态及成绩，不含标准答案。PUT /{id}/draft、POST /{id}/submit均为{version,answers:{题目ID:[选项ID]}}，仅当前绑定本人可写；未答计零分，非法题目/选项422，版本冲突409，已提交修改409。重复相同提交返回原记录。提交先原子锁定并提交事务，再评分。
- POST /assessments/assignments/{id}/score：当前有访问权者可恢复submitted任务评分，保留原始答案，完成后唯一成绩；并不允许重交。评分失败状态仍submitted，error_code=SCORING_FAILED。
- GET /workbench：当前授权下真实人才、解析任务、本人匹配明细及测评任务统计，同时返回definitions说明各口径。没有编制/缺口或演示数字。
- PATCH /catalog/{kind}/{id}：{version,enabled}，catalog.manage全局，条件更新，保留历史；无删除接口。

原有/admin/users、/admin/roles及grants接口由真实页面复用。完整聊天/语义任务/流式与AI调用日志接口见下一节。


## 第四阶段统一聊天、日志及完整管理接口
所有路径前缀/api。chat.use使用人才数据范围，并与talent.read同时满足；系统管理员不自动获得。以下接口均检查当前账号及有效权限，撤权/禁用对旧JWT、会话、引用及检查点生效。

- GET/POST /chat/conversations：GET分页{items,total}；POST带Idempotency-Key及{kind:selected|filtered|authorized,ids?,filters?}。filters只接受kind/skill/education/experience，复用当前页面原文筛选语义。后端固定实际人才ID；selected空数组为空，不能扩大。
- GET /chat/conversations/{id}：本人且当前仍有全部会话范围权限；历史各轮引用再次检查来源权限/归属，不直接返缓存敏感回答。
- POST /chat/conversations/{id}/messages（202）：幂等键及{version,question,confirm:false}；同会话活动任务互斥，返回持久job。明确待确认计划使用confirm=true；这不是普通技能逐条确认。追问继承结构条件与已明确语义判据；取消/松开条件和扩大范围需确认。
- GET /chat/jobs/{id}：技术状态、run_version、范围、计划、回答、逐人结果/版本/过期、覆盖进度及attempts。检索未列入结果的人不计作已完成语义评估；完整语义人数逐人处理，不用top-k数量当总数。
- GET /chat/jobs/{id}/events?offset=0：带Bearer的SSE。progress输出真实覆盖进度，entry输出已验证且当前授权的逐人结果，chunk输出已验证汇总文本，done/reconnect/revoked控制连接。offset是已接收字符位置；重连只读同一任务，不创建新消息或任务。不是未经校验的模型token透传。每个输出块重新鉴权。
- POST /chat/jobs/{id}/retry（202）：{version}，最多3个执行版本，只重试可恢复失败，成功条目不重做；撤权及恢复耗尽不可直接重试。
- GET /chat/jobs/{job}/entries/{entry}/citations/{fact}：人才/事实/来源/位置/版本，必须属于该条目实际证据；人工事实返回人工记录，不伪造文件。文件原文仍通过既有受控任务/文件接口。

Plan仅允许intent、kind、skill、education(eq/ge)、years(ge/gt)、skill_years与skill_years_op、semantic、criteria、clarification、expand；所有数值/枚举/长度受限，任意SQL、函数名、写操作参数均拒绝。years是总工作经验，skill_years使用独立技能时间证据；未知不计符合，不借总年限。最高已完成学历精确等值与至少区分，“超过”严格大于。上界/区间、无法表达的复杂条件保守澄清，不擅自反转。模型JSON偶发不合schema只允许一次受控修复，仍完整白名单及权限校验。

管理补齐：GET /admin/menu-options；PUT /admin/roles/{id}/menus={version,menus}（account.manage）；GET /admin/binding-choices?q=&offset=&limit=为账号绑定提供最小姓名/人才ID/身份/部门元数据，不能读取联系方式或正文；GET /admin/user-page返回带角色、绑定姓名的账号分页，UserUpdate可显式修改department_id；未提供部门保持原值。
GET /admin/logs/audit及/ai返回{items,total}，支持offset/limit、action包含与state精确筛选，audit.read；没有正文查看或日志编辑接口。PATCH /catalog/{kind}/{id}除启停外可条件更新名称，部门岗位关联身份不可变。菜单显示配置不替代功能撤权，撤权仍通过grants。
