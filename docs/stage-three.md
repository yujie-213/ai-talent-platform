# 第三阶段：岗位需求与全范围匹配

2026-11-06（北京时间），李玉杰明确确认第二阶段已验收、远端已更新审批，并授权开始第三阶段。基线为 origin/codex/stage-two-resume 872664d；开发分支 codex/stage-three-requirements。第二阶段页面体验及“未确认”语义优化仍按远端决定暂缓，人工保护不取消。

## 实施顺序及状态

1. S3-01 岗位需求基础闭环：已实现，后端自动化验证及前端构建结果见本页下方。真实页面人工验收未进行。
2. S3-02 同表单 JD 自动提取与可选 AI 完善：已实现，后端SQLite/MySQL、真实模型合成样本及Edge交互已验证（覆盖范围见下方）。保留原文，空字段回填、冲突给差异；不编造薪资地点等企业事实；失败可继续手填。
3. S3-03 匹配任务与不可变快照：未开始。新增独立业务任务实体，复用现有可靠投递机制，不能把无文件匹配任务伪装成简历解析任务；短事务、幂等、执行版本、租约恢复。
4. S3-04 全范围硬条件与语义排序：未开始。固定当前授权外部全范围，可加内部并排除目标部门现任；不要求应聘关联，空范围不扩大；逐人才有结果或明确失败。技能声明或项目使用可命中；没有时间证据的技能年限为未知。
5. S3-05 证据、历史及候选人关联展示：未开始。硬条件满足/未知/失败分组，明确失败不进入合格榜；展示配置化规则版本、实际语义分、来源、快照、资料/岗位过期标识；重新读取鉴权，撤权与迟到执行拒绝。
6. S3-06 合成标注评测、真实模型/Embedding、Worker恢复、MySQL/权限及页面验收：未开始。完成后标第三阶段待用户验收，不自动进入第四阶段。

## 首批实现设计

- 公司岗位、部门岗位复用既有基础资料；每个招聘需求绑定一个不可更换的部门岗位。同一公司岗位在不同部门建立不同需求，移动需求需新建，避免历史正文跨部门转移。
- `recruitment_requirements` 保存草稿、状态、编辑版本及有效版本号；`requirement_versions` 只追加经HR确认的不可变快照，包括正文、结构化条件、薪资和地点。编辑有效需求只改草稿，旧有效版本不变；停用保留历史，再生效创建下一个版本。保存不创建匹配任务。
- 生效必填名称、地点、薪资、职责、要求、结构化条件，HR显式确认正文与条件一致。代码校验字段和数值，不宣称自动理解所有正文矛盾。
- 薪资支持明确区间或显式面议；区间为非负整数、下限≤上限，币种 CNY/USD/EUR，周期月/年/时。福利可空。
- 结构化条件：必备/加分技能不可重复或交叉；最低学历明确“ 不限 ”或层级；最低工作年限 null 表示不限、0为明确不要求经验。技能清单空表示无该类限制。后续评分基线须评测形成，不在本批承诺权重/效果。
- 新动作 `requirement.read` / `requirement.write` 各自接受 global 或 department；不继承 talent.read、系统管理身份或另一个动作范围。创建需要目标部门读写权限；编辑/生效/停用需要本记录当前读写权限。无授权列表为空，详情和写操作隐藏记录存在性。
- 新增迁移 `f084aa25c006`，不改写历史、不自动迁移、不自动给现有账号扩权。当前未应用开发库；现有API/Worker运行版本未调整。
- 单表单支持人工完整维护、暂存、确认生效、停用和查看完整历史；页面有未保存修改时不能确认生效。本轮已接JD辅助；匹配尚无可用按钮。

## API 与权限配置

`GET/POST /api/requirements`；`GET/PUT /api/requirements/{id}`；`POST /api/requirements/{id}/activate`；`POST /api/requirements/{id}/disable`。

列表返回 `{items,total}`，默认20、最多100、稳定分页。创建传 Idempotency-Key；PUT传完整草稿及version；生效传 `{version,confirmed:true}`；停用传 `{version}`。版本冲突409，缺字段422。读取详情含完整versions快照；列表仅草稿/当前状态。

现有账号不会自动新增授权。由有 account.manage 的账号通过现有 `GET /api/admin/roles` 取得当前角色及授权，再 `PUT /api/admin/roles/{id}/grants` 保留原有授权并增加以下项目；传当前角色version。不要用这两条覆盖整个原有授权列表。

```json
[
  {"action":"requirement.read","scope":"department","scope_id":"实际部门ID"},
  {"action":"requirement.write","scope":"department","scope_id":"实际部门ID"}
]
```

需要全公司需求范围时可显式配置global及scope_id:null；该范围不扩大候选人权限。开发库部署时先手动执行迁移并重载API，前端登录后在有requirement.read授权时出现“岗位需求”。本批不需要重建OCR镜像或变更模型。

## 本批验证

实际执行结果：

- `.venv/Scripts/python.exe -m pytest -q --tb=short -p no:cacheprovider`：50 passed / 156.83秒（完整46项既有用例+首批4项；补充第5项后仅重跑定向）。
- `.venv/Scripts/python.exe -m pytest -q tests/test_requirements.py --tb=short -p no:cacheprovider`：最终5 passed / 21.62秒。
- `.venv/Scripts/python.exe scripts/test-mysql.py tests/test_requirements.py`：最终5 passed / 35.41秒，真实随机独立MySQL库；脚本finally只删除本轮测试库。初次3 passed/1 failed，发现回滚时MySQL外键依赖索引；修复未共享新迁移，随整表删除索引后通过。
- `npm --prefix frontend run build`：类型检查及Vite生产构建通过（原包体提示仍在）。
- `git diff --check`：通过。
- 受限运行初次无法打开临时SQLite/启动构建子进程，改正常本机权限后执行以上验证；未把环境报错当业务失败或伪报通过。

独立SQLite/MySQL测试覆盖草稿必填、生效确认、不可变历史、编辑版本冲突、停用/再生效、幂等、同名不同部门、指定部门越权、管理员/员工默认拒绝、撤销写权不影响读权、旧令牌即时撤读、薪资/技能/年限校验及迁移升降级。

未验证：真实页面交互、真实JD/匹配模型、匹配任务恢复和匹配效果；均未宣称通过。测试未调用模型，不以此证明智能匹配能力。


## S3-02 JD辅助交付（2026-11-06）

### 业务与入口

- `POST /api/requirements/assist`：请求包含mode（extract/improve）、draft；已保存需求另传requirement_id和当前编辑version。服务只返回建议，不保存草稿、不生效、不启动匹配。
- `RequirementDraft.jd_text`最多20000字符，原文随草稿及确认快照保存。既有JSON可缺省该字段，不需新迁移、不改写已共享迁移。辅助页面目前接受粘贴纯文本，不支持岗位文档上传；简历文件导入流程不充当JD入口。
- 同一表单粘贴JD后500ms触发提取；也可点击重试或完善。未选部门岗位先提示，保留已粘贴原文。空字段可自动回填；已有值或推理期间人工修改产生差异卡片；结构化条件始终由HR显式采纳，生成提议不自动回填。原文/部门变化、关闭/切换表单或保存造成的迟到响应丢弃。
- AI失败时保留表单与原文，可手工保存；修复空薪资默认控件不能保存草稿的问题：上下限都未填时发送salary:null，半填区间仍由后端拒绝。
- `services/jd_assist.py`先检查需求读写/部门范围和版本，rollback结束读取事务后调用共享generate_json，返回后重新查账号启用、当前授权与版本。新需求按目标部门鉴权；旧需求不可更换部门岗位。审计只记录动作/记录号/成功失败，无原文。
- `services/resume_providers.generate_json`统一复用第二阶段模型配置、90秒超时和安全错误；简历抽取沿用原prompt与返回契约，没有新增模型/依赖或变更用户配置。
- 白名单逐字段校验类型和限额。提取模式必须有JD连续引用；名称/地点/福利是原文连续内容，技能必须有引用，学历/年限须明确，薪资区间需数字、币种、周期依据。无依据企业事实在完善模式也丢弃；无依据职责/要求/技能提议标proposal并要求显式采纳。程序并未证明语义绝对正确，HR生效确认仍需核对正文与条件。共享单位如“2-3万元/月”当前保守忽略，手工填写或核对，不能称完整薪资解析。

### 实际验证与限制

- `.venv/Scripts/python.exe -m pytest -q tests/test_jd_assist.py tests/test_requirements.py --tb=short -p no:cacheprovider`：13 passed /42.11秒。真实API/SQLite，生成调用为明确替身；覆盖引用/格式、虚构事实过滤、提议分类、原文保存且不自动写建议、无权限不调用模型、模型期间撤权/禁用/编辑、无长事务及安全失败。
- `.venv/Scripts/python.exe scripts/test-mysql.py tests/test_jd_assist.py tests/test_requirements.py`：13 passed /83.09秒，真实随机独立MySQL库；生成模型仍为替身。
- `npm --prefix frontend run build`：类型及生产构建通过，既有包体提示仍在。
- 独立5175前端 + `npm --prefix frontend run test:jd-assist`：真实Edge交互通过，API为合成替身，不修改开发库。覆盖粘贴自动提取、空字段合并、冲突保留、推理中编辑及先输入再清空仍不补回、条件采纳、原文/空薪资保存、超时回退、完善提议不自动采纳、未保存禁止生效及关闭后的迟到返回。初次测试定位textarea失败，修正测试定位器后通过；不是业务修复或真实API集成宣称。
- `.venv/Scripts/python.exe scripts/evaluate-jd.py`：实际调用已配置生成模型，两份合成样本。最终完整JD返回9项有效建议，在10个实际有输入字段中漏description；薪资/地点/技能/学历/年限依据通过校验。简略完善样本返回3项建议，无薪资/地点/福利虚构返回；两次运行有建议数量波动。结果仅保存在忽略目录data/stage-three-evaluation/jd.json。不代表总体准确率或所有注入/矛盾场景已验证；真实模型的提取遗漏需HR补齐，仍受生效必填拦截。
- `.venv/Scripts/python.exe -m pytest -q --tb=short -p no:cacheprovider`：完整59 passed /176.09秒（前两阶段及岗位需求/JD全部回归）。没有执行真实API→浏览器→生成模型的完整连通验收；各层验证范围如上，不合称真实全链路通过。

第三阶段仍进行中。下一步S3-03独立匹配任务、不可变范围/资料快照和可靠恢复，再进入S3-04评分与全范围语义排序。代码提交c57c15a；文档提交以git log为准。独立5175测试前端已关闭。开发库仍未应用第三阶段迁移/重载API，未修改现有账号授权。
