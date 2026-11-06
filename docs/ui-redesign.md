# UI 重构实施记录

2026-11-06，基线424723e；独立分支codex/ui-ux-redesign。第五阶段未启动。

## 已核实的问题与功能
真实Edge登录三类合成账号：HR可用工作台、候选人、档案、聊天、岗位、任务、测评；员工为本人范围，没有聊天与管理；管理员只有工作台和系统管理，没有人才正文。旧界面一级导航平铺、人才事实表格过密、正常来源重复“未确认”、档案聊天离开详情。现有导入/逐文件失败、筛选分页、人工编辑、文件证据、JD/匹配、测评、账号/角色/基础资料/审计全部保留。

## 设计与入口映射
- 工作台：实时统计＋按当前菜单和动作交集显示的快捷入口。
- 人才工作分组：候选人筛选（卡片、多选、分页、导入折叠区）、人才档案（维护）、档案聊天（历史）、任务记录（进度）。
- 招聘与成长：岗位需求（统一表单内JD辅助与匹配）、轻量测评（保留角色按钮分离）。
- 系统管理：角色/菜单、账号、基础资料、操作审计，不给管理员扩正文权限。
- 人才卡片→档案主体＋右侧可收起AI→来源弹窗/下载→关闭详情回到原筛选及页码。多人/筛选聊天在人才列表旁打开；沿用ChatWorkspace，不添加新Agent。
- 正常来源显示简历声明/人工维护，冲突与异常仍使用原quality及更新建议，不改确认数据库状态。

## Tokens与布局
主色#2563eb、深导航#15243b、底色#f5f7fb、白卡片；文字#1e293b/次级#526176；警告#a16207。中文系统字体栈，无外部字体；4/8间距，12px卡片圆角，轻阴影。统一映射Element Plus变量。卡片桌面3列，中屏2列，小屏1列；档案宽屏双栏，窄屏上下排列。可见焦点、减少动态效果、长内容换行。

## Skill
来源https://github.com/nextlevelbuilder/ui-ux-pro-max-skill；固定安装器ui-ux-pro-max-cli@2.15.0；项目级.agents/skills/ui-ux-pro-max，scripts/data已核对（该版不提供references目录）。实际执行npm exec --yes --package=ui-ux-pro-max-cli@2.15.0 -- uipro init --help及init --ai codex，无force/global。安装内容下一轮自动发现，本轮已直接完整阅读SKILL并运行检索。
解释器C:/Users/Windows/anaconda3/python.exe，脚本使用本项目scripts/search.py绝对路径。查询：recruiting talent workspace modern --design-system -p AI Talent Platform -f markdown；card selection detail panel --domain ux（无结果，重试state preservation）；components state forms --stack vue。采用留白、对比、导航状态和状态保留建议；弃用Hero/CTA营销布局、Google字体及为表单/状态引入新库的推荐，复用Vue和Element Plus。

## 验收点
真实API筛选（含requirement_id与未应用输入区分）、分页多选、详情首次发问/直接答案/引用、返回原位置、会话切换与迟到隔离；JD/匹配、员工答题、管理权限；1440×900与1366×768及窄视口。截图只保存本机忽略data目录。验证记录随实现补充。
