# 第三阶段实际验证与验收

> 历史实施／验证记录：以下状态、命令、选择器与样本数对应记录当时。当前进度见[progress](progress.md)，最新页面与验证入口见[调整记录](filter-task-adjustment.md)和[测试指南](testing.md)；勿据此重置当前数据或自动开展下一阶段。

2026-11-06（北京时间）。阶段交付待用户验收；本文件仅记录执行过的检查及边界，不代表总体准确率或已获用户验收。

## 环境与隔离

Windows项目.venv Python3.13.5，固定依赖；既有本项目独立MySQL13306/Redis16379；Linux Celery Worker/dispatcher；真实本地Ollama bge-m3（已锁摘要，1024维），既有Milvus保留。API8000、前端5173。没有升级既有Dify/Milvus/Neo4j/Conda模型或删库/卷；第三阶段继续使用0.2.1依赖镜像并挂载当前源码。`.venv/Scripts/python.exe -m pip check`及compose exec worker python -m pip check均无损坏依赖。

SQLite回归使用独立临时库；MySQL脚本创建随机talent_test_*库，结束仅删除该库。新增f084aa25c006、g195bb36d007已显式应用开发库；API、worker、dispatcher已重载。显式prepare-stage-three-demo.py只给现有合成HR追加需求读写，不替换原授权，不给管理员/员工业务正文权。账号密码/原文件/报告/截图均在忽略目录或.env，不入Git。

## 自动化验证

| 实际命令 | 结果及性质 |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q --tb=short -p no:cacheprovider` | 最终完整75 passed /248.28秒（此前完整68 passed /272.07秒）。包含前两阶段回归及新增需求/JD/匹配 |
| `.venv/Scripts/python.exe scripts/test-mysql.py` | 完整68 passed /471.51秒，真实随机独立MySQL；随后新增条件/边界另行定向验证 |
| `.venv/Scripts/python.exe scripts/test-mysql.py tests/test_matching.py tests/test_jd_assist.py tests/test_requirements.py` | 最终29 passed /196.50秒，覆盖全部第三阶段需求/JD/匹配；模型/Embedding为确定性替身 |
| `.venv/Scripts/python.exe -m pytest -q tests/test_requirements.py tests/test_matching.py --tb=short -p no:cacheprovider` | 收尾中途18 passed /65.94秒；同范围MySQL18 passed /120.91秒；后续包含于最终更完整验证 |
| 定向`-k 'started_run or scope_intersects or recovery_exhaustion'` | SQLite3 passed /12.17秒、MySQL3 passed /19.20秒 |
| 定向`-k selected_requirement` | SQLite1 passed /4.42秒、MySQL1 passed /6.45秒；验证所选需求不混入其他需求分数 |
| `npm --prefix frontend run build` | 最终类型/生产构建通过；既有大包体提示保留 |
| `$env:FRONTEND_URL='http://127.0.0.1:5173'; npm --prefix frontend run test:jd-assist` | 真实Edge+合成API交互通过；自动粘贴、空字段合并、推理期间输入/清空保护、冲突/条件采纳、原文保存、失败回退及关闭后的迟到响应。不是生产API/模型证明 |
| `git diff --check` | 已通过；本机秘密值排除扫描通过，只报告是否命中，不打印值 |

关键覆盖：缺必填/未确认/草稿/停用不能新匹配；同名跨部门独立；草稿不覆盖当前有效版本；需求及人才权限独立、不同动作取交集；空选择不扩大；默认外部和可选内部排除目标部门；不要求应聘关联；超过20人的固定范围逐人处理/稳定分页；技能声明/项目使用/NoSQL边界、学历低于/缺失、总日期去重/下界、技能年限不借总年限；原文当前文件归属/读权再校验；模型期间撤读/撤写/禁用/源版本冲突；幂等、失败重试、重复消息、租约恢复、次数耗尽、旧执行拒绝；选中需求的分数隔离；完整不可变快照与过期提示。

测试过程曾发现：中英文相邻技能边界误判（修复业务规则）；所选需求列混入其他需求分数（修复过滤并加回归）。初次技能年限纯单元用例未走Pydantic默认值，规范化用例后重跑；实际API数据已规范化。早期MySQL新需求回滚单独删外键依赖索引失败，f084在共享前已修复并通过。浏览器脚本曾因Element Plus菜单、隐藏原生checkbox、placeholder定位失败，改为关联菜单/可见标签/文本，并以唯一合成需求名称重跑，不将这些定位失败当业务修复。所有最终结果如上，未隐藏失败过程。

## 真实生成与排序评测

` .venv/Scripts/python.exe scripts/evaluate-jd.py ` 使用真实已配置生成模型及三个合成样本：完整JD最终9项有效建议/10个有输入字段，漏description；简略完善返回3项建议，未返回虚构薪资/地点/福利；技能年限样本返回4项建议，包含独立技能年限，引用通过。没有样本外准确率承诺；真实浏览器流程由HR手工补齐/确认后生效，缺项不能生效。中文数字、共享薪资单位等复杂格式保守待核对，不宣称自动无漏抽。

` .venv/Scripts/python.exe scripts/evaluate-matching.py ` 真实bge-m3/BM25/RRF对3条合成项目排序，相关Python/RAG项目 > 部分相关Java接口项目 > 无关行政项目。最终规则v2保存在本机报告。只是小样本初始排序基线，50/20/30不是经统计证明最优参数，分数不是能力/录用概率。

同脚本另发起**无额外筛选、非top-k**的当前授权外部全范围任务：实际18人，14人完整评估、4人明确PROFILE_EMPTY，待处理0；没有事实者不伪造分数、不冒充模型成功。真实本地资料未打印或写入Git；报告只保存计数/失败码及合成排序样本。

` .venv/Scripts/python.exe scripts/verify-skill-years-live.py ` 真实API→MySQL→Worker→Embedding：合成人才有6年总工作经历但无Python时间声明，在“3年Python”条件下为待核对；补充明确“Python开发经验：3年”后新建匹配才满足。旧任务仍保留原快照。规则v2新增该条件；旧v1快照无此字段，兼容为不限定，未回写旧结果。

原始合成报告仅在本机data/stage-three-evaluation/{jd,matching,live,skill-years,browser}.json，均被忽略。

## 真实后台与故障恢复

`.venv/Scripts/python.exe scripts/verify-stage-three-live.py` 退出0，无模型/队列/数据库替身：

1. 合成样本默认外部全筛选范围5人，含内部时6人；目标部门现任排除。技能栏声明和项目使用均命中；本科/大专/缺学历/无Python依据产生预期满足/不满足/待核对分组。无应聘关联也处理，真实余弦/BM25/RRF和完整分数落库。
2. 显式关联后候选人展示已有分数；匹配本身不建立应聘关系。
3. 停本项目Redis，API任务/outbox仍持久化，投递未成功；finally恢复Redis后自动补发完成。
4. 捕获真实匹配running后对本项目worker发送SIGKILL，finally恢复；45秒租约到期后执行版本2成功、attempt1为expired。重复/旧消息不新增成果，旧finish返回false。
5. 修改合成档案再读旧结果，旧快照不变且profile_stale；更新有效需求旧任务requirement_stale；显式[]产生0人完成，不扩大。

故障服务均已恢复。不要与同一项目其他故障脚本并行。该脚本会新增合成记录，不清空业务库。

## 真实页面全链路

前端目录执行`npm run test:stage-three-live`，真实Edge→API→MySQL→生成模型与Linux Worker/bge-m3，**没有API或模型替身**，最终已通过（v2部署后也复核通过）：

- HR同一表单粘贴纯文本自动提取并保留原文；手工核对/补齐技能、学历、年限、面议；暂存草稿时匹配按钮禁用。
- HR确认生效为独立版本，手动匹配5名合成外部人才；页面实际轮询完成，分组/分数/证据可见；资料不是预设假结果。
- 从项目证据标记应聘；候选人页选该需求只见关联人才、仅该需求的分数/版本/时间，不混入其他需求结果。
- 员工/管理员看不到需求入口；更换需求/匹配/结果ID的真实请求返回404，不借HR权限。
- 截图只保留本机data/screenshots，最终交付截图为合成匹配证据/筛选后的合成人才，未提交。测试未代替李玉杰本人的验收。

## 人工验收建议

1. 打开http://127.0.0.1:5173，使用本机HR合成账号；在岗位需求查看“第三阶段页面合成”及“第三阶段合成技能年限”记录。
2. 新建需求手工暂存，缺薪资/地点等不能生效；核对JD原文、差异和条件。“优先技能”不能被结构化配置默默改为必备。
3. 确认生效后手动匹配；默认外部范围，不需要先关联；可选内部并排除目标部门现任。先看分组，再看证据与总分。
4. 打开历史记录核对需求/人才/规则快照；修改后标旧，新运行独立保存；停用不再接受新匹配。
5. 显式标记应聘后在候选人页选该需求；未匹配者不出现假分；员工/管理员不因系统身份获得正文权。

## 未评测与限制

不是总体OCR/抽取/匹配准确率报告；只有有限合成语义/规则样本，未做大规模标注、负载/长时/渗透测试。复杂否定、同义词、学历和日期解析保守未知，手写/低清等沿用第二阶段限制。JD文件上传不在本次接口（纯文本粘贴）。场景需要新的硬条件类型时必须显式建模，不把模型自由文本当可执行规则。历史保留与敏感数据清理仍沿用本机约束；未部署公网；未实现第四阶段聊天/测评/完整管理页。第二阶段标签语义/页面体验待优化项未擅自扩大到本阶段。


## 后续年限审查（基线e9350de）
上述为首次交付的真实记录。其后发现上下界/否定、总与技能年限、JD数字归属问题，现已修复为v3。修复前复现、完整SQLite140/隔离MySQL88、真实链路及历史处理见stage-three-review.md；旧结果须以规则过期提示核对，不能当作当前分组。
