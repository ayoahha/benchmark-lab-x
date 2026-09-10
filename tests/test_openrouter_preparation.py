"""HTTP simulations only; usage fixtures are not evidence of provider access."""
from base64 import b64decode
from contextlib import closing, redirect_stdout
from copy import deepcopy
import io
import json
import multiprocessing
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from benchmark_lab_x import preparation as prep, runtime, service, storage
from benchmark_lab_x import openrouter_preparation as assistant


KEY = 'fixture-key-never-a-credential'
ESTIMATE = {'channel': 'OpenRouter', 'model_id': assistant.MODEL, 'context_length': 1000000, 'canonical_slug': assistant.MODEL + '-20260826',
            'assumptions': {'input_tokens': 1000000, 'cached_input_tokens': 0, 'output_tokens': 8192},
            'sources': {key: {'url': 'https://openrouter.ai/api/v1/' + path,
                              'retrieved_at': '2026-09-10T00:00:00+00:00', 'body_sha256': 'b' * 64}
                        for key, path in [('model', 'model/' + assistant.MODEL),
                                          ('endpoints', 'models/' + assistant.MODEL + '/endpoints')]},
            'endpoints': [{'model_id': assistant.MODEL, 'tag': tag, 'provider_name': provider,
                           'supported_parameters': ['temperature', 'top_p', 'reasoning', 'max_tokens', 'response_format'],
                           'pricing_raw': {'prompt': '0.0000002', 'completion': '0.0000008'}}
                          for tag, provider in assistant.PROVIDERS.items()]}
RESERVE = assistant.reservation(ESTIMATE)
ROUTE = {'requested': assistant.MODEL, 'strategy': 'direct', 'attempt': 1,
         'endpoints': {'available': [{'provider': 'Modal', 'model': assistant.MODEL, 'selected': True}]}}

NEED = 'Je passe trop de temps à retrouver ce qui a été décidé en réunion et qui doit faire quoi. Je voudrais comparer des modèles pour m’aider.'
CLARIFICATION = 'Association entièrement fictive organisant un événement ; notes françaises ; décisions, actions, responsables, échéances et informations à confirmer.'
CORRECTION = 'Garde les mêmes notes et distingue clairement les propositions des décisions validées. Pour les responsables absents, indique à confirmer.'
NOTES = ('Association fictive Les Lanternes, réunion du 3 octobre 2027.\n'
         'P1 : Mila propose un concert ; aucune décision prise.\n'
         'D1 : Le comité valide un atelier le 20 novembre.\n'
         'A1 : Noé prépare les affiches. Échéance initiale : 10 octobre.\n'
         'D2 : Échéance des affiches reportée au 14 octobre.\n'
         'A2 : Réserver les tables avant le 18 octobre ; responsable non désigné.\n')
REFERENCE = ('P1 : concert proposé, non validé. D1 : atelier validé. '
             'A1 et D2 : Noé, affiches, échéance 14 octobre, remplace le 10. '
             'A2 : tables, 18 octobre, responsable à confirmer. '
             'Toute reformulation fidèle est recevable. Ne pas deviner le responsable.')


def result(stage='preview'):
    return {'stage': stage,
            'explanation': {'clarification': 'Quelles notes et quel relevé souhaitez-vous comparer ?',
                            'preview': 'Exemple fictif à relire.',
                            'scope_confirmation': 'Je ne peux pas envoyer de rappels. Souhaitez-vous préparer leur texte ?',
                            'suspended': 'Préparation suspendue.'}[stage],
            'reformulation': 'Extraire les décisions et actions des notes françaises.',
            'fictional_parameters': {'association': 'Les Lanternes, inventée'},
            'package': {'instruction': 'Relever décisions, propositions, actions, responsables et échéances ; signaler les inconnues.',
                        'deliverables': ['Relevé structuré'], 'criteria': ['Respect des notes'],
                        'acceptable_ambiguities': ['Reformulations fidèles'], 'human_work': 'Relire et confirmer les inconnues',
                        'limits': ['Exercice fictif unique, sans action externe'],
                        'pieces': [{'name': 'notes.txt', 'role': 'candidate', 'content': NOTES},
                                   {'name': 'reference.txt', 'role': 'judge', 'content': REFERENCE}]}
                       if stage == 'preview' else None}


def http_body(value=None, **updates):
    return storage._strict_json({'id': 'fixture-provider-id', 'model': assistant.MODEL,
        'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant',
                    'content': storage._strict_json(value if value is not None else result())}}],
        'openrouter_metadata': ROUTE, 'usage': {'cost': 0.000202, 'prompt_tokens': 1000, 'completion_tokens': 200, 'total_tokens': 1200,
                  'prompt_tokens_details': {'cached_tokens': 400}}, **updates}).encode()


def executor_process(data, sock, entered=None):
    connection = Mock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.length = 0
    connection.getresponse.return_value.read.return_value = http_body(result('clarification'), usage=None)
    if entered is not None:
        def interrupted_response():
            entered.set()
            while True:
                time.sleep(1)
        connection.getresponse.side_effect = interrupted_response
    with patch.dict(os.environ, {'OPENROUTER_API_KEY': KEY}), patch.object(assistant, 'HTTPSConnection', return_value=connection), \
            patch.object(service, 'release_identity', return_value='a' * 40):
        runtime.main(['executor', '--data', str(data), '--socket', str(sock),
                      '--preparation-assistant', assistant.ASSISTANT])


class OpenRouterPreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='openrouter-fixture-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.data = self.home / 'private'
        storage.initialize(self.data)
        storage.initialize_preparation(self.data)
        self.store = storage.Store(self.data)
        self.addCleanup(self.store.close)
        self.store.create_budget('fixture', '100', 'USD')
        self.authority = dict(authority_id='FICTIONAL_HTTP_ONLY', budget_id='fixture',
                              reserve_amount=RESERVE, requested_configuration=assistant.configuration(ESTIMATE))
        prep.admit(self.store, self.authority)
        self.session, self.csrf, self.token = prep.session(self.store, None, create=True)
        self.transport = assistant.OpenRouterPreparation(KEY)
        self.http = Mock()
        self.http.getresponse.return_value.status = 200
        self.http.getresponse.return_value.length = 0
        self.raw = http_body()
        self.http.getresponse.return_value.read.return_value = self.raw
        patched = patch.object(assistant, 'HTTPSConnection', return_value=self.http)
        self.connection = patched.start()
        self.addCleanup(patched.stop)

    def submit(self, **fields):
        body = fields or dict(action_id='create', request=NEED)
        return prep.submit(self.store, self.session, 'd', body, 'a' * 40, self.transport)[0]

    def execute(self, **fields):
        operation = self.submit(**fields)
        prep.execute(self.data, operation, self.transport)
        return next(op for op in self.store.inspect_operations() if op['operation_id'] == operation), prep.view(self.store, self.session, 'd')

    def test_exact_wire_is_durable_before_http_and_unknown_cost_blocks_next_call(self):
        def at_request(method, path, *, body, headers):
            with closing(storage.Store(self.data)) as reader:
                operation = reader.inspect_operations()[0]
                self.assertEqual('EMISSION_POSSIBLE', operation['state'])
                self.assertEqual(body, operation['resources'][1].encode())
                self.assertEqual(RESERVE, reader.inspect_budget('fixture')['reserved'])
            self.assertEqual(('POST', assistant.PATH), (method, path))
            self.assertEqual('Bearer ' + KEY, headers['Authorization'])
            self.assertNotIn(KEY.encode(), body)
            sent = json.loads(body)
            self.assertEqual(assistant.MODEL, sent['model'])
            self.assertEqual(assistant.PARAMETERS, {k: sent[k] for k in assistant.PARAMETERS})
            self.assertNotIn('tools', sent)
            self.assertNotIn('thinking', sent)
            self.assertNotIn('request_id', sent)
            self.assertEqual({'effort': 'max'}, sent['reasoning'])
            self.assertTrue(sent['provider']['allow_fallbacks'])
            self.assertEqual(list(assistant.PROVIDERS), sent['provider']['only'])
            self.assertEqual(sent['provider']['only'], sent['provider']['order'])
            self.assertTrue(sent['provider']['require_parameters'])
            self.assertEqual('enabled', headers['X-OpenRouter-Metadata'])
        self.http.request.side_effect = at_request
        operation_id = self.submit()
        accepted = self.store.inspect_operations()[0]
        self.assertEqual('INTENT_RECORDED', accepted['state'])
        self.assertEqual(2, len(accepted['resources']))
        self.http.request.assert_not_called()
        prep.execute(self.data, operation_id, self.transport)
        operation = self.store.inspect_operations()[0]
        view = prep.view(self.store, self.session, 'd')
        observed = operation['receipt']['observed_configuration']
        self.assertEqual(self.raw, b64decode(observed['http']['body_base64']))
        self.assertEqual(assistant.MODEL, observed['model'])
        self.assertIsNone(observed['parameters'])
        self.assertEqual(ROUTE, observed['route'])
        self.assertEqual('Modal', observed['provider'])
        self.assertEqual('OpenRouter', operation['requested_configuration']['provider'])
        self.assertEqual('0.000202', observed['consumption']['amount'])
        self.assertFalse(observed['consumption']['invoice'])
        self.assertEqual('KNOWN', operation['observed_cost']['status'])
        self.assertEqual('preview', view['stage'])
        self.assertEqual([NOTES.encode()], [prep.piece_bytes(self.store, self.session, 'd', view['revision'], p['id'])
                                          for p in view['package']['pieces']])
        self.assertNotIn(REFERENCE, prep.render(view, self.csrf).decode())
        self.assertEqual('0', self.store.inspect_budget('fixture')['reserved'])
        self.http.request.side_effect = None
        self.http.getresponse.return_value.read.return_value = http_body(usage=None)
        unknown, later = self.execute(action_id='unknown', revision=2, kind='correct', message=CORRECTION)
        budget = self.store.inspect_budget('fixture')
        self.assertEqual(RESERVE, budget['reserved'])
        self.assertEqual('0.000202', budget['spent'])
        self.assertEqual([unknown['operation_id']], budget['unknown_cost_operations'])
        with self.assertRaises(storage.BudgetError):
            self.submit(action_id='next', revision=later['revision'], kind='clarify', message=CLARIFICATION)
        prep.execute(self.data, unknown['operation_id'], self.transport)
        self.assertEqual(2, self.http.request.call_count)
        self.assertEqual(2, self.connection.call_count)
        self.connection.assert_called_with(assistant.HOST, timeout=assistant.TIMEOUT_SECONDS)
        self.assertNotIn(KEY, storage._strict_json(operation))

    def test_full_scenario_same_budget_preserves_notes_agreements_and_validation(self):
        self.http.getresponse.return_value.read.return_value = http_body(result('clarification'))
        _, clarified = self.execute()
        self.assertEqual('clarification', clarified['stage'])
        self.assertIn('Quelles notes', clarified['explanation'])
        self.http.getresponse.return_value.read.return_value = http_body()
        _, before = self.execute(action_id='clarify', revision=2, kind='clarify', message=CLARIFICATION)
        prep.validate(self.store, self.session, 'd', prep.binding('d', 3, before['package_sha256']))
        changed = result()
        changed['package']['criteria'].append('Propositions séparées des décisions ; responsable absent à confirmer')
        self.http.getresponse.return_value.read.return_value = http_body(changed)
        operation, after = self.execute(action_id='correct', revision=3, kind='correct', message=CORRECTION)
        request = json.loads(operation['resources'][0])
        self.assertEqual(NOTES, request['pieces_seen'][0]['content'])
        self.assertNotIn(REFERENCE, operation['resources'][1])
        self.assertEqual(before['payload']['validated_assumptions'], after['payload']['validated_assumptions'])
        self.assertEqual(NEED, after['payload']['request'])
        self.assertEqual(NOTES.encode(), self.store.read_piece(after['package']['pieces'][0]['id']))
        self.assertIsNone(after['validation'])
        self.assertIsNotNone(prep.view(self.store, self.session, 'd', 3)['validation'])
        self.assertFalse(after['qualified'])
        prep.validate(self.store, self.session, 'd', prep.binding('d', 4, after['package_sha256']))
        self.http.getresponse.return_value.read.return_value = http_body(result('scope_confirmation'))
        operation, view = self.execute(action_id='limit', revision=4, kind='clarify', message='Envoie aussi les rappels aux participants.')
        self.assertEqual('scope_confirmation', view['stage'])
        self.assertIn('ne peux pas envoyer', view['explanation'])
        self.assertIsNone(view['package'])
        self.assertEqual(4, self.http.request.call_count)
        self.assertEqual('RECEIVED', operation['state'])
        self.assertEqual('0.000808', self.store.inspect_budget('fixture')['spent'])
        self.assertEqual('0', self.store.inspect_budget('fixture')['reserved'])
        self.assertTrue(self.store.verify_storage()['integrity_ok'])

    def test_bad_output_keeps_raw_receipt_without_orphan_piece(self):
        broken = result()
        broken['package']['pieces'][1]['role'] = 'operator'
        self.http.getresponse.return_value.read.return_value = http_body(broken)
        operation, view = self.execute()
        self.assertEqual('RECEIVED', operation['state'])
        self.assertEqual('suspended', view['stage'])
        self.assertIsNone(prep.admission(self.store))
        self.assertEqual(http_body(broken), b64decode(operation['receipt']['observed_configuration']['http']['body_base64']))
        self.assertEqual([], self.store.verify_storage()['orphan_files'])

    def test_truncation_wrong_model_tools_non_json_and_http_errors_are_not_retried(self):
        operation_id = self.submit()
        operation = self.store.inspect_operations()[0]
        request = json.loads(operation['resources'][0])
        wire = self.transport.prepare(operation, request, self.store.inspect_budget('fixture'))
        self.assertEqual(wire, operation['resources'][1])
        operation['state'] = 'EMISSION_POSSIBLE'
        choices = [{'finish_reason': 'length', 'message': {'role': 'assistant', 'content': '{}'}}]
        tools = [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '{}', 'tool_calls': [{'type': 'function'}]}}]
        for status, raw in [(200, b'not json'), (200, b'{"usage":NaN}'), (200, b'{"model":"x","model":"y"}'), (200, http_body(model='glm-5.3')),
                            (200, http_body(choices=choices)), (200, http_body(choices=tools)),
                            (429, b'{"error":"rate limit"}'), (302, b'redirect'),
                            (200, b' ' * (assistant.MAX_RESPONSE_BYTES + 1))]:
            with self.subTest(status=status, raw_size=len(raw)):
                self.http.reset_mock()
                self.http.getresponse.return_value.status = status
                self.http.getresponse.return_value.read.return_value = raw
                response = self.transport(operation, request)
                self.assertIsNone(response['receipt']['result'])
                self.assertEqual('KNOWN' if raw in (http_body(choices=choices), http_body(choices=tools), http_body(model='glm-5.3')) else 'UNKNOWN', response['cost']['status'])
                self.assertEqual(1, self.http.request.call_count)

        self.http.getresponse.return_value.status = 200
        self.http.getresponse.return_value.length = 17
        self.http.getresponse.return_value.read.return_value = http_body()
        response = self.transport(operation, request)
        self.assertEqual('UNKNOWN', response['cost']['status'])
        self.assertIsNone(response['receipt']['result'])
        self.assertFalse(response['receipt']['observed_configuration']['http']['complete'])

    def test_reported_cost_is_exact_and_missing_cost_has_no_tariff_fallback(self):
        for usage in [None, {}, {'cost': None}, {'cost': -1}, {'cost': True}, {'cost': 'NaN'},
                      {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}]:
            measured = assistant.consumption({'usage': usage})
            self.assertIsNone(measured['amount'])
            self.assertEqual('UNKNOWN', measured['status'])
        self.assertEqual('0', assistant.consumption({'usage': {'cost': 0}})['amount'])
        self.assertEqual('0.123456789012345678901', assistant.consumption({'usage': {'cost': '0.123456789012345678901'}})['amount'])
        # A reported debit is independent from optional token breakdowns and upstream cost
        measured = assistant.consumption({'usage': {'cost': '0.02', 'cost_details': {'upstream_inference_cost': 99}}})
        self.assertEqual('0.02', measured['amount'])
        self.assertEqual('USD', measured['currency'])
        self.http.getresponse.return_value.read.return_value = http_body(openrouter_metadata=None)
        operation, _ = self.execute()
        observed = operation['receipt']['observed_configuration']
        self.assertIsNone(observed['route'])
        self.assertIsNone(observed['provider'])
        self.assertEqual('KNOWN', operation['observed_cost']['status'])

    def test_timeout_keeps_intention_reserve_and_no_replay_after_restart(self):
        self.http.getresponse.side_effect = TimeoutError('private provider error ' + KEY)
        operation, view = self.execute()
        self.assertEqual('AMBIGUOUS', operation['state'])
        self.assertEqual(2, len(operation['resources']))
        self.assertEqual('suspended', view['stage'])
        runtime.stop(self.data, self.store, 'FIXTURE_RESTART', after_process_exit=True)
        prep.execute(self.data, operation['operation_id'], self.transport)
        self.assertEqual(1, self.http.request.call_count)
        self.assertEqual(RESERVE, self.store.inspect_budget('fixture')['reserved'])
        self.assertNotIn(KEY, storage._strict_json(self.store.inspect_operations()))

    def test_configuration_budget_and_size_refuse_before_emission(self):
        for change in ['model', 'reserve', 'currency', 'limit', 'size']:
            with self.subTest(change=change):
                operation = {'operation_id': 'fixture', 'requested_configuration': assistant.configuration(ESTIMATE), 'phase': 'preparation', 'reserved_amount': RESERVE}
                request = {'message': 'x'}
                budget = {'currency': 'USD', 'limit': '100'}
                if change == 'model': operation['requested_configuration']['model'] = 'glm-5.3'
                if change == 'reserve': operation['reserved_amount'] = '0'
                if change == 'currency': budget['currency'] = 'TEST'
                if change == 'limit': budget['limit'] = '101'
                if change == 'size': request['message'] *= assistant.MAX_REQUEST_BYTES
                with self.assertRaises(ValueError):
                    self.transport.prepare(operation, request, budget)
        self.authority['requested_configuration']['model'] = 'glm-5.3'
        prep.admit(self.store, self.authority)
        with self.assertRaises(ValueError):
            self.execute()
        self.assertEqual([], self.store.inspect_operations())
        self.assertEqual('0', self.store.inspect_budget('fixture')['reserved'])
        self.assertEqual(self.authority, prep.admission(self.store))
        self.http.request.assert_not_called()

    def test_reservation_uses_public_text_prices_and_rejects_missing_required_price(self):
        self.assertEqual('0.2065536', RESERVE)
        estimate = deepcopy(ESTIMATE)
        estimate['endpoints'][0]['pricing_raw'].update({'discount': 0.5, 'request': None, 'image': None})
        self.assertEqual(RESERVE, assistant.reservation(estimate))
        estimate['endpoints'][0]['pricing_raw']['overrides'] = [{'image': '1'}]
        self.assertEqual(RESERVE, assistant.reservation(estimate))
        estimate['endpoints'][0]['pricing_raw']['overrides'] = [{'prompt': '1', 'min_prompt_tokens': 10}]
        with self.assertRaises(ValueError): assistant.reservation(estimate)
        estimate = deepcopy(ESTIMATE)
        del estimate['endpoints'][0]['pricing_raw']['completion']
        self.authority['requested_configuration']['reservation_estimate'] = estimate
        prep.admit(self.store, self.authority)
        with self.assertRaisesRegex(ValueError, 'prompt ou completion'):
            self.submit()
        self.assertEqual([], self.store.inspect_operations())
        self.assertEqual('0', self.store.inspect_budget('fixture')['reserved'])
        self.http.request.assert_not_called()

    def test_native_fallback_after_429_is_accepted_without_another_http_call(self):
        self.http.getresponse.return_value.read.return_value = http_body(openrouter_metadata={**ROUTE, 'strategy': 'fallback', 'attempt': 2,
            'attempts': [{'provider': 'CoreWeave', 'model': assistant.MODEL, 'status': 429},
                         {'provider': 'Modal', 'model': assistant.MODEL, 'status': 200}]})
        operation, view = self.execute()
        self.assertEqual('preview', view['stage'])
        self.assertEqual(2, operation['receipt']['observed_configuration']['route']['attempt'])
        self.assertEqual('KNOWN', operation['observed_cost']['status'])
        self.assertIsNotNone(prep.admission(self.store))
        self.assertEqual(1, self.http.request.call_count)

    def test_canonical_model_is_attributed_but_another_revision_or_endpoint_is_rejected(self):
        canonical = ESTIMATE['canonical_slug']
        route = deepcopy(ROUTE)
        route['attempt'] = 4
        route['endpoints']['available'][0]['model'] = canonical
        self.http.getresponse.return_value.read.return_value = http_body(model=canonical, openrouter_metadata=route)
        operation, view = self.execute()
        self.assertEqual('preview', view['stage'])
        self.assertEqual(canonical, operation['receipt']['observed_configuration']['model'])
        self.assertIsNotNone(operation['receipt']['observed_configuration']['routing_limit'])
        for index, updates in enumerate([{'model': assistant.MODEL + '-20260827'},
                {'openrouter_metadata': {**ROUTE, 'attempts': [{'provider': 'Modal', 'model': assistant.MODEL + '-20260827'}]}},
                {'openrouter_metadata': {**ROUTE, 'attempts': [{'provider': 'Modal', 'tag': 'outside/fp8', 'model': assistant.MODEL}]}}]):
            prep.admit(self.store, self.authority)
            self.http.getresponse.return_value.read.return_value = http_body(**updates)
            operation, view = self.execute(action_id='different-' + str(index), revision=view['revision'], kind='correct', message=CORRECTION)
            self.assertEqual('suspended', view['stage'])
            self.assertEqual('KNOWN', operation['observed_cost']['status'])
        self.assertEqual(4, self.http.request.call_count)

    def test_unmapped_provider_name_is_unknown_not_an_invented_alias(self):
        route = deepcopy(ROUTE)
        route['endpoints']['available'][0]['provider'] = 'NovitaAI'
        self.http.getresponse.return_value.read.return_value = http_body(openrouter_metadata=route)
        operation, view = self.execute()
        self.assertEqual('preview', view['stage'])
        observed = operation['receipt']['observed_configuration']
        self.assertIsNone(observed['provider'])
        self.assertEqual('NovitaAI', observed['route']['endpoints']['available'][0]['provider'])

    def test_429_retains_only_safe_identifiers_and_no_cost_or_retry_is_invented(self):
        response = self.http.getresponse.return_value
        response.status = 429
        response.read.return_value = b'{"error":{"code":429,"message":"fixture upstream pool busy"}}'
        response.getheader.side_effect = {'X-Generation-Id': 'gen-fixture-error', 'Retry-After': '30'}.get
        operation, view = self.execute()
        observed = operation['receipt']['observed_configuration']
        self.assertEqual('gen-fixture-error', observed['generation_id'])
        self.assertEqual({'X-Generation-Id': 'gen-fixture-error', 'Retry-After': '30'}, observed['http']['response_headers'])
        self.assertEqual('UNKNOWN', operation['observed_cost']['status'])
        self.assertEqual('suspended', view['stage'])
        self.assertEqual(RESERVE, self.store.inspect_budget('fixture')['reserved'])
        self.assertEqual(1, self.http.request.call_count)
        self.assertEqual({'X-Generation-Id', 'Retry-After'}, {c.args[0] for c in response.getheader.call_args_list})

    def test_key_absent_default_transport_and_reflected_key(self):
        with patch.dict(os.environ, {'ZAI_API_KEY': KEY}, clear=True), patch.object(service, 'serve_executor') as executor, \
                patch.object(service, 'release_identity', return_value='a' * 40), redirect_stdout(io.StringIO()):
            arguments = ['executor', '--data', str(self.data), '--socket', str(self.home / 'executor.sock')]
            self.assertEqual(78, runtime.main(arguments + ['--preparation-assistant', assistant.ASSISTANT]))
            executor.assert_not_called()
            self.http.request.assert_not_called()
            self.assertEqual(0, runtime.main(arguments))
            self.assertIsNone(executor.call_args.kwargs['transport'])
        reflected = result()
        reflected['explanation'] = KEY
        self.http.getresponse.return_value.read.return_value = http_body(reflected)
        operation, view = self.execute()
        self.assertNotIn(KEY, storage._strict_json(operation))
        self.assertTrue(operation['receipt']['observed_configuration']['http']['credential_redacted'])
        self.assertEqual('suspended', view['stage'])

    def test_runtime_web_executor_mapping_and_web_cannot_select_transport(self):
        public = self.home / 'public'
        public.mkdir()
        sock = self.home / 'executor.sock'
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        context = multiprocessing.get_context('spawn')
        children = []
        def stop_children():
            for process in reversed(children):
                if process.is_alive(): process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join()
        self.addCleanup(stop_children)
        for target, args in [(executor_process, (self.data, sock)),
                             (service.serve_web, ('127.0.0.1', port, public, sock, 'a' * 40))]:
            process = context.Process(target=target, args=args)
            process.start()
            children.append(process)
        base = f'http://127.0.0.1:{port}'
        def call(path, body=None):
            headers = {'Accept': 'application/json', 'Cookie': 'benchmark_session=' + self.token}
            if body is not None: headers['Content-Type'] = 'application/json'
            try:
                response = urlopen(Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers), timeout=2)
            except HTTPError as error:
                response = error
            with response:
                return response.status, json.loads(response.read())
        deadline = time.monotonic() + 10
        while True:
            try:
                if call('/readyz')[0] == 200: break
            except OSError: pass
            if time.monotonic() > deadline: self.fail('local processes not ready')
            time.sleep(.02)
        self.assertIsNone(prep.admission(self.store))
        prep.admit(self.store, self.authority)
        body = dict(csrf_token=self.csrf, dossier_id='d', action_id='http', request=NEED)
        self.assertEqual(400, call('/preparation/dossiers', {
            **body, 'dossier_id': 'too-large', 'action_id': 'large', 'request': 'x' * 65536})[0])
        self.assertEqual([], self.store.inspect_operations())
        self.assertEqual('0', self.store.inspect_budget('fixture')['reserved'])
        self.assertEqual(self.authority, prep.admission(self.store))
        self.assertEqual([], self.store._connection.execute('SELECT * FROM s2_actions').fetchall())
        self.assertEqual([], self.store._connection.execute('SELECT * FROM s2_dossiers').fetchall())
        self.assertEqual(400, call('/preparation/dossiers', {**body, 'model': 'other'})[0])
        code, accepted = call('/preparation/dossiers', body)
        self.assertEqual(202, code)
        deadline = time.monotonic() + 5
        while True:
            code, view = call('/preparation/dossiers/d')
            if view['stage'] == 'clarification': break
            if time.monotonic() > deadline: self.fail('simulated response not published')
            time.sleep(.02)
        self.assertIn('Quelles notes', view['explanation'])
        self.assertEqual('UNKNOWN', view['observed_cost']['status'])
        self.assertEqual(202, call('/preparation/dossiers', body)[0])
        self.assertEqual(1, len(self.store.inspect_operations()))
        code, _ = call('/preparation/dossiers/d/messages', dict(csrf_token=self.csrf, action_id='next', revision=2,
                                                              kind='clarify', message=CLARIFICATION))
        self.assertEqual(409, code)

    def test_killed_executor_restarts_closed_with_durable_ambiguous_request(self):
        context = multiprocessing.get_context('spawn')
        entered = context.Event()
        sock = self.home / 'executor.sock'
        children = []
        def cleanup():
            for process in children:
                if process.is_alive(): process.kill()
                process.join(5)
        self.addCleanup(cleanup)
        def start(gate=None):
            process = context.Process(target=executor_process, args=(self.data, sock, gate))
            process.start()
            children.append(process)
            deadline = time.monotonic() + 5
            while True:
                try:
                    service.executor_health(sock)
                    return process
                except OSError:
                    if time.monotonic() > deadline: self.fail('executor not ready')
                    time.sleep(.02)
        first = start(entered)
        prep.admit(self.store, self.authority)
        accepted = service.preparation_request(sock, 'POST', '/preparation/dossiers', self.token,
            dict(csrf_token=self.csrf, dossier_id='d', action_id='interrupted', request=NEED))
        self.assertEqual(202, accepted['status'])
        self.assertTrue(entered.wait(5))
        pending = self.store.inspect_operations()[0]
        self.assertEqual('EMISSION_POSSIBLE', pending['state'])
        first.kill()
        first.join(5)
        start()
        after = self.store.inspect_operations()[0]
        self.assertEqual('AMBIGUOUS', after['state'])
        self.assertEqual(pending['resources'], after['resources'])
        self.assertEqual(2, len(after['resources']))
        self.assertIsNone(after['receipt'])
        self.assertIsNone(prep.admission(self.store))
        self.assertEqual(RESERVE, self.store.inspect_budget('fixture')['reserved'])
        self.assertEqual('suspended', prep.view(self.store, self.session, 'd')['stage'])


if __name__ == '__main__':
    unittest.main()
