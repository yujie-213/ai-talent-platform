# 第四阶段审查修复：筛选范围与具体问答

2026-11-06，基线bdc0efa，分支codex/stage-four-chat-assessment。开始工作区干净，继续现有第四阶段授权。修复代码提交3c946fe，文档最终提交由git log查看。状态：修复并部署本机，待用户验收；不进入第五阶段。

## 问题与最终行为

1. 原候选人列表支持requirement_id，聊天前端漏传且后端schema拒绝该字段，两个查询还重复实现筛选规则。现由repositories/candidate_filters.py共用有效档案、身份、技能/教育/经历原文包含及显式应聘关系条件，保留SQL通配符转义。列表按talent.read，聊天另与chat.use取交集；聊天不会扩大列表范围。需求使用原requirements.get鉴权，创建、历史、工具执行和检查点经current_scope重新检查需求读权。
2. 原ask/compare在证据评估后仅拼接“有来源支持”状态。现增加ai/chat_answer.py，在原问题与逐人已核验证据上生成受约束的答案片段参数，再由代码组成直接答案及比较。学校、技能、经历等可从事实回答，不因缺少同名结构化筛选字段而预先澄清。

前端只将最近一次成功列表请求的五项筛选传入聊天，不带排序/分页，也不将编辑但尚未应用的表单当作当前范围。会话保存requirement_id，页面明确显示。已核验片段组成带编号答案，编号按钮复用原引用鉴权入口；比较按同一判据对齐，展示具体共同记录和差异。

答案模型只接收已核验引用、问题和当前人才标识。每段必须绑定本人/本判据的既有fact_id与quote，text必须是该quote的连续原文，未知字段、跨人/跨引用及新增事实拒绝。整理不通过时明确退回具体证据原文，仍保留引用。共同点仅按实际相同提取值归纳，差异称为“记录差异”；信息不足不推断为能力缺失，不生成无证据优劣排名。

外部整理调用在事务外，调用前及返回保存前重新检查账号、需求/人才/文件权限、执行和会话版本。人数及结构化规则继续由代码负责，未开放SQL或写工具。调用只记录chat.answer安全元数据；业务表使用既有answer JSON，无新增依赖或迁移。

## 实际验证

| 实际命令 | 结果与性质 |
|---|---|
| `.venv/Scripts/python -m pytest -q tests/test_chat_review.py --tb=short`（修复前） | 2 failed /8.56秒，分别复现requirement_id被422拒绝、具体学校未进入答案 |
| 同命令（首次修复后） | 2 passed /8.43秒 |
| 同命令（最终完整新增边界组） | 8 passed /14.96秒，含编造/跨人/引用替换/额外工具字段拒绝、共同记录与整理时撤权 |
| `.venv/Scripts/python -m pytest -q tests/test_chat_review.py tests/test_archive_chat.py tests/test_matching.py --tb=short` | SQLite定向40 passed /139.57秒；真实API/DB/LangGraph，模型/Embedding使用明确替身；含原聊天/岗位匹配回归 |
| `.venv/Scripts/python scripts/test-mysql.py tests/test_chat_review.py tests/test_archive_chat.py tests/test_matching.py` | 独立随机MySQL同组40 passed /344.08秒，开发库不重置；新增验证涵盖需求筛选/撤权、学校/比较、编造/跨人片段/额外工具字段拒绝及答案整理中撤权 |
| `.venv/Scripts/python scripts/verify-chat-review-live.py` | 真实API/MySQL/Redis/Worker/LangGraph/生成API，无模型/数据库替身；两条全新合成档案中仅甲应聘目标需求，列表1人=聊天1人，未混入乙；直接学校答案和具体比较通过，两次均为validated_extractive_answer，非回退结果；逐条引用核对通过 |
| `npm --prefix frontend run test:chat-review-live` | 真实Edge/API/模型链通过；技能筛选2人→选需求1人→修改但未应用输入→聊天仍为原1人，学校直接回答/编号来源按钮、真实比较历史均核对通过；无API替身 |
| `npm --prefix frontend run build` | TypeScript和生产构建通过；仍有约1MB主包提示 |

小规模效果：合成甲毕业于合成星河大学、声明Python/Java，合成乙毕业于合成青山大学、声明Python/Rust。单人真实答案为“甲：合成星河大学［1］”；比较实际展示学校差异、共同Python及Java/Rust记录差异，六条引用逐人绑定。样本、真实答案及截图保存在忽略data/stage-four/chat-review-*，不入Git，不代表总体准确率。

验证过程：首次真实模型将“毕业院校”误判为不支持的结构字段而澄清，已补充计划提示：结构筛选字段不限制事实问答，学校/专业/公司/项目等走ask/compare逐人取证；再次真实API及浏览器学校提问通过。页面脚本最初误用原生input placeholder定位Element Plus选择器，改为可见占位文字后通过。一次pytest命令误写不存在的test_candidates.py，未执行测试；纠正为实际test_matching.py后取得上表结果。

## 本机部署与历史边界

使用原Dockerfile.stage4构建同一0.4.0项目镜像，并按README三文件compose `up -d --no-deps worker dispatcher indexer`重载项目后台；仅停止已核实的本项目8000进程后以隐藏窗口重启Windows API，页面5173使用更新代码。无新迁移，数据库head仍k539ff70b011，无依赖/服务版本升级，无seed、删库/卷/模型、账号重置或main合并。最终API `/api/health`返回ok，页面5173返回200。

最终镜像构建成功，摘要sha256:741475ae0324113e024b8eb09b048d0291e7f9890da0d5c673738965833ca9cf。Windows/API及后台复用原生成、Embedding和数据库配置；本轮不重新评测OCR、测评或大规模吞吐。

旧会话未保存的应聘条件无法可靠推断，**需从修复后的筛选页面新建会话**；不对旧范围偷偷补条件。旧模板回答保留历史，新增问答使用新整理；不批量回写旧消息/检查点/业务结果。相同原文提取值才作为共同记录，语义改写、隐含能力和总体效果仍有局限。

## 李玉杰复核步骤

1. HR进入候选人筛选，选择某应聘需求，确认仅显式关联人才；点击“按当前筛选范围聊天”并新建会话，核对人数、名单与应聘需求编号。
2. 在含学校信息的单人会话问“毕业院校是什么？”，应直接出现学校名称；点击答案编号来源，核对本人、原文和版本。
3. 勾选两名合成人才，比较学校/技能；应看到具体值、共同记录与差异，引用不串人。缺失资料应明确不足。
4. 撤销需求读权后，新的该需求筛选和已有对应会话读取都应被拒绝。历史缺失应聘条件的会话按上文新建，不据旧范围判断本次修复。
