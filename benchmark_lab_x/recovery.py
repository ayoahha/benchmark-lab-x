"""Receipt-driven recovery proposals; each emission still needs private admission"""
from base64 import b64decode
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json

from . import campaigns as c, qualification as q, outgoing
from .storage import BudgetError, ConflictError, IntegrityError, _fields, _money, _transaction

_IDENTITY = ('provider', 'model', 'revision', 'access', 'channel_id')
_UNRECOVERABLE = {'MODEL_IDENTITY_MISMATCH', 'PROVIDER_ROUTE_MISMATCH', 'HARNESS_ERROR'}
_RECOVERABLE = {'LENGTH', 'EMPTY_OUTPUT', 'ROUTE_ERROR'}


def parent(store, connection, operation_id):
    row = connection.execute('SELECT campaign_id FROM s4_attempts WHERE operation_id=?', (operation_id,)).fetchone()
    if row is None:
        raise ValueError('Tentative source absente')
    snapshot = c._inspect(store, connection, row[0])
    attempt = next(a for a in snapshot['attempts'] if a['operation_id'] == operation_id)
    return snapshot, attempt


def observation(attempt):
    if attempt['state'] != 'RECEIVED' or attempt['attribution_incident']:
        raise ConflictError('Reçu attribuable requis ; aucun rejeu ambigu')
    receipt = attempt['operation']['receipt']
    observed = receipt['observed_configuration']
    http = observed.get('http', {})
    raw = b64decode(http.get('body_base64', ''), validate=True)
    if (sha256(raw).hexdigest() != http.get('body_sha256') or not http.get('complete')
            or http.get('credential_redacted') or receipt['result']['emission'] != 'ESTABLISHED'):
        raise IntegrityError('Reçu HTTP complet requis')
    data = json.loads(raw)
    choices = data.get('choices') or []
    choice = choices[0] if len(choices) == 1 else {}
    message = choice.get('message') or {}
    reason = choice.get('finish_reason')
    incident = receipt['result']['incident']
    content = message.get('content') or ''
    if reason == 'content_filter' or choice.get('native_finish_reason') == 'refusal' or message.get('refusal'):
        kind = 'CONTENT_REFUSAL'
    elif incident in _UNRECOVERABLE or observed.get('pi', {}).get('terminal') is False:
        kind = 'UNRECOVERABLE'
    elif http['status'] == 200 and reason == 'length':
        kind = 'LENGTH'
    elif http['status'] in (429, 502, 503, 504):
        kind = 'ROUTE_ERROR'
    elif http['status'] == 200 and reason == 'stop' and not content and incident in (None, 'PROVIDER_RESPONSE_INCOMPLETE'):
        kind = 'EMPTY_OUTPUT'
    elif http['status'] == 200 and reason == 'stop' and content and incident is None:
        kind = 'COMPLETE'
    else:
        kind = 'UNRECOVERABLE'
    usage = data.get('usage') or {}
    return dict(kind=kind, output_chars=len(content), usage=usage,
                provider=observed.get('provider'), route=observed.get('route'),
                receipt_sha256=q.digest(receipt), received_at=http.get('received_at'))


def validate_link(store, connection, manifest):
    oid = manifest['recovery_of']
    row = connection.execute('SELECT c.rowid FROM s4_campaigns c JOIN s4_attempts a USING(campaign_id) WHERE a.operation_id=?', (oid,)).fetchone()
    own = connection.execute('SELECT rowid FROM s4_campaigns WHERE campaign_id=?', (manifest['campaign_id'],)).fetchone()
    if row is None or (own and row[0] >= own[0]):
        raise ValueError('La reprise doit suivre un reçu antérieur')
    previous, attempt = parent(store, connection, oid)
    old = previous['manifest']
    if observation(attempt)['kind'] not in _RECOVERABLE:
        raise ValueError('Incident non récupérable ; refus conservé')
    if any(manifest.get(k) != old.get(k) for k in ('contract_sha256', 'conditions', 'cases', 'cost_basis', 'financial_cost_policy')):
        raise ValueError('La reprise conserve tâche et conditions')
    cell = next(x for x in old['plan'] if x['cell_id'] == attempt['cell_id'])
    config = next(x for x in old['panel'] if x['id'] == cell['configuration_id'])
    if manifest['plan'] != [cell] or len(manifest['panel']) != 1:
        raise ValueError('Une reprise concerne uniquement la cellule interrompue')
    new = manifest['panel'][0]
    if any(new[k] != config[k] for k in config if k not in ('parameters', 'route', 'effort')):
        raise ValueError('Modèle ou identité de tâche modifié')
    if not set(new['parameters']['provider']['only']) <= set(config['parameters']['provider']['only']):
        raise ValueError('Endpoint hors autorisation initiale')


def _identity(configuration, outgoing_format):
    return dict({key: configuration[key] for key in _IDENTITY}, outgoing_format=outgoing_format)


def _cost(attempt):
    return deepcopy(attempt['operation']['observed_cost'])


def _chain(store, connection, snapshot, attempt):
    steps = []
    current_snapshot, current = snapshot, attempt
    while True:
        try:
            observed = observation(current)
        except (ValueError, ConflictError, IntegrityError):
            observed = dict(kind='UNRECOVERABLE', route=None, received_at=None)
        config = current['operation']['requested_configuration']
        steps.append(dict(operation_id=current['operation_id'], kind=observed['kind'],
                          incident=current['operation']['receipt']['result']['incident'],
                          route=observed.get('route'), requested_route=config.get('route'),
                          parameters=deepcopy(config['parameters']), received_at=observed.get('received_at'),
                          cost=_cost(current)))
        parent_id = current_snapshot['manifest'].get('recovery_of')
        if not parent_id:
            break
        current_snapshot, current = parent(store, connection, parent_id)
    steps.reverse()
    return steps


def _record(snapshot, attempt, observed, chain):
    config = attempt['operation']['requested_configuration']
    return dict(outgoing_format=outgoing.FORMAT, provider=config['provider'], model=config['model'],
                revision=config['revision'], access=config['access'], channel_id=config['channel_id'],
                parameters=deepcopy(config['parameters']), effort=config['effort'], route=config['route'],
                observed_provider=observed['provider'], observed_route=observed['route'],
                operation_id=attempt['operation_id'], campaign_id=snapshot['manifest']['campaign_id'],
                receipt_sha256=observed['receipt_sha256'], received_at=observed['received_at'],
                cost=_cost(attempt), recovery_chain=chain)


def profile(store, identity):
    """Successful transport parameters derived from the existing durable receipts"""
    _fields(identity, _IDENTITY + ('outgoing_format',), 'transport identity')
    connection = c.connection_for(store)
    with _transaction(connection):
        for (oid,) in connection.execute('SELECT operation_id FROM s4_attempts ORDER BY rowid DESC').fetchall():
            snapshot, attempt = parent(store, connection, oid)
            config = attempt['operation']['requested_configuration']
            contract = c._approved(store, connection, snapshot['manifest']['contract_sha256'])
            if (contract['package'].get('outgoing_format') != identity['outgoing_format']
                    or any(config[key] != identity[key] for key in _IDENTITY)):
                continue
            try:
                observed = observation(attempt)
            except (ValueError, ConflictError, IntegrityError):
                continue
            if observed['kind'] == 'COMPLETE':
                return _record(snapshot, attempt, observed, _chain(store, connection, snapshot, attempt))
    return None


def propose(store, operation_id, capabilities):
    """No call or write: adapt from a receipt and freshly supplied public metadata"""
    connection = c.connection_for(store)
    with _transaction(connection):
        snapshot, attempt = parent(store, connection, operation_id)
        contract = c._approved(store, connection, snapshot['manifest']['contract_sha256'])
        if contract['package'].get('outgoing_format') != outgoing.FORMAT:
            raise ValueError('Ancien contenu : nouvelle comparaison requise')
        observed = observation(attempt)
        if observed['kind'] not in _RECOVERABLE:
            raise ValueError('Aucune reprise automatique de ce reçu')
        manifest = deepcopy(snapshot['manifest'])
        cell = next(x for x in manifest['plan'] if x['cell_id'] == attempt['cell_id'])
        config = next(x for x in manifest['panel'] if x['id'] == cell['configuration_id'])
        if capabilities['id'] != config['model']:
            raise ValueError('Capacités d’un autre modèle')
        if manifest.get('recovery_of') and observed['kind'] == 'LENGTH':
            _, earlier = parent(store, connection, manifest['recovery_of'])
            if observed['output_chars'] <= observation(earlier)['output_chars']:
                raise ValueError('Arrêt : aucune progression de sortie')
        params = config['parameters']
        allowed = params['provider']['only']
        endpoints = [e for tag in allowed for e in capabilities['endpoints']
                     if e['tag'] == tag and e['status'] == 0]
        if observed['kind'] in ('ROUTE_ERROR', 'EMPTY_OUTPUT'):
            if not observed['route']:
                raise ValueError('Endpoint fautif non attribué')
            endpoints = [e for e in endpoints if e['tag'] != observed['route']]
        if not endpoints:
            raise ValueError('Endpoints autorisés épuisés')
        input_tokens = observed['usage'].get('prompt_tokens')
        if type(input_tokens) is not int or input_tokens < 0:
            raise ValueError('Quantité d’entrée non établie')
        limit = min(manifest['conditions']['defaults']['context_window'] - input_tokens,
                    *(min(e['max_completion_tokens'], e['context_length'] - input_tokens) for e in endpoints))
        if observed['kind'] == 'LENGTH':
            params['max_tokens'] = min(params['max_tokens'] * 2, limit)
            if params['max_tokens'] <= attempt['operation']['requested_configuration']['parameters']['max_tokens']:
                raise ValueError('Limite modèle atteinte')
        if params['max_tokens'] > limit:
            raise ValueError('Limite endpoint atteinte')
        for e in endpoints:
            if not set(params).difference({'provider', 'stream'}) <= set(e['supported_parameters']):
                raise ValueError('Paramètres non pris en charge')
        tags = [e['tag'] for e in endpoints]
        params['provider'].update(only=tags, order=tags)
        config['route'] = 'OpenRouter ordered endpoints: ' + ','.join(tags)
        # Reserve the full declared context as input, without a speculative discount
        reserves = []
        for e in endpoints:
            pricing = e['pricing']
            if pricing.keys() - {'prompt','completion','input_cache_read','input_cache_write','discount'}:
                raise ValueError('Tarification additionnelle à vérifier')
            reserves.append(_money(pricing['prompt']) * manifest['conditions']['defaults']['context_window']
                            + _money(pricing['completion']) * params['max_tokens'])
        reserve = max(reserves)
        budget = c._envelope(store, connection, snapshot, snapshot['admissions'][-1]['authority'])
        if reserve > Decimal(budget['available']):
            raise BudgetError('Budget de reprise insuffisant')
        manifest.update(campaign_id='recovery-' + q.digest([operation_id, params])[:40], recovery_of=operation_id,
                        panel=[config], plan=[cell], attempt_policy=dict(retries=False, order=[cell['cell_id']],
                        reason='Reprise technique liée au reçu ' + operation_id + ' ; aucune sélection sémantique'))
        return dict(manifest=manifest, reserve_amount=str(reserve), budget_id=budget['budget_id'],
                    source_receipt=observed, capabilities_sha256=q.digest(capabilities))


def starting_configuration(store, configuration, *, content_format=None):
    """Prepare a future configuration from a complete receipt, never edit a contract"""
    proposed = deepcopy(configuration)
    if content_format != outgoing.FORMAT:
        return dict(configuration=proposed, profile=None)
    learned = profile(store, _identity(proposed, content_format))
    if learned is None:
        return dict(configuration=proposed, profile=None)
    proposed['parameters'] = deepcopy(learned['parameters'])
    proposed['route'] = learned['route']
    proposed['effort'] = learned['effort']
    return dict(configuration=proposed, profile=learned)
