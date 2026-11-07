"""真实API/MySQL：同版本并发、同键幂等、三角色隔离及有限读取时延。"""
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import re
import statistics
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    access = (ROOT / 'data/local-access.txt').read_text(encoding='utf-8')
    admin = re.search(r'^admin: (.+)$', access, re.M)[1]
    demo = re.search(r'^demo.hr / demo.employee: (.+)$', access, re.M)[1]
    with httpx.Client(base_url='http://127.0.0.1:5173/api', timeout=60, trust_env=False) as client:
        tokens = {}
        for username, password in [('admin', admin), ('demo.hr', demo), ('demo.employee', demo)]:
            response = client.post('/auth/login', json={'username':username, 'password':password})
            response.raise_for_status()
            tokens[username] = response.json()['data']['token']
        hr = {'Authorization':'Bearer ' + tokens['demo.hr']}
        key = 'stage-five-' + uuid.uuid4().hex
        payload = {'kind':'external','name':'第五阶段合成并发验收-' + key[-8:],
                   'facts':[{'category':'skill','content':'Python 合成并发验收'}]}
        def create(_):
            response = client.post('/talents', headers={**hr, 'Idempotency-Key':key}, json=payload)
            response.raise_for_status()
            return response.json()['data']
        with ThreadPoolExecutor(max_workers=2) as pool:
            twins = list(pool.map(create, range(2)))
        assert twins[0]['id'] == twins[1]['id']
        changed = client.post('/talents', headers={**hr,'Idempotency-Key':key}, json={**payload,'name':'不同内容'})
        assert changed.status_code == 409
        profile = twins[0]
        body = {key:profile[key] for key in ('kind','name','phone','email','department_id','department_position_id','owner_id','pool_id','version')}
        body['facts'] = [{'category':f['category'],'content':f['content']} for f in profile['facts']]
        def edit(index):
            return client.put('/talents/' + profile['id'], headers=hr,
                json={**body,'name':payload['name'] + str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            edit_codes = sorted(pool.map(edit, range(2)))
        assert edit_codes == [200,409]
        for name in ('admin','demo.employee'):
            response = client.get('/talents/' + profile['id'], headers={'Authorization':'Bearer ' + tokens[name]})
            assert response.status_code == 404
        def measure(_):
            started = time.perf_counter()
            response = client.get('/workbench', headers=hr)
            response.raise_for_status()
            return (time.perf_counter() - started) * 1000
        def stats(values):
            ordered = sorted(values)
            return {'requests':len(values), 'p50_ms':round(statistics.median(values),2),
                'p95_ms':round(ordered[math.ceil(.95 * len(ordered))-1],2), 'max_ms':round(max(values),2)}
        sequential = [measure(index) for index in range(20)]
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as pool:
            parallel = list(pool.map(measure, range(20)))
        elapsed = time.perf_counter() - started
        report = {'real_services':['frontend-proxy','API','MySQL'], 'synthetic_profile_id':profile['id'],
            'same_key_unique_profile':True, 'same_key_changed_body_conflict':True,
            'same_version_parallel_statuses':edit_codes, 'admin_employee_isolated':True,
            'workbench_sequential':stats(sequential), 'workbench_concurrency_4':stats(parallel),
            'parallel_elapsed_seconds':round(elapsed,2), 'not_a_capacity_or_production_load_test':True}
        folder = ROOT / 'data/stage-five'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'api-concurrency-performance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('Real API concurrency/idempotency/isolation: passed')
        print('workbench sequential:', json.dumps(stats(sequential)))
        print('workbench concurrency=4:', json.dumps(stats(parallel)))


if __name__ == '__main__':
    main()
