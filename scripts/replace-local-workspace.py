"""用户明确授权后使用的本机资料替换器；默认仅预览，必须有完整离线备份。"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import secrets
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from sqlalchemy import create_engine, delete, select, update, func, event
from sqlalchemy.orm import Session as DbSession
from app.core import config
from app.core.db import Base, engine, Session
from app.core.security import hash_password
from app.models.entities import Department,Position,DepartmentPosition,Pool,Role,User,UserRole,Grant,Talent,uid
from app.services.business import save_talent, audit
from app.schemas.inputs import TalentInput
from workspace_data import DEPARTMENTS,POOLS,TRACKS,INTERNAL,people


def load_backup_module():
    spec=importlib.util.spec_from_file_location('workspace_backup',ROOT/'scripts/backup-local.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def replace_rows(db, actors):
    """在单事务内删除旧业务行并重建基础资料；不改表结构或迁移版本。"""
    old_ids=list(db.scalars(select(Talent.id)))
    # 显式断开用户和人才的循环外键，始终保留外键校验，不TRUNCATE/删库。
    db.execute(update(User).values(talent_id=None,department_id=None))
    db.execute(update(Talent).values(owner_id=None))
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(delete(table))
    db.expunge_all()
    departments={name:Department(name=name) for name in DEPARTMENTS}
    pools={name:Pool(name=name) for name in POOLS}
    positions={track:Position(name=spec[0]) for track,spec in TRACKS.items()}
    db.add_all([*departments.values(),*pools.values(),*positions.values()]);db.flush()
    department_positions={track:DepartmentPosition(department_id=departments[spec[1]].id,
        position_id=positions[track].id) for track,spec in TRACKS.items()}
    db.add_all(department_positions.values());db.flush()
    roles={key:Role(name=name) for key,name in [('admin','系统管理员'),('hr','人力资源经理'),
        ('employee','员工'),('manager','智能应用负责人')]}
    db.add_all(roles.values());db.flush()
    for action in ('account.manage','catalog.manage','audit.read'):
        db.add(Grant(role_id=roles['admin'].id,action=action,scope='global'))
    for action in ('talent.read','talent.write','file.read','file.write','task.run','assessment.assign','assessment.read','chat.use'):
        for scope in ('internal_all','external_all'):
            db.add(Grant(role_id=roles['hr'].id,action=action,scope=scope))
    for action in ('requirement.read','requirement.write','assessment.manage'):
        db.add(Grant(role_id=roles['hr'].id,action=action,scope='global'))
    for action in ('talent.read','file.read','chat.use','assessment.read'):
        db.add(Grant(role_id=roles['employee'].id,action=action,scope='self'))
        db.add(Grant(role_id=roles['manager'].id,action=action,scope='department',scope_id=departments['智能应用部'].id))
    db.add(Grant(role_id=roles['manager'].id,action='requirement.read',scope='department',scope_id=departments['智能应用部'].id))
    users={}
    users['admin']=User(id=actors['admin']['id'],username='admin',password_hash=actors['admin']['password_hash'],
        version=actors['admin']['version']+1)
    passwords={}
    for name,username,track,_ in INTERNAL:
        preserved=actors.get(username)
        if preserved:
            account=User(id=preserved['id'],username=username,password_hash=preserved['password_hash'],version=preserved['version']+1)
        else:
            passwords[username]=secrets.token_urlsafe(16)
            account=User(username=username,password_hash=hash_password(passwords[username]))
        account.department_id=departments[TRACKS[track][1]].id
        users[username]=account
    db.add_all(users.values());db.flush()
    for username,user in users.items():
        role='admin' if username=='admin' else 'hr' if username in ('zhou.yan','lin.jing') else 'manager' if username=='luo.chen' else 'employee'
        db.add(UserRole(user_id=user.id,role_id=roles[role].id))
    db.flush()
    hr=users['zhou.yan'];records={}
    for index,person in enumerate(people()):
        if person['source']:
            continue  # 原文件资料必须通过真实导入/Worker/模型生成，不伪造解析结果。
        values={key:person[key] for key in ('name','kind','phone','email','facts')}
        if person['kind']=='internal':
            values.update(department_id=departments[person['department']].id,
                department_position_id=department_positions[person['track']].id)
        else:
            values.update(owner_id=users['zhou.yan' if index%2==0 else 'lin.jing'].id,pool_id=pools[person['pool']].id)
        record=save_talent(db,hr,TalentInput.model_validate(values),uid())
        records[person['name']]=record.id
        if person.get('username'):
            users[person['username']].talent_id=record.id
    audit(db,users['admin'],'workspace.initialize',None,uid())
    db.flush()
    return {'old_talent_ids':old_ids,'people':records,'users':{name:user.id for name,user in users.items()},
        'department_positions':{track:obj.id for track,obj in department_positions.items()},
        'pools':{name:pool.id for name,pool in pools.items()}},passwords


def check():
    folder=ROOT/'data/workspace';folder.mkdir(parents=True,exist_ok=True)
    path=folder/('constraints-'+uuid.uuid4().hex+'.db')
    isolated=create_engine('sqlite:///'+path.as_posix())
    @event.listens_for(isolated,'connect')
    def foreign_keys(connection,_):connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(isolated)  # 仅刚创建的隔离资料检查库。
    actors={name:{'id':uid(),'password_hash':hash_password(secrets.token_urlsafe(16)),'version':1}
        for name in ('admin','zhou.yan','chen.yu')}
    with DbSession(isolated) as db,db.begin():
        replace_rows(db,actors)
    with DbSession(isolated) as db,db.begin():
        replace_rows(db,actors)
        assert db.scalar(select(func.count()).select_from(Talent))==40
        assert db.scalar(select(func.count()).select_from(User))==13
        assert db.get(User,actors['admin']['id']).password_hash==actors['admin']['password_hash']
    isolated.dispose()
    # 仅清理本次随机创建且已核对位于工作区内的隔离文件。
    assert path.resolve().is_relative_to(folder.resolve()) and path.name.startswith('constraints-')
    path.unlink()
    print('Constraint check passed: transactional replacement, foreign keys, 40 initial profiles, 13 accounts')


def apply(backup_path):
    if Path.cwd().resolve()!=ROOT or engine.url.database!='talent' or engine.url.host!='127.0.0.1' or engine.url.port!=13306:
        raise RuntimeError('TARGET_MUST_BE_EXISTING_LOCAL_PROJECT')
    backup_path=backup_path.resolve()
    if not backup_path.is_relative_to((ROOT/'data/backups').resolve()):
        raise RuntimeError('BACKUP_OUTSIDE_PROJECT')
    backup=load_backup_module();backup.require_offline()
    manifest=json.loads((backup_path/'manifest.json').read_text(encoding='utf-8'))
    if backup.counts('talent')!=manifest['table_counts'] or hashlib.sha256((backup_path/'database.sql').read_bytes()).hexdigest()!=manifest['database_sha256']:
        raise RuntimeError('BACKUP_MUST_MATCH_CURRENT_DATABASE')
    file_root=config.FILE_ROOT.resolve()
    if file_root!=(ROOT/'data/files').resolve() or backup.hashes(file_root)!=manifest['files'] or backup.hashes(backup_path/'files')!=manifest['files']:
        raise RuntimeError('BACKUP_FILES_MUST_MATCH_PROJECT_FILE_ROOT')
    access=(ROOT/'data/local-access.txt').read_text(encoding='utf-8')
    admin_password=re.search(r'^admin: (.+)$',access,re.M)[1]
    main_password=re.search(r'^demo.hr / demo.employee: (.+)$',access,re.M)[1]
    with Session.begin() as db:
        actors={}
        for old,new in [('admin','admin'),('demo.hr','zhou.yan'),('demo.employee','chen.yu')]:
            user=db.scalar(select(User).where(User.username==old))
            if not user:raise RuntimeError('ORIGINAL_LOGIN_ACCOUNT_MISSING_REFUSING_REPEAT')
            actors[new]={'id':user.id,'password_hash':user.password_hash,'version':user.version}
        output,passwords=replace_rows(db,actors)
    # 事务已成功，再清理已备份的原文件。逐个核对绝对路径，不递归删除或跨目录。
    for relative in manifest['files']:
        path=(file_root/relative).resolve()
        if not path.is_relative_to(file_root) or path.is_symlink():
            raise RuntimeError('UNEXPECTED_FILE_PATH')
        path.unlink()
    lines=['本机账号，请勿提交或分享。','admin: '+admin_password,
        'zhou.yan: '+main_password,'chen.yu: '+main_password]
    lines.extend(name+': '+password for name,password in passwords.items())
    (ROOT/'data/local-access.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    folder=ROOT/'data/workspace';folder.mkdir(parents=True,exist_ok=True)
    output.update({'backup':str(backup_path),'fictional_dataset':True,'expected_people':48,'source_profiles_pending':8})
    (folder/'installed.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Workspace foundation replaced: 40 profiles, 13 accounts; 8 source profiles await real import')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--replace-local-data',action='store_true')
    parser.add_argument('--backup',type=Path)
    args=parser.parse_args()
    if args.check:check()
    elif args.replace_local_data and args.backup:apply(args.backup)
    elif args.replace_local_data:parser.error('an existing verified offline backup is required')
    else:print('Preview: 48 people (36 external, 12 internal), 13 accounts, 6 departments, 7 requirements; no data changed')


if __name__=='__main__':main()
