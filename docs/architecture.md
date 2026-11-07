# 当前架构与模块导航

模块化单体，Windows上的FastAPI与Vue前端、Linux中的Celery Worker/dispatcher/indexer共享业务实现。MySQL为权威源，Redis负责投递，Milvus为可重建索引。数据库迁移显式执行，应用启动不建表。运行方式见[部署](deployment.md)。

## 模块职责

| 入口 | 职责 |
|---|---|
| `backend/app/api/` | HTTP参数、鉴权依赖、统一响应、SSE和受控下载 |
| `backend/app/services/` | 业务事务、版本屏障、幂等、任务编排与成果保存 |
| `backend/app/repositories/` | 当前授权查询、分页、候选人条件、事实来源与聊天范围 |
| `backend/app/core/` | 配置、数据库、身份、动作与数据范围权限 |
| `backend/app/models/`、`schemas/` | 持久实体及受约束请求契约；数据库演进在Alembic |
| `backend/app/ai/` | 受控问答图、查询计划、证据和模型回答约束 |
| `backend/app/tasks/worker.py`、`cli.py` | 消费者入口、outbox投递、租约恢复及索引补偿 |
| `frontend/src/App.vue` | 身份、授权菜单、导航、档案写入与解析任务页 |
| `frontend/src/*Workspace.vue` | 人才、画像、岗位匹配、聊天、测评与管理工作区 |
| `infra/`、`scripts/`、`tests/` | 锁定服务配置、本机运维与验证、自动化回归 |

## 核心业务链

- 简历：导入文件 → resume_tasks短事务建立任务/outbox → dispatcher投递 → Worker读取/OCR/模型抽取 → 授权、资料版本和执行版本复核 → 保存建议或事实 → 索引补偿。人工确认的类别与空值受保护。
- 筛选与画像：candidates → candidate_filters共用条件与权限 → MySQL计数和分页。姓名字面包含，学历/总年限复用match_rules；画像事实来源额外校验file.read及当前Task/File归属。
- 岗位：requirements草稿 → jd_assist受控建议 → HR确认不可变版本 → match_tasks固定需求/范围/事实/规则快照 → Worker执行 → match_rules三态校验与Embedding/BM25/RRF排序 → 当前授权读取分组、解释和历史。
- 问答：画像/勾选/筛选范围 → archive_chat → chat_jobs可靠任务 → archive_graph与MySQL检查点 → 受控计划/证据核验/回答 → 保存前再次鉴权与版本检查 → SSE或历史恢复。模型不持有任意SQL执行权限。
- 测评：题库 → 不可变试卷 → 分配绑定员工 → 版本化草稿 → 原子提交 → 独立事务确定性评分 → 授权成绩与实测维度。测评分不加入岗位匹配。

## 当前页面与接口补充

CandidateWorkspace同时承载简历筛选与人才列表。人才画像使用姓名/技能300ms自动搜索和身份/学历/经验标签；简历筛选以真实岗位标签为主，解析历史从上传旁打开。ProfileWorkspace/ProfileFacts提供独立画像及来源，ChatWorkspace复用上下文问答；侧栏不再提供独立问答与历史入口。

解析统计来自workbench.parse_tasks，不回退人才数。`GET /tasks`在权限过滤后按最近Attempt.started_at倒序分页，再以ID稳定排序，返回人才姓名、经文件读权核验的文件名和parsed_at；无执行时间排后。批次概览为`GET /imports/summary`，按本人导入与当前授权聚合。当前接口补充见[api](api.md)。

共享界面组件包括PageHeader、StatusTag、FactGrid、EmptyState、UuidShort、PersonAvatar、ScoreRing与MiniDonut。工作台人才数与解析任务数是独立口径。日志只保存安全元数据，不记录秘密或简历正文。

## 验证与设计边界

权限、幂等、版本冲突与恢复均由后端控制；菜单隐藏不代表撤权。外部模型调用不持有长事务。具体测试及真实效果边界见[测试指南](testing.md)和[最新调整](filter-task-adjustment.md)。历史实现导航见[归档](architecture-history.md)。
