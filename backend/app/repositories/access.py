"""权限相关数据访问；范围的业务含义由 core.security 决定。"""
from sqlalchemy import select, func, not_, and_
from app.models.entities import Grant, UserRole, Talent, Fact, TalentHistory, Task, File


def current_task_file(db, task: Task, lock: bool = False) -> File | None:
    """文件当前归属才是来源边界，旧任务不能借旧人才ID读取已移走的材料。"""
    query = select(File).where(File.id == task.file_id).execution_options(populate_existing=True)
    source = db.scalar(query.with_for_update() if lock else query)
    return source if source and source.talent_id == task.talent_id else None


def effective_talent_clause():
    # 导入尚未产生有效资料的占位行只属于任务视角。
    return not_(and_(Talent.name == '待解析', Talent.version == 1))

def current_grants(db, user_id: str, action: str):
    return list(db.scalars(select(Grant).join(UserRole, Grant.role_id == UserRole.role_id).where(UserRole.user_id == user_id, Grant.action == action)))

def scoped_talent(db, talent_id: str, condition):
    return db.scalar(select(Talent).where(Talent.id == talent_id, condition))

def talent_page(db, condition, offset: int, limit: int):
    items = list(db.scalars(select(Talent).where(condition).order_by(Talent.id).offset(offset).limit(limit)))
    total = db.scalar(select(func.count()).select_from(Talent).where(condition))
    return items, total

def talent_facts(db, talent_id: str):
    return list(db.scalars(select(Fact).where(Fact.talent_id == talent_id)))

def talent_history(db, talent_id: str):
    return list(db.scalars(select(TalentHistory).where(TalentHistory.talent_id == talent_id).order_by(TalentHistory.version.desc())))


def task_page(db, condition, offset: int, limit: int):
    # 先按当前人才权限过滤，再分页和计数，避免总数泄露其他范围。
    query = select(Task).join(Talent, Task.talent_id == Talent.id).where(condition)
    items = list(db.scalars(query.order_by(Task.id).offset(offset).limit(limit)))
    total = db.scalar(select(func.count()).select_from(Task).join(Talent, Task.talent_id == Talent.id).where(condition))
    return items, total
