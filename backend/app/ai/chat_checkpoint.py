"""LangGraph同步MySQL检查点适配器；仅JSON，不反序列化任意Python对象。"""
import json
from sqlalchemy import select
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from app.core.db import Session
from app.models.chat_entities import ChatCheckpoint, ChatJob


class MySQLChatSaver(BaseCheckpointSaver):
    def _gate(self,db,config):
        from app.services.archive_chat import actor
        cfg=config['configurable']
        jid,version=cfg['thread_id'],cfg['run_version']
        actor(db,db.get(ChatJob,jid),version)
        return jid,version

    def _config(self,config,cid):
        return {'configurable':{**config['configurable'],'checkpoint_id':cid,'checkpoint_ns':''}}

    def get_tuple(self,config):
        with Session() as db:
            jid,version=self._gate(db,config)
            query=select(ChatCheckpoint).where(ChatCheckpoint.job_id==jid,ChatCheckpoint.run_version==version)
            cid=config['configurable'].get('checkpoint_id')
            if cid:query=query.where(ChatCheckpoint.checkpoint_id==cid)
            item=db.scalar(query.order_by(ChatCheckpoint.checkpoint_id.desc()).limit(1))
            if not item:return None
            return CheckpointTuple(self._config(config,item.checkpoint_id),item.checkpoint,item.checkpoint_metadata,
                self._config(config,item.parent_id) if item.parent_id else None,
                [(w['task'],w['channel'],w['value']) for w in item.writes])

    def put(self,config,checkpoint,metadata,new_versions):
        # roundtrip拒绝对象/可执行序列化，只允许本流程的原始JSON状态。
        checkpoint,metadata=json.loads(json.dumps([checkpoint,metadata]))
        with Session.begin() as db:
            jid,version=self._gate(db,config)
            db.add(ChatCheckpoint(job_id=jid,run_version=version,checkpoint_id=checkpoint['id'],
                parent_id=config['configurable'].get('checkpoint_id'),checkpoint=checkpoint,
                checkpoint_metadata=metadata,writes=[]))
        return self._config(config,checkpoint['id'])

    def put_writes(self,config,writes,task_id,task_path=''):
        with Session.begin() as db:
            jid,version=self._gate(db,config)
            item=db.scalar(select(ChatCheckpoint).where(ChatCheckpoint.job_id==jid,ChatCheckpoint.run_version==version,
                ChatCheckpoint.checkpoint_id==config['configurable']['checkpoint_id']).with_for_update())
            if item is None:raise ValueError('CHECKPOINT_NOT_FOUND')
            saved={(w['task'],w['index']):w for w in item.writes}
            for i,(channel,value) in enumerate(writes):
                saved[(task_id,i)]={'task':task_id,'index':i,'channel':channel,'value':json.loads(json.dumps(value))}
            item.writes=list(saved.values())

    def list(self,config,*,filter=None,before=None,limit=None):
        if config is None:raise ValueError('EXPLICIT_JOB_REQUIRED')
        with Session() as db:
            jid,version=self._gate(db,config)
            query=select(ChatCheckpoint.checkpoint_id).where(ChatCheckpoint.job_id==jid,ChatCheckpoint.run_version==version)
            if before:query=query.where(ChatCheckpoint.checkpoint_id<before['configurable']['checkpoint_id'])
            ids=list(db.scalars(query.order_by(ChatCheckpoint.checkpoint_id.desc()).limit(min(limit or 100,100))))
        for cid in ids:
            item=self.get_tuple(self._config(config,cid))
            if not filter or all(item.metadata.get(k)==v for k,v in filter.items()):yield item
