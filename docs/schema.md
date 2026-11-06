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
增量迁移f084aa25c006新增recruitment_requirements（部门、部门岗位、创建人、draft JSON、status、编辑version、active_version、时间）及requirement_versions（需求FK、number、snapshot JSON、确认人、时间）。需求号+有效版本号唯一。部门岗位在业务上不可更换；部门单列供当前授权过滤，创建时从部门岗位取得。完整草稿采用有严格schema的JSON，后续匹配使用确认快照，不能直接读取未生效草稿。该表不是任意工作流定义。历史版本只追加，所有业务更新由编辑version条件控制。开发库未应用，测试库已验证迁移。
