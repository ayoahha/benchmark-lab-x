"""Technical recovery preserves the task, money and every earlier receipt"""
from base64 import b64encode
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from benchmark_lab_x import campaigns as c, qualification as q, recovery as r, storage
from tests.test_s3_regressions import fixture, specification, check, ACTOR, AUTHORITY
from tests.test_s4_regressions import manifest, inputs, response


class Recovery(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name).resolve() / 'private'
        sid, view, ref = fixture(self.data)
        q.initialize(self.data); c.initialize(self.data)
        self.store = storage.Store(self.data); self.addCleanup(self.store.close)
        spec = specification(ref); spec['cost_basis']['unit'] = 'USD'
        draft = q.draft(self.store, 'fixture', view['revision'], spec)
        qualified = q.qualify(self.store, draft['contract_sha256'], reviewer=ACTOR, check=check)
        q.approve(self.store, draft['contract_sha256'], qualified['qualification_id'], actor=ACTOR, authority=AUTHORITY)
        m = manifest(draft); m['financial_cost_policy'] = 'retain_reserve'
        m['conditions']['defaults'] = {'context_window': 10000}
        for p in m['panel']:
            p.update(model='fixture/'+p['id'], revision='rev-'+p['id'],
                     parameters={'max_tokens':100,'provider':{'only':['one','two'],'order':['one','two'],
                     'allow_fallbacks':True,'require_parameters':True}})
        self.store.create_budget('local-comparison','40','USD')
        c.create(self.store,m)
        self.admit('local-comparison')
        self.caps = dict(id='fixture/x', endpoints=[dict(tag=t,status=0,max_completion_tokens=1000,
             context_length=10000,supported_parameters=['max_tokens'],
             pricing=dict(prompt='0.000001',completion='0.000002')) for t in ['one','two']])

    def admit(self, cid):
        snap=c.inspect(self.store,cid)
        a,e=inputs(snap,cells=[p['cell_id'] for p in snap['manifest']['plan']])
        a['reserve_amounts']={k:v for k,v in a['reserve_amounts'].items() if k in a['allowed_cells']}
        c.admit(self.store,cid,a,e)

    def ident(self, config=None, **changes):
        panel=config or c.inspect(self.store,'local-comparison')['manifest']['panel'][0]
        value=dict(provider=panel['provider'],model=panel['model'],revision=panel['revision'],
                   access=panel['access'],channel_id=panel['channel_id'],outgoing_format=r.outgoing.FORMAT)
        value.update(changes)
        return value

    def emit(self, cid='local-comparison', cell='x', oid='first', finish='length', output='', unknown=False,
             status=200, incident=None, native=None, refusal=None, route='one', terminal=None):
        c.reserve(self.store,cid,cell,oid)
        def transport(op,request):
            x=response(op,request);x['cost']['currency']='USD'
            if unknown: x['cost'].update(status='UNKNOWN',amount=None,source='Coût financier absent ; réserve conservée')
            if incident is None:
                x['receipt']['result'].update(output=output,incident=None if finish=='stop' else 'PROVIDER_RESPONSE_INCOMPLETE')
            else:
                x['receipt']['result'].update(output=output,incident=incident)
            message=dict(content=output)
            if refusal is not None: message['refusal']=refusal
            choice=dict(finish_reason=finish,message=message)
            if native is not None: choice['native_finish_reason']=native
            raw=json.dumps(dict(choices=[choice],usage=dict(prompt_tokens=50))).encode()
            observed=x['receipt']['observed_configuration']
            observed.update(provider='One',route=route,http=dict(status=status,complete=True,
                  credential_redacted=False,body_base64=b64encode(raw).decode(),body_sha256=sha256(raw).hexdigest(),received_at='2026-09-11T00:00:00Z'))
            if terminal is not None: observed['pi']=dict(terminal=terminal)
            return x
        c.execute(self.data,oid,transport)

    def test_length_link_idempotence_profile_and_unchanged_source(self):
        self.emit()
        before=c.inspect(self.store,'local-comparison')
        proposal=r.propose(self.store,'first',self.caps)
        self.assertEqual(200,proposal['manifest']['panel'][0]['parameters']['max_tokens'])
        self.assertIsNone(r.profile(self.store,self.ident()))
        with self.assertRaises(ValueError):
            r.profile(self.store,dict(model='fixture/x'))
        cid=proposal['manifest']['campaign_id'];c.create(self.store,proposal['manifest'])
        with self.assertRaises(storage.ConflictError):c.create(self.store,proposal['manifest'])
        self.admit(cid);self.emit(cid=cid,oid='second',finish='stop',output='Complete')
        reqs=[json.loads(self.store._connection.execute('SELECT request_json FROM s4_attempts WHERE operation_id=?',(oid,)).fetchone()[0]) for oid in ['first','second']]
        self.assertEqual(reqs[0]['outgoing'],reqs[1]['outgoing'])
        self.assertNotEqual(reqs[0]['requested_configuration']['parameters']['max_tokens'],
                            reqs[1]['requested_configuration']['parameters']['max_tokens'])
        after=c.inspect(self.store,'local-comparison')
        self.assertEqual({k:v for k,v in before.items() if k != 'budget'},
                         {k:v for k,v in after.items() if k != 'budget'})
        with closing(storage.Store(self.data)) as reopened:
            profile=r.profile(reopened,self.ident())
            self.assertEqual('second',profile['operation_id'])
            self.assertEqual(200,profile['parameters']['max_tokens'])
            self.assertEqual('rev-x',profile['revision'])
            self.assertNotEqual(profile['model'],profile['revision'])
            self.assertIsNone(r.profile(reopened,self.ident(revision='other-rev')))
            self.assertIsNone(r.profile(reopened,self.ident(provider='other-provider')))
            self.assertIsNone(r.profile(reopened,self.ident(access='API')))
            self.assertIsNone(r.profile(reopened,self.ident(channel_id='other-channel')))
            dumped=storage._strict_json(profile)
            self.assertNotIn('Complete',dumped)
            self.assertNotIn('body_base64',dumped)
            self.assertNotIn('choices',dumped)
            next_config=r.starting_configuration(reopened,before['manifest']['panel'][0],content_format=r.outgoing.FORMAT)
            self.assertEqual(200,next_config['configuration']['parameters']['max_tokens'])
            self.assertEqual('second',next_config['profile']['operation_id'])
            self.assertIsNone(r.starting_configuration(reopened,before['manifest']['panel'][0])['profile'])
        with self.assertRaises(storage.ConflictError):c.reserve(self.store,cid,'x','third')

    def test_refusal_no_progress_and_limit_stop(self):
        self.emit(finish='content_filter')
        with self.assertRaises(ValueError):r.propose(self.store,'first',self.caps)
        self.emit(cell='y',oid='refusal',finish='content_filter')
        self.assertIsNone(r.profile(self.store,self.ident()))

    def test_no_progress_stops_after_larger_allocation(self):
        self.emit()
        proposal=r.propose(self.store,'first',self.caps);cid=proposal['manifest']['campaign_id']
        c.create(self.store,proposal['manifest']);self.admit(cid);self.emit(cid=cid,oid='second')
        with self.assertRaisesRegex(ValueError,'progression'):r.propose(self.store,'second',self.caps)

    def test_budget_retains_unknown_sibling_and_limits(self):
        self.emit();self.emit(cell='y',oid='unknown',finish='content_filter',unknown=True)
        proposal=r.propose(self.store,'first',self.caps)
        cid=proposal['manifest']['campaign_id'];c.create(self.store,proposal['manifest']);self.admit(cid)
        self.emit(cid=cid,oid='second',finish='stop',output='complete')
        self.assertEqual('7',self.store.inspect_budget('local-comparison')['reserved'])
        caps=deepcopy(self.caps)
        for e in caps['endpoints']:e['max_completion_tokens']=100
        with self.assertRaisesRegex(ValueError,'Limite'):r.propose(self.store,'first',caps)
        for e in caps['endpoints']:e['max_completion_tokens']=1000;e['pricing']['completion']='100'
        with self.assertRaises(storage.BudgetError):r.propose(self.store,'first',caps)

    def test_route_recovery_stays_within_original_endpoints(self):
        self.emit(status=503,finish=None)
        proposal=r.propose(self.store,'first',self.caps)
        self.assertEqual(['two'],proposal['manifest']['panel'][0]['parameters']['provider']['only'])
        bad=deepcopy(proposal['manifest']);bad['panel'][0]['parameters']['provider']['only']=['foreign']
        with self.assertRaises(ValueError):c.create(self.store,bad)

    def test_route_error_then_success_keeps_incident_and_learned_route(self):
        source=c.inspect(self.store,'local-comparison')['manifest']['panel'][0]
        self.emit(status=503,finish=None)
        proposal=r.propose(self.store,'first',self.caps)
        self.assertEqual(['two'],proposal['manifest']['panel'][0]['parameters']['provider']['only'])
        cid=proposal['manifest']['campaign_id'];c.create(self.store,proposal['manifest']);self.admit(cid)
        self.emit(cid=cid,oid='second',finish='stop',output='Complete',route='two')
        reqs=[json.loads(self.store._connection.execute('SELECT request_json FROM s4_attempts WHERE operation_id=?',(oid,)).fetchone()[0]) for oid in ['first','second']]
        self.assertEqual(reqs[0]['outgoing'],reqs[1]['outgoing'])
        learned=r.starting_configuration(self.store,source,content_format=r.outgoing.FORMAT)
        self.assertEqual(['two'],learned['configuration']['parameters']['provider']['only'])
        self.assertEqual(proposal['manifest']['panel'][0]['route'],learned['configuration']['route'])
        kinds=[step['kind'] for step in learned['profile']['recovery_chain']]
        self.assertEqual(['ROUTE_ERROR','COMPLETE'],kinds)

    def test_empty_output_proposes_remaining_endpoint(self):
        self.emit(finish='stop',output='')
        proposal=r.propose(self.store,'first',self.caps)
        self.assertEqual(['two'],proposal['manifest']['panel'][0]['parameters']['provider']['only'])
        self.assertEqual(100,proposal['manifest']['panel'][0]['parameters']['max_tokens'])

    def test_each_terminal_or_unrecoverable_case_refuses_proposal(self):
        for fields in [dict(finish='content_filter'),
                       dict(finish='stop',output='x',native='refusal'),
                       dict(finish='stop',output='x',refusal='refused'),
                       dict(finish='stop',output='ok',incident='HARNESS_ERROR'),
                       dict(finish='stop',output='ok',incident='MODEL_IDENTITY_MISMATCH'),
                       dict(status=503,finish=None,route=None),
                       dict(finish='stop',output='ok',terminal=False)]:
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as tmp:
                data=Path(tmp).resolve()/'private'
                sid,view,ref=fixture(data)
                q.initialize(data);c.initialize(data)
                with closing(storage.Store(data)) as store:
                    spec=specification(ref);spec['cost_basis']['unit']='USD'
                    draft=q.draft(store,'fixture',view['revision'],spec)
                    qualified=q.qualify(store,draft['contract_sha256'],reviewer=ACTOR,check=check)
                    q.approve(store,draft['contract_sha256'],qualified['qualification_id'],actor=ACTOR,authority=AUTHORITY)
                    m=manifest(draft);m['financial_cost_policy']='retain_reserve'
                    m['conditions']['defaults']={'context_window':10000}
                    for p in m['panel']:
                        p.update(model='fixture/'+p['id'],revision='rev-'+p['id'],
                                 parameters={'max_tokens':100,'provider':{'only':['one','two'],'order':['one','two'],
                                 'allow_fallbacks':True,'require_parameters':True}})
                    store.create_budget('local-comparison','40','USD')
                    c.create(store,m)
                    snap=c.inspect(store,'local-comparison')
                    a,e=inputs(snap,cells=[p['cell_id'] for p in snap['manifest']['plan']])
                    a['reserve_amounts']={k:v for k,v in a['reserve_amounts'].items() if k in a['allowed_cells']}
                    c.admit(store,'local-comparison',a,e)
                    previous=self.store; previous_data=self.data
                    self.store=store; self.data=data
                    try:
                        self.emit(**fields)
                        with self.assertRaises(ValueError):
                            r.propose(store,'first',self.caps)
                    finally:
                        self.store=previous; self.data=previous_data

    def test_unknown_cost_profile_keeps_reserve_and_source(self):
        self.emit(finish='stop',output='Complete',unknown=True)
        profile=r.profile(self.store,self.ident())
        self.assertEqual('UNKNOWN',profile['cost']['status'])
        self.assertIsNone(profile['cost']['amount'])
        self.assertIn('réserve',profile['cost']['source'])
        self.assertEqual('7',self.store.inspect_budget('local-comparison')['reserved'])
        dumped=storage._strict_json(profile)
        self.assertNotIn('Complete',dumped)
        self.assertNotIn('body_base64',dumped)


if __name__ == '__main__':
    unittest.main()
