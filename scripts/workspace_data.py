"""由用户授权的虚构业务资料；不是实际候选人，也不预设AI结果。"""
from datetime import date

DEPARTMENTS = ['技术研发部','智能应用部','数据平台部','产品设计部','企业运营部','人力资源部']
POOLS = ['社会招聘','内推人才','校园招聘','长期关注']
TRACKS = {
    'ai': ('AI应用工程师','智能应用部','计算机科学与技术',['Python','RAG','LangGraph','Milvus','Docker'],
        ['企业知识助手','售后工单助手','合同信息抽取平台'],
        ['负责知识切分、混合检索与引用追溯，建立240条人工标注问答，完成灰度上线和持续监控，服务销售及交付团队。',
         '使用LangGraph编排检索和证据核验，设计工具权限边界与失败重试，接入既有业务系统，月处理约2万次问答。',
         '实现PDF文档解析和字段抽取，保留原文位置，增加人工校对与版本保护，负责接口开发及容器化部署。']),
    'python': ('Python后端工程师','技术研发部','软件工程',['Python','FastAPI','MySQL','Redis','Celery','Docker'],
        ['供应链协同平台','订单履约中心','设备运维平台'],
        ['负责订单与库存接口，使用MySQL事务和幂等键控制重复提交；通过Celery处理异步任务，完善告警、重试及审计。',
         '设计组织权限和数据范围，优化批量查询与慢SQL，将常用列表接口响应从1.2秒降至300毫秒左右。',
         '负责设备事件接入、工单流转和文件管理，完成Docker部署、健康检查和运行文档，参与季度恢复演练。']),
    'frontend': ('前端工程师','产品设计部','计算机科学与技术',['TypeScript','Vue 3','Element Plus','Vite','CSS'],
        ['客户运营工作台','渠道管理系统','项目交付门户'],
        ['使用Vue 3和TypeScript构建多角色工作台，负责复杂筛选、表格、表单校验和上传体验，适配笔记本及大屏。',
         '重构跨页面状态和请求取消逻辑，避免迟到响应覆盖当前选择，完善键盘操作、错误反馈及组件文档。',
         '维护统一组件与设计变量，优化代码分包和首屏加载，结合用户访谈改善审批、检索与批量操作流程。']),
    'data': ('数据工程师','数据平台部','数据科学与大数据技术',['Python','SQL','Airflow','Spark','MySQL'],
        ['经营数据中台','客户指标体系','实时经营看板'],
        ['建设订单、客户及财务主题数据集，使用Airflow编排每日同步，设置数据质量规则和失败告警，维护字段口径。',
         '使用SQL和Spark完成多源数据清洗与聚合，处理重复、迟到与缺失数据，为经营分析提供稳定数据服务。',
         '负责指标需求沟通、ETL开发和数据血缘，支持渠道转化与续费分析，并建立权限分层和敏感字段脱敏规范。']),
    'java': ('Java开发工程师','技术研发部','软件工程',['Java','Spring Boot','MySQL','Redis','Kafka'],
        ['会员权益中心','交易结算平台','企业采购平台'],
        ['负责会员、权益和订单服务，使用Spring Boot实现业务接口，维护事务一致性、消息补偿及接口幂等。',
         '优化结算批处理和数据库索引，完善Redis缓存失效策略，参与上线值守、故障复盘及容量评估。',
         '负责供应商准入和采购履约模块，接入Kafka业务事件，编写接口文档及自动化回归用例。']),
    'quality': ('质量工程师','技术研发部','信息管理与信息系统',['Python','Playwright','SQL','Postman','JMeter'],
        ['客户平台质量保障','交易链路质量建设','数据平台验收体系'],
        ['围绕登录权限、订单和文件链路建立接口及页面回归，使用Playwright维护关键流程，定位并跟进线上缺陷。',
         '梳理并发提交、异常恢复和跨角色访问场景，开展接口压力评估，输出问题复现步骤与上线风险清单。',
         '建立数据校验规则和发布验收清单，核对指标口径、历史数据回补及任务补偿，协同研发完成问题闭环。']),
    'product': ('产品经理','企业运营部','信息管理与信息系统',['需求分析','业务流程','原型设计','SQL','数据分析'],
        ['企业服务运营平台','销售协作工作台','智能知识产品'],
        ['负责用户访谈、业务流程和需求优先级，输出原型及验收标准，协调研发、设计和运营完成迭代。',
         '梳理线索到交付的协作流程，设计权限和关键指标，结合SQL分析定位使用瓶颈，推动跨部门上线。',
         '负责知识助手的场景选择、内容治理和效果反馈，区分可核验事实与生成建议，组织业务人员验收。']),
    'hr': ('人力资源经理','人力资源部','人力资源管理',['招聘管理','人才盘点','组织发展','数据分析'],
        ['年度人才盘点','研发团队招聘','员工成长计划'],
        ['负责技术岗位需求沟通、招聘渠道和人才库维护，组织跨部门人才盘点与员工能力发展。']),
}

EXTERNAL_NAMES = {
    'ai':['周奕辰','林沐言','沈知远','许清禾','陆嘉宁','江予安','苏景行','叶舒然'],
    'python':['陈思远','方子墨','何昱辰','宋佳宁','杜若溪','顾明泽'],
    'frontend':['唐雨桐','许安然','程以宁','温书瑶','韩子谦','邵云舒'],
    'data':['梁知夏','谢景澄','孟星河','陶予晴','钟亦凡','邱若宁'],
    'java':['赵承宇','傅明轩','袁泽川','魏嘉禾'],
    'quality':['郑南乔','蒋亦宁','曹书昀'],
    'product':['陆予棠','秦知微','贺景和'],
}
INTERNAL = [
    ('陈瑜','chen.yu','python',6),('罗宸','luo.chen','ai',9),('郭宁','guo.ning','frontend',5),
    ('林致远','lin.zhiyuan','data',7),('徐婧','xu.jing','product',6),('赵铭','zhao.ming','java',8),
    ('唐佳','tang.jia','quality',4),('吴彤','wu.tong','data',3),('周妍','zhou.yan','hr',8),
    ('林静','lin.jing','hr',5),('苏晴','su.qing','frontend',3),('何川','he.chuan','ai',4),
]
SCHOOLS = ['杭州电子科技大学','南京信息工程大学','浙江工业大学','江苏大学','重庆邮电大学','西安邮电大学',
           '上海大学','武汉理工大学','成都信息工程大学','安徽大学','苏州大学','浙江理工大学']
COMPANIES = ['青禾云科','瀚舟信息','云栈数字','星澜科技','知行互联','云岑软件','远帆数据','启序科技']
SOURCE_NAMES = {'周奕辰','林沐言','沈知远','陈思远','方子墨','唐雨桐','梁知夏','陆予棠'}
EMAIL_NAMES = ['zhou.yichen','lin.muyan','shen.zhiyuan','xu.qinghe','lu.jianing','jiang.yuan','su.jingxing','ye.shuran',
    'chen.siyuan','fang.zimo','he.yuchen','song.jianing','du.ruoxi','gu.mingze','tang.yutong','xu.anran','cheng.yining',
    'wen.shuyao','han.ziqian','shao.yunshu','liang.zhixia','xie.jingcheng','meng.xinghe','tao.yuqing','zhong.yifan',
    'qiu.ruoning','zhao.chengyu','fu.mingxuan','yuan.zechuan','wei.jiahe','zheng.nanqiao','jiang.yining','cao.shuyun',
    'lu.yutang','qin.zhiwei','he.jinghe'] + [person[1] for person in INTERNAL]
REQUIREMENTS = [
    ('企业知识助手 AI应用工程师','ai',['Python','RAG'],['LangGraph','Milvus'],3,'本科',22000,32000,'杭州','active'),
    ('业务平台 Python后端工程师','python',['Python','MySQL'],['FastAPI','Celery'],4,'本科',18000,28000,'杭州','active'),
    ('客户工作台 前端工程师','frontend',['Vue 3','TypeScript'],['Element Plus','CSS'],3,'本科',16000,24000,'杭州','active'),
    ('经营数据平台 数据工程师','data',['SQL','Python'],['Airflow','Spark'],3,'本科',18000,26000,'上海','active'),
    ('交易结算 Java开发工程师','java',['Java','Spring Boot'],['Kafka','Redis'],4,'本科',18000,28000,'杭州','active'),
    ('企业服务 产品经理','product',['需求分析'],['SQL','数据分析'],4,'本科',20000,30000,'上海','draft'),
    ('交付平台 质量工程师','quality',['Playwright'],['Python','SQL'],2,'不限',13000,19000,'杭州','disabled'),
]


def people():
    result = []
    for track, names in EXTERNAL_NAMES.items():
        for index, name in enumerate(names):
            result.append(profile(name,track,2+(index*2+list(EXTERNAL_NAMES).index(track))%8,
                len(result), 'external'))
    for name,username,track,years in INTERNAL:
        item = profile(name,track,years,len(result),'internal')
        item['username'] = username
        result.append(item)
    assert len(result) == 48 and len({p['name'] for p in result}) == 48
    return result


def profile(name, track, years, index, kind):
    title,department,major,skills,projects,descriptions = TRACKS[track]
    degree = '硕士' if index%7==1 else '大专' if index%11==8 else '本科'
    school = SCHOOLS[index%len(SCHOOLS)] if degree!='大专' else '杭州职业技术学院'
    graduation = 2026-years
    selected = list(skills)
    if kind=='external' and index%5==3:
        selected=selected[:2]
    if kind=='external' and index%9==5:
        selected=selected[1:]
    if track=='ai' and index==2:
        degree='硕士'
    study_years = 3 if degree in ('硕士','大专') else 4
    recent_start = 2026-min(3,years)
    facts=[{'category':'education','content':f'{graduation-study_years}年9月 - {graduation}年6月  {school}  {major}  {degree}毕业'},
        {'category':'experience','content':f'{recent_start}年7月至今，{COMPANIES[index%len(COMPANIES)]} {title}。总工作经验{years}年，负责需求评审、方案设计、开发交付和运行维护。'},
        {'category':'project','content':f'{2024-index%2}年3月 - {2026-index%2}年6月  {projects[index%len(projects)]}。{descriptions[index%len(descriptions)]}'},
        {'category':'skill','content':'、'.join(selected)}]
    if years>3:
        facts.append({'category':'experience','content':f'{graduation}年7月 - {recent_start}年6月  {COMPANIES[(index+3)%len(COMPANIES)]}  {title}。参与核心业务模块建设，与产品及交付团队核对需求和上线效果。'})
    if years>=4:
        facts.append({'category':'project','content':f'{max(graduation+1,2022)}年8月 - 2024年2月  {projects[(index+1)%len(projects)]}。{descriptions[(index+1)%len(descriptions)]}'})
    if index%4!=2 and track in ('ai','python','data','java'):
        main='Java' if track=='java' else 'Python'
        facts.append({'category':'skill','content':f'{main}开发经验{max(1,years-1)}年，能够独立完成模块设计、实现和交付。'})
    if index%3==0:
        facts.append({'category':'certificate','content':'大学英语六级，能够阅读技术文档并参与英文需求讨论。'})
    if index%8==4:
        facts.append({'category':'certificate','content':'计算机技术与软件专业技术资格 软件设计师，2023年取得。'})
    return {'name':name,'track':track,'kind':kind,'department':department,'title':title,
        'years':years,'degree':degree,'phone':f'{[138,186,159,187][index%4]}{32005891+index*18743:08d}',
        'email':EMAIL_NAMES[index]+'@mail.example','facts':facts,
        'pool':POOLS[index%len(POOLS)],'source':name in SOURCE_NAMES,
        'expected_salary':f'{14+years}-{20+years}K','availability':['两周内到岗','一个月内到岗','在职，机会合适可沟通'][index%3]}
