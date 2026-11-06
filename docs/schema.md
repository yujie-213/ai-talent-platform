# 阶段一数据库设计

MySQL 8.4，utf8mb4；SQLAlchemy 2；Alembic 显式迁移，不随应用启动建表。SQLite 仅作快速自动化测试。ID 为随机 UUID 字符串，时间统一 UTC 秒。禁止业务硬删除组织、账号、人才、文件、任务和审计。

| 表 | 关键字段 / 关系 / 索引 |
|---|---|
| users | username 唯一，password_hash，enabled，version，talent_id 可空唯一 FK，department_id FK |
| roles / user_roles | 名称唯一，角色 version 原子检测授权配置冲突；账号角色联合主键 |
| grants | role_id FK，action，scope，scope_id；按角色/动作索引；动作与范围绑定 |
| departments | name 唯一 |
| positions | 公司岗位 name 唯一 |
| department_positions | department_id + position_id 唯一，两个 FK |
| pools | 人才库 name 唯一 |
| talents | kind internal/external；内部必有部门，外部不得有部门/部门岗位；owner_id/pool_id；version；联系方式；部门岗位必须同部门；按部门/负责人/库索引 |
| facts | talent_id FK，category（education/experience/project/skill/certificate），content，source_type manual，source_version，confirmed，created_at；按人才索引。人工事实结构化分表行保存，不存万能档案 JSON |
| talent_history | talent_id/version 唯一，actor_id，changed_fields（仅字段名），created_at；不复制敏感正文 |
| files | talent_id，relative_path 唯一（随机生成），original_name，media_type，size，sha256，created_by；仅受控下载，不映射静态目录 |
| tasks | talent_id/file_id/created_by FK，kind=mechanism_test，state，run_version，lease_until，result，error_code；状态/租约索引 |
| attempts | task_id/run_version 唯一，state，started_at/ended_at；独立技术结果 |
| outbox | task_id/run_version 唯一，published_at，tries；未投递索引；同事务创建，重复消息允许 |
| idempotency | user_id/action/key 联合唯一，request_hash，resource_id；账号隔离，冲突 409 |
| audit | actor_id 可空，action，target_id，outcome，request_id，created_at；仅元数据，无密码/令牌/正文 |

权限 scope：self / department（scope_id=部门）/ internal_all / owner（外部负责人为当前用户）/ pool（scope_id=库）/ external_all / global（仅管理动作）。动作 talent.read/talent.write/file.read/file.write/task.run 独立匹配；员工授予 self 的只读动作，管理员只授管理动作。跨记录请求无范围返回 404，功能缺失 403。查询通过同一策略生成 SQL 条件，分页前过滤。

账号 bootstrap 从交互式密码创建；合成样本脚本需显式提供本机密码，不保存默认密码。管理动作有独立版本；编辑使用 UPDATE WHERE version 原子条件并同事务替换事实及记录历史。绑定唯一约束防一人多号；管理身份不输出人才正文。

任务：queued -> running -> succeeded/failed；运行领取为条件 UPDATE，租约 30 秒，测试任务短于租约。恢复仅扫描过期 running，递增 run_version、将旧 attempt 标 expired 并新建 outbox。失败可显式重试，最多 3 个执行版本；运行前和提交结果前重新检查发起人的当前授权。结果提交必须匹配 running + run_version，迟到结果丢弃。outbox 提交发送后再标投递，崩溃可能重复发送，消费领取确保幂等。轮询补偿器持续补发及恢复；Broker 不作为业务权威源。

文件单份最大 10 MiB；允许 PDF/PNG/JPEG/DOCX；验证文件可读取、非加密、PDF 页数 <=50、DOCX 安全压缩包上限；本阶段单文件请求，不提供批量解析。先鉴权，再流式限额读取，保存到 UUID 相对路径；数据库失败清理本次新文件。所有文件及任务读取重新检查对应人才当前范围。本阶段不解析、不调用模型。

## 第二阶段增量 b640cc81b002
resume_records：task_id 主键/外键，base_version/run_version，provisional，batch_id索引，segments/validated JSON，quality与模型标识。原文不混入当前有效 facts；每个 segment 有编号/locator/method/text，抽取有quote/segment_id。
index_events：id、talent_id、version唯一，state/error_code；档案保存同事务写事件，外部调用在提交后。状态 pending/ready/failed/obsolete。MySQL为权威源。来源原文保存在受控结果接口，日志只记录编号/错误码。

### 后续增量迁移
- c751dd92b003：import_failures，仅保留当前上传者的批次/文件名/请求摘要/错误码和说明；(user_id,key)唯一，无效文件不保存正文，重复失败请求不重复计数。
- d862ee03b004：talent_field_states，(talent_id,field)主键；confirmed/source_type/source_version，覆盖name/phone/email，包括人工确认空值。已有人工档案通过该迁移回填确认状态。
- resume_records通过task关联当前人才、原文件、创建者；provisional说明初次导入。quality含pending/complete/needs_review/possible_duplicate/identity_conflict/version_conflict/failed；validated含fields/issues/missing、suggestions和当次授权内重复ID。读取时重新过滤重复ID，不能利用旧快照泄露已撤权档案。
- 成功解析的原始证据不随人工编辑删除。当前Fact人工保存视为重新确认，原抽取记录/原文件仍可查；Task技术状态与资料quality、IndexEvent状态分开。

### e973ff14b005 审查修复增量
index_events新增attempt_count、failure_count、last_attempt_at、next_attempt_at及(state,next_attempt_at,last_attempt_at)索引；历史行默认0，新应用事件按创建时刻到期。attempt_count作领取版本，显式重建递增使旧调用失效；失败次数独立用于30秒起、最多1小时的指数退避。
talent_field_states同表扩展使用education/experience/project/skill/certificate类别键（无需新表），保留空集合确认；迁移由已有人工标量确认记录回填类别，确认来源版本取最近人工版本。降级保留确认元数据，重新升级不重复插入。不删除或重置既有业务明细。


## 第三阶段首批：招聘需求（2026-11-06）
增量迁移f084aa25c006新增recruitment_requirements（部门、部门岗位、创建人、draft JSON、status、编辑version、active_version、时间）及requirement_versions（需求FK、number、snapshot JSON、确认人、时间）。需求号+有效版本号唯一。部门岗位在业务上不可更换；部门单列供当前授权过滤，创建时从部门岗位取得。完整草稿采用有严格schema的JSON，后续匹配使用确认快照，不能直接读取未生效草稿。该表不是任意工作流定义。历史版本只追加，所有业务更新由编辑version条件控制。首批交付时仅测试库验证；第三阶段收尾已应用开发库。


S3-02在draft/snapshot JSON契约增加jd_text（最多20000字符）；旧记录缺省空串，不回写历史快照、不新增DDL。建议临时返回，不自动修改已保存版本，采纳后经现有草稿保存/确认生效。


## 第三阶段完整匹配落表（g195bb36d007）

match_runs绑定requirement_id/有效版本、创建人、不可变需求/范围/规则JSON快照，保存技术state、业务outcome、run_version/lease_until/error_code/时间；match_entries以(run_id,talent_id)唯一，保存人才/事实快照、BM25信号、逐人状态、检查/证据/评分结果及失败码；match_attempts以(run_id,run_version)唯一保存尝试/过期/结束；match_outbox同样唯一，保存投递状态/次数。talent_requirements复合主键为(talent_id,requirement_id)，是显式应聘关联，不充当身份/职业/授权。

迁移接f084aa25c006，两条均已应用本机开发库；历史共享迁移未改写。匹配不再创建虚假File或借用解析Task外键。独立JSON条件新增skill_experience_years，无须DDL；旧确认版本/匹配快照保持原样，缺省为不限制。规则v2与权重/模型配置随每个任务保存，旧v1记录不回写。快照事实可带经授权的文件/任务/定位/引用，读取再次检查当前文件归属及读权，不能把快照当权限旁路。


## 第四阶段测评及基础资料增量
h206cc47e008：assessment_questions保存严格题目JSON、编辑version及enabled；assessment_papers保存标题及编辑版本；assessment_paper_versions以(paper_id,number)唯一，snapshot拷贝题目/选项/答案/维度/分值及exact-set-v1规则，不提供修改接口。assessment_assignments固定paper_version_id/employee_id/talent_id/assigned_by，分别保存draft、final_answers、version、state、提交时间及安全错误码；assessment_results以assignment_id为主键保证唯一最终成绩，保存总分/满分/实际维度及规则版本。原始答案随任务保留，成绩独立入档不覆盖历史，不写匹配分。

i317dd58f009：departments/positions/pools/department_positions增加enabled与version，已有行回填启用/版本1。停用采用条件更新，不删除外键或历史归属；新建部门岗位、新人才归属及新需求拒绝使用已停用基础资料。既有归属可以继续保留和编辑资料。两条迁移已应用开发库，没有改写共享历史迁移。聊天及菜单后续增量见下一节。


## 第四阶段聊天及菜单增量（j428ee69a010 / k539ff70b011）
chat_conversations保存所属账号、固定范围ID/筛选/北京时间as_of、已明确条件、待确认计划与编辑版本；chat_messages以会话+sequence唯一，保存问题、当轮范围/条件/回答及时间。chat_jobs一消息一任务，保存技术状态、run_version/租约/安全错误码；chat_entries以任务+人才ID唯一，保存当轮人才/有效事实/来源版本快照、支持/未知/相反证据/结构排除/失败/未检索状态及引用。chat_attempts与chat_outbox分别以任务+执行版本唯一。

chat_checkpoints为原生LangGraph同步检查点适配表，以job_id/run_version/checkpoint_id唯一，保存父检查点、JSON checkpoint/metadata及去重pending_writes。图状态仅job_id/version/phase等技术标识；不保存权限凭证，不把检查点当业务成果。不同执行版本隔离命名空间，旧执行无法写新成果；恢复读取同样实时鉴权。只允许JSON，不使用pickle或任意Python对象反序列化。

ai_calls只保存operation/target_id/model/state/elapsed_ms/error_code/created_at，不保存提示词、聊天/简历正文、URL或密钥。生成模型、Embedding与OCR共享元数据记录；聊天/简历/JD按可用任务或追踪编号关联，部分独立索引调用可无目标编号。roles新增enabled_menus JSON：历史NULL表示按当前功能授权派生可见菜单；显式数组用于显示配置，仍与功能授权取交集，不能扩大后端权限。菜单与授权修改共用角色version检测冲突。

四条第四阶段增量迁移均已应用开发库；j/k接已共享h/i，未修改历史数据归属、旧需求/匹配结果或账户。
