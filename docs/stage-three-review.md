# 第三阶段年限审查修复

2026-11-06（北京时间）。修复代码c384b97，审查基线e9350de，开发分支codex/stage-three-requirements。李玉杰提出三项年限/引用问题，本轮在同阶段内修复；阶段仍待用户验收，不进入第四阶段。

## 复现与修正

修复前`.venv/Scripts/python.exe -m pytest -q tests/test_year_review.py --tb=short -p no:cacheprovider`为3 failed，分别复现以下问题。

| 输入与条件 | 修复前 | 规则v3 |
|---|---|---|
| Python经验3年以上，最低Python5年 | 不满足 | 待核对，下界3不能证明不足5，也不能证明达到5 |
| 没有3年Python经验，最低Python3年 | 满足 | 待核对，不能把否定断言当肯定数字 |
| 只有Python工作经验2年，最低总工作3年 | 不满足 | 待核对，技能经历不能充当总经历上界 |
| 总工作5年，其中Python工作2年，最低总工作3年 | 待核对 | 满足，只采纳总年限5，不把技能2当成总年限冲突 |
| JD要求3年Python经验、总工作年限不限，模型给总年限3 | 被标为可靠JD提取 | 提取模式丢弃；完善模式至多为无依据提议，不能标jd |

新增`services/year_evidence.py`共享保守证据解析：保留上下界、开闭边界、否定/模糊标记和数值在完整原文中的位置。匹配只有在整个可行区间都满足最低值时判满足，整个区间都低于要求时判不满足；跨界、否定、模糊或矛盾为待核对。工作日期去重仍只提供总年限下界。

总年限只接受通用工作经验/总年限声明，泛称前缀必须是通用叙述/要求；不会从Python/Java/项目工作经验中间截取数字。技能年限与总年限都使用同一证据语义。否定“三年技能经验”不会同时被误当成“不具备这项技能”。

JD校验在完整source里确定条件归属/边界，再检查quote是否覆盖该字段的数值；裁短引用不能洗掉技能前缀或否定，重复数字片段存在归属歧义时不标可靠。当前结构只有整数最小年限，不能无损表达上界/闭区间/严格大于或模糊条件，因此不把这些原文硬压成最小值；保留原文供HR处理。精确数字或包含下界的“至少/以上”等可支持对应最小值，不能擅自提高或降低。

## 旧规则与数据

当前规则升为`evidence-bm25-dense-rrf-v3`。不迁移、不删除、不回写已保存的需求、人才快照或历史结果；`rules_stale`作为计算响应字段提示旧规则结果，不修改其历史分组/分数。详情、结果API、候选人分数及页面均提供失效提示。

旧v1/v2任务若进入新版Worker，不允许用新算法算完却标旧版本：排队/运行旧任务明确失败RULE_VERSION_CHANGED，不能旧任务原地重试；已完成条目及历史保持。当前版本任务原有授权、执行版本、续租和重试保护保留。

**已采纳并经HR确认的旧JD条件不会自动修正。** 应先核对已保存条件，再发起新匹配；规则失效提示不等同于业务条件已纠错。真实业务数据不做猜测式修复。

## 实际验证

- 修复前3条复现：3 failed；修复后同项通过。
- `.venv/Scripts/python.exe -m pytest -q tests/test_year_review.py --tb=short -p no:cacheprovider`：最终63 passed（收尾额外覆盖“超过3年以上”仍保留严格下界；62项基线为0.22秒），纯合成文本，无模型/数据库查询。包含年限范围/否定/模糊/严格比较、总与技能归属、JD裁短引用/重复数字/相反条件/无法表达上界的拒绝。
- `.venv/Scripts/python.exe -m pytest -q --tb=short -p no:cacheprovider`：完整140 passed /311.94秒（收尾追加1条组合边界后仅重跑63项纯文本矩阵），真实独立SQLite；包含旧规则历史保留、排队/运行拒绝、重试拒绝及候选人过期标记。
- `.venv/Scripts/python.exe scripts/test-mysql.py tests/test_matching.py tests/test_year_review.py tests/test_jd_assist.py`：最终88 passed /206.59秒，真实随机隔离MySQL；Embedding/生成调用为确定性替身，不是模型效果证据。
- `npm --prefix frontend run build`：类型及生产构建通过，既有包体提示仍在。
- `.venv/Scripts/python.exe scripts/verify-year-review-live.py`：真实API/MySQL/Linux Worker/bge-m3对上述4条合成档案的三个匹配任务均完整执行，实际分组分别unknown、unknown、unknown/pass，全部使用v3；真实JD调用不会把该技能3年标成可靠总年限3年；旧规则历史详情rules_stale=true。没有API/模型替身。
- 在frontend目录`npm run test:year-review-live`：真实Edge只读旧合成记录，实际看到失效提示和保留的历史结果，无API替身；截图仅在忽略目录data/screenshots/year-review-old-rule.png。
- `git diff --check`通过；收尾秘密排除扫描不打印值，真实账号/报告/.env/原文件不入Git。

本机无未完成匹配时已重载API/worker/dispatcher，修复运行在8000/5173；没有数据库迁移、依赖升级、权限扩张或删库/卷/模型。实际合成报告仅在忽略目录data/stage-three-evaluation/year-review.json。

## 限制与验收

规则不是通用自然语言理解。中文数量词、复杂跨句指代、未支持的年限句式可能无法识别；未知不能被当作能力不足或符合。这里只记录上述确定性矩阵与真实合成链路，不承诺总体准确率。岗位上界/区间条件未新增结构化编辑器，JD不可无损承载时不标可靠，需HR明确处理。

验收可用新建合成需求/档案重复表中样例；检查旧结果提示、新任务v3及JD原文引用。旧结果不自动变成新分数，旧需求条件须人工核对。
