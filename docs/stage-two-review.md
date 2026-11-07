# 第二阶段审查问题修复

> 历史实施／验证记录：以下状态、命令、选择器与样本数对应记录当时。当前进度见[progress](progress.md)，最新页面与验证入口见[调整记录](filter-task-adjustment.md)和[测试指南](testing.md)；勿据此重置当前数据或自动开展下一阶段。

2026-11-05，北京时间；审查基线646a562，分支codex/stage-two-resume。三个反馈均已复现，本阶段已于2026-11-05获李玉杰明确验收通过，第三阶段仍未启动。

## 修复与原因

1. P1 文件重关联后的旧任务越权读取：原实现仅按Task.talent_id鉴权，没有确认File当前归属。新增repositories/access.current_task_file，读取原文前确认Task与File当前talent_id相同并检查权限，失败统一404；授权通过后才加载原文JSON。初次执行、最终落库、重试、关联核对也使用该边界，机制任务同样校验当前来源。最终提交先锁任务再锁文件，关联期间不会用迟到结果写回旧档案。批次历史排除不一致来源；索引构建与命中复核剔除已移走文件的引用。原始文件与历史记录不删除，不把所有旧任务自动授权给新档案。
2. P2 人工清空最后一条事实被恢复：确认意图不再依赖还存在的Fact行。人工保存同时确认education/experience/project/skill/certificate类别，空集合也保留TalentFieldState记录；重新解析只生成建议。新迁移用历史标量人工确认记录回填完整表单的类别确认。确认记录约束自动修改，不把空集合推断为“确实不具备任何技能”。迁移不自动删除既有明细；若先前已有误恢复的数据，请人工核对后清空保存。
3. P2 失败索引事件堵住后续：增加next_attempt_at/last_attempt_at/failure_count/attempt_count与到期索引。只选到期事件，按到期时间、上次领取时间和ID稳定排序；新事件到期时间为创建时刻，避免一直抢在已到期重试之前。失败退避30、60、120秒递增，上限3600秒。短事务领取后关闭事务进行Embedding/Milvus调用，600秒租约允许进程中断后恢复；领取版本防止旧结果覆盖新一轮重建。显式重建可重新安排立即执行。

## 迁移与运行

新增e973ff14b005_review_protection_scheduling.py，沿用现有MySQL，无破坏性重置；增加索引调度元数据，补齐人工确认类别。SQLite/MySQL均验证历史已清空数据升级和重复升降级，降级不删除确认记录。开发库已执行alembic upgrade head。
Worker/indexer镜像更新为ai-talent-stage2-backend:0.2.1，业务API和后台进程重载，依赖版本、OCR/Embedding模型、其他应用服务不变。

## 验证（全部合成材料）

- 修复前：`.venv/Scripts/python.exe -m pytest tests/test_stage_two_review.py -q --tb=short`，3 failed /10.37s，分别复现旧任务返回200、技能恢复和第21条事件饥饿。
- 新增6项审查回归：同文件3个任务与实际关联接口、权限收窄后的旧原文404及旧执行拒绝；人工清空后重复解析仍为空且有建议；21条失败事件三轮仅处理21次、第21条已执行；退避到期后再执行；模型调用期间关联变化丢弃结果；旧索引领取不能覆盖显式重建；历史清空确认迁移。部分场景合并在同一测试。
- SQLite定向6 passed /19.96s，MySQL定向6 passed /43.06s；收尾读取顺序复核6 passed /19.82s；补强P1索引引用验证1 passed /3.66s（原档案有效且确实可读，文件引用仍被拒绝）。
- 完整SQLite：`.venv/Scripts/python.exe -m pytest -q --tb=short`，46 passed /162.30s。
- 完整MySQL：`.venv/Scripts/python.exe scripts/test-mysql.py`，46 passed /254.73s；随机独立talent_test_库，结束只删除该测试库，开发库不清空。
- `.venv/Scripts/python.exe scripts/test-index-live.py`通过：真实Ollama/Milvus连接失败、服务恢复后的受控重建、当前版本和后端权限过滤。该脚本显式重新安排重试，不把它当作真实等待退避计时的证明；退避时间由上述可控时钟测试精确验证。
- 模型与Embedding替身只用于确定性权限/时序/调度回归，不宣称本轮重新评测OCR或生成模型准确率。前端未修改，无新增浏览器效果宣称。原样本限制仍见stage-two-verification.md。
- API健康和登录后候选人读取均HTTP200；本项目MySQL/Redis/Worker/dispatcher/indexer均运行。

验收可重复操作：将同一文件的一个任务关联目标档案，收窄到原档案范围，旧原文接口应404；删除最后一个技能并保存，再解析应只给建议；构造21条持续失败事件，连续补偿不会重复占满前20条，后续事件能推进。

通用Worker来源校验收尾回归：`.venv/Scripts/python.exe -m pytest tests/test_stage_one.py tests/test_stage_two_review.py -q --tb=short`，SQLite17 passed /63.89s；`.venv/Scripts/python.exe scripts/test-mysql.py tests/test_stage_one.py tests/test_stage_two_review.py`，MySQL17 passed /103.25s。MySQL脚本现支持透传pytest选择参数，默认仍运行全套。

## 阶段验收决定（2026-11-05）
李玉杰实际试用了页面和测试简历，并明确要求将第二阶段审查标记通过。该结论覆盖核心技术链路与三项审查修复，不等于页面操作体验通过无缺陷，也不宣称整体OCR/抽取准确率。已知后续优化：页面流程不顺畅，大量“未确认”标签混淆提取可信度、来源与技能真实性；不应让HR机械地逐项确认技能，真实性应在面试或测评环节核验。优化时保留人工修改防覆盖保护，避免单纯隐藏标记。第三阶段未获启动授权，分支不自动合并main。
