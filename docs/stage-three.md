# 第三阶段：岗位需求与全范围匹配

2026-11-06（北京时间），李玉杰明确确认第二阶段已验收、远端已更新审批，并授权开始第三阶段。基线为 origin/codex/stage-two-resume 872664d；开发分支 codex/stage-three-requirements。第二阶段页面体验及“未确认”语义优化仍按远端决定暂缓，人工保护不取消。

## 实施顺序及状态

1. S3-01 岗位需求基础闭环：已实现，后端自动化验证及前端构建结果见本页下方。真实页面人工验收未进行。
2. S3-02 同表单 JD 自动提取与可选 AI 完善：未开始。保留原文，空字段回填、冲突给差异；不编造薪资地点等企业事实；失败可继续手填。
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
- 单表单支持人工完整维护、暂存、确认生效、停用和查看完整历史；页面有未保存修改时不能确认生效。JD辅助和匹配没有可用按钮，不用固定结果代替。

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
