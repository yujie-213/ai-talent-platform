# 第四阶段验证记录（进行中，非阶段验收报告）

2026-11-06，北京时间。当前只完成测评、工作台和部分管理。聊天、持久语义任务、AI调用日志页面及完整管理交付仍未完成；不标待用户验收，不进入第五阶段。

## 基线与运行环境

- 起始分支codex/stage-three-requirements，HEAD与远端均7c322a3，工作区干净；c384b97..7c322a3只有文档差异。新分支codex/stage-four-chat-assessment，从该HEAD创建，main未动。
- 普通权限运行pytest首次无法打开临时SQLite，不能算业务失败或通过。使用正常本机权限重跑。首次完整回归期间添加了新迁移，进程旧metadata未包含新表，后续fixture出现重复建表错误；该次91 passed/50 errors无效，未作为基线。
- 为消除开发中变更干扰，git archive导出7c322a3至忽略的data/stage-four-baseline，使用项目.venv及该目录backend执行`python -m pytest -q --tb=short`：**141 passed /244.70秒**，真实隔离SQLite，原始基线未修改。
- 现有Python3.13项目.venv、Windows API、真实MySQL13306/Redis16379、现有Linux Worker；没有升级既有服务、删库或清空账号。

## 实际命令与结果

| 命令 | 结果/性质 |
|---|---|
| `.venv/Scripts/python -m pytest -q tests/test_assessments.py` | 首批4 passed /10.14秒，真实API及隔离SQLite；故障评分为显式异常替身 |
| `.venv/Scripts/python scripts/test-mysql.py tests/test_assessments.py` | 首批4 passed /23.24秒，真实随机隔离MySQL；不碰开发库 |
| `.venv/Scripts/python -m pytest -q tests/test_assessments.py tests/test_stage_four_management.py --tb=short` | 6 passed /21.59秒，含工作台/停用/角色授权 |
| `.venv/Scripts/python scripts/test-mysql.py tests/test_assessments.py tests/test_stage_four_management.py` | 6 passed /43.03秒，含两条迁移及唯一成绩并发 |
| `.venv/Scripts/python -m pytest -q --tb=short` | 147 passed /290.09秒；之后增加两项测评测试及停用归属检查，另见下一项 |
| `.venv/Scripts/python -m pytest -q tests/test_assessments.py tests/test_stage_four_management.py tests/test_requirements.py --tb=short` | 最新14 passed /62.60秒，含撤权/禁用、试卷新版本、隔离库迁移升降级及第三阶段需求回归 |
| `npm --prefix frontend run build` | 类型及生产构建通过；保留原有大包提示 |
| `node frontend/scripts/assessment-live.mjs`（实际cwd=frontend，命令`node scripts/assessment-live.mjs`） | 真实Edge→API→MySQL，无API/评分替身；HR页面题库创建、发布、分配，员工草稿、提交并得到10/10，标准答案隔离，管理员无业务入口，角色页面通过 |
| `npm --prefix frontend run test:browser` | 三账号真实Edge/实际API/MySQL/上传/Worker机制任务通过，无OCR或模型效果宣称 |
| `npm --prefix frontend run test:task-pagination` | 61条分页、页外新任务直达与轮询通过；明确合成API替身 |
| `$env:FRONTEND_URL='http://127.0.0.1:5173'; npm --prefix frontend run test:jd-assist` | JD粘贴、人工防覆盖、显式采纳、失败和迟到保护通过；明确合成API替身 |
| `.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head`及`current` | 开发库已至i317dd58f009；h206cc47e008/i317dd58f009增量应用，无历史迁移改写或重置 |

真实页面首次在提交确认框等待中文“确定”失败，产品默认按钮是英文；已显式配置中文确定/继续答题并重跑通过。原任务分页替身测试发现隐藏测评抽屉造成多匹配，改为仅有详情时挂载抽屉，重新通过。没有掩盖这些失败。

## 覆盖及限制

测试覆盖标准答案投影隔离、旧快照、非法题目/选项、草稿、原子锁定、重复/并发提交唯一成绩、评分故障保留原提交并恢复、非本人拒绝、换绑/禁用/撤权、试卷新版本不影响历史、迁移往返、按权限工作台及停用历史保留。评分异常由monkeypatch注入，不代表真实生产故障。

真实Edge脚本使用既有合成账号；通过既有管理员API为合成HR显式追加测评manage(global)、assign/read(internal_all)，不赋予管理员业务正文权限，不重新seed。新建题目/试卷/任务均有合成标签。报告和截图在忽略目录data/stage-four，未提交账号、原文件或敏感正文。

测评恢复当前为页面/API显式恢复评分，不是Celery自动补偿；大规模并发/负载和长期运行未测。题库/试卷/员工选择列表目前未分页；任务历史分页，工作台按当前授权实时计算。基础资料支持新增和启停，尚不宣称完整组织管理/菜单配置/日志管理交付。雷达图仅本试卷实际可归一化维度，少于三个维度用条形图，缺失为未测评；不跨试卷推断可比性。

LangGraph仅做Windows兼容性预检：`pip index versions langgraph`、`pip install --dry-run langgraph==1.2.20`、项目.venv实际安装1.2.20及`pip check`通过；核心1.7.6、checkpoint4.3.1。未改requirements/Worker镜像，未实现图流程/MySQL检查点，未验证Linux运行，不能算聊天交付。持久化候选依据官方[自定义检查点文档](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/checkpointers.mdx)，具体方案和依赖仍须实现并锁定验证。

## 本机页面核验步骤

1. 打开本机5173并使用data/local-access.txt已有合成账号登录；工作台无固定演示数字。管理员应无人才/测评正文入口。
2. 管理员→角色与菜单权限创建角色，配置功能/范围；账号管理设置启停、角色、人才绑定。指定部门/人才库使用下拉选择。
3. HR→轻量测评→新增题目：设置题型、选项、正确选项、维度、分值；发布试卷，选择题目后发布不可变版本，分配给绑定合成员工。
4. 员工→轻量测评→答题/查看，保存草稿，再提交确认；提交后不可改答案，查看总分与实测维度。HR人才详情可看授权结果历史。
5. 编辑题库答案并发布试卷新版本，旧任务的题目/版本和成绩保持原样；新分配才使用新版本。
6. 管理员基础资料停用某对象，已有归属保留；停用对象不可用于新建归属。启停及权限编辑陈旧版本应冲突。

这些步骤仅核验已实现子项，不等于负责人对第四阶段整体验收。
