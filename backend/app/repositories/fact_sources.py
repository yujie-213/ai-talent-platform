"""给已授权事实补充可核对来源；文件读权与当前文件/任务归属独立检查。"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import allowed
from app.models.entities import File, ResumeRecord, Talent, Task, User


def attach_sources(db: Session, user: User, talent: Talent, facts: list[dict]) -> list[dict]:
    if not allowed(db, user, 'file.read', talent):
        return facts
    records = db.execute(select(ResumeRecord, Task).join(Task, Task.id == ResumeRecord.task_id)
        .join(File, File.id == Task.file_id).where(Task.talent_id == talent.id,
            File.talent_id == talent.id, Task.state == 'succeeded')
        .order_by(ResumeRecord.task_id, ResumeRecord.run_version)).all()
    for fact in facts:
        if fact['source_type'] != 'resume':
            continue
        for record, task in records:
            if record.base_version + 1 != fact['source_version'] or not record.validated:
                continue
            for field in record.validated.get('fields', []):
                if field['category'] == fact['category'] and field['value'] == fact['content']:
                    fact.update(source_file_id=task.file_id, source_task_id=task.id,
                        locator=field['locator'], quote=field['quote'])
    return facts
