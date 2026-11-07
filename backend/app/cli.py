"""本机受控管理入口；密码只通过隐藏输入或环境变量传入。"""
import argparse
import getpass
import os
import time
from sqlalchemy import select, func
from app.core.db import Session
from app.core.security import hash_password
from app.models.entities import User, Role, UserRole, Grant, Department, Position, DepartmentPosition, Pool, Talent

def bootstrap(username: str, password: str):
    if len(password) < 12:
        raise ValueError('密码至少 12 字符')
    with Session.begin() as db:
        if db.scalar(select(func.count()).select_from(User)):
            raise ValueError('已有账号，禁止重复引导')
        role = Role(name='系统管理')
        user = User(username=username, password_hash=hash_password(password))
        db.add_all([role, user])
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        for action in ('account.manage', 'catalog.manage', 'audit.read'):
            db.add(Grant(role_id=role.id, action=action, scope='global'))

def seed(password: str):
    if len(password) < 12:
        raise ValueError('合成账号密码至少 12 字符')
    with Session.begin() as db:
        if db.scalar(select(User).where(User.username == 'demo.hr')):
            raise ValueError('合成数据已存在，不重复写入')
        a, b = Department(name='合成研发部'), Department(name='合成产品部')
        pos, pool = Position(name='合成工程师'), Pool(name='合成人才库')
        hr, emp = User(username='demo.hr', password_hash=hash_password(password)), User(username='demo.employee', password_hash=hash_password(password))
        hr_role, emp_role = Role(name='合成HR'), Role(name='合成员工')
        db.add_all([a, b, pos, pool, hr, emp, hr_role, emp_role])
        db.flush()
        dp1 = DepartmentPosition(department_id=a.id, position_id=pos.id)
        dp2 = DepartmentPosition(department_id=b.id, position_id=pos.id)
        db.add_all([dp1, dp2])
        db.flush()
        t = Talent(name='合成员工甲', kind='internal', department_id=a.id, department_position_id=dp1.id, email='synthetic@example.invalid')
        ext = Talent(name='合成候选人乙', kind='external', owner_id=hr.id, pool_id=pool.id, email='candidate@example.invalid')
        db.add_all([t, ext])
        db.flush()
        emp.talent_id, emp.department_id = t.id, a.id
        db.add_all([UserRole(user_id=hr.id, role_id=hr_role.id), UserRole(user_id=emp.id, role_id=emp_role.id)])
        for action in ('talent.read', 'talent.write', 'file.read', 'file.write', 'task.run'):
            for scope in ('internal_all', 'external_all'):
                db.add(Grant(role_id=hr_role.id, action=action, scope=scope))
        for action in ('talent.read', 'file.read'):
            db.add(Grant(role_id=emp_role.id, action=action, scope='self'))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['bootstrap', 'seed-demo', 'dispatch', 'recover', 'dispatcher', 'index', 'indexer', 'index-cleanup'])
    parser.add_argument('--username', default='admin')
    parser.add_argument('--after', default='', help='旧向量清理的上一批游标')
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    if args.command == 'bootstrap':
        bootstrap(args.username, os.getenv('BOOTSTRAP_PASSWORD') or getpass.getpass('本机管理员密码: '))
    elif args.command == 'seed-demo':
        seed(os.getenv('DEMO_PASSWORD') or getpass.getpass('合成测试账号密码: '))
    elif args.command == 'index-cleanup':
        import json
        from app.services.resume_index import cleanup_old_indexes
        report = cleanup_old_indexes(args.limit, args.after)
        print(json.dumps(report, ensure_ascii=True))
        if report['failed_profiles']:
            raise SystemExit(1)
    elif args.command in ['index', 'indexer']:
        from app.services.resume_index import compensate_indexes, enqueue_missing_indexes
        from sqlalchemy.exc import SQLAlchemyError
        while True:
            try:
                enqueue_missing_indexes()
                print('indexed:', compensate_indexes(), flush=True)
            except SQLAlchemyError:
                if args.command == 'index':
                    raise RuntimeError('INDEX_DATABASE_UNAVAILABLE') from None
                print('index cycle: database unavailable, retrying', flush=True)
            if args.command == 'index':
                break
            time.sleep(30)
    else:
        from app.tasks.worker import dispatch, recover
        from app.services.match_tasks import dispatch as dispatch_matches, recover as recover_matches
        from app.services.chat_jobs import dispatch as dispatch_chats, recover as recover_chats
        if args.command == 'dispatch':
            print('published:', dispatch() + dispatch_matches() + dispatch_chats())
        elif args.command == 'recover':
            print('recovered:', recover() + recover_matches() + recover_chats())
        else:
            while True:
                recover()
                recover_matches()
                recover_chats()
                dispatch()
                dispatch_matches()
                dispatch_chats()
                time.sleep(3)

if __name__ == '__main__':
    main()
