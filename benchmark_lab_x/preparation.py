"""Private fictional preparation on S1. No product transport is installed here."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import hmac
from html import escape
import json
import os
from pathlib import Path
import re
import secrets

from .storage import (Store, SchemaError, IntegrityError, ConflictError, BudgetError,
                      _transaction, _strict_json as encode, _fields, _text,
                      _identity, _money, _sum_money, _unique_object, _payload_json)


class Denied(ValueError):
    pass


def identifier(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) is None:
        raise ValueError('Identifiant invalide')
    return value


def connection_for(store):
    connection = store._s1_connection()
    if not connection.execute("SELECT 1 FROM sqlite_schema WHERE name='s2_control'").fetchone():
        raise SchemaError('Initialisation explicite S2 requise')
    return connection


def admission(store, connection=None):
    connection = connection if connection is not None else connection_for(store)
    raw = connection.execute('SELECT admission_json FROM s2_control WHERE singleton=1').fetchone()[0]
    if raw is None:
        return None
    result = json.loads(raw, object_pairs_hook=_unique_object)
    check_authority(result)
    return result


def check_authority(value):
    _fields(value, ('authority_id', 'budget_id', 'reserve_amount', 'requested_configuration'), 'admission')
    _text(value['authority_id'], 'authority_id')
    _text(value['budget_id'], 'budget_id')
    _money(value['reserve_amount'])
    if type(value['requested_configuration']) is not dict or not value['requested_configuration']:
        raise ValueError('Configuration requise')
    encode(value)


def close_admission(store):
    connection = store._s1_connection()
    if connection.execute("SELECT 1 FROM sqlite_schema WHERE name='s2_control'").fetchone():
        with _transaction(connection, write=True):
            connection.execute('UPDATE s2_control SET admission_json=NULL WHERE singleton=1 AND admission_json IS NOT NULL')


def admit(store, authority):
    check_authority(authority)
    connection = connection_for(store)
    with _transaction(connection, write=True):
        if os.path.lexists(store._root / 'restore.json'):
            raise Denied('Restauration à rapprocher')
        store._budget(connection, authority['budget_id'], store._operations(connection))
        connection.execute('UPDATE s2_control SET admission_json=? WHERE singleton=1', (encode(authority),))


def session(store, token, *, create=False):
    connection = connection_for(store)
    raw = None
    if type(token) is str and re.fullmatch('[0-9a-f]{64}', token):
        raw = bytes.fromhex(token)
        row = connection.execute('SELECT session_id FROM s2_sessions WHERE token_sha256=?',
                                 (sha256(raw).hexdigest(),)).fetchone()
        if row:
            return row[0], sha256(b'csrf:' + raw).hexdigest(), token
    if not create:
        raise Denied('Session requise')
    raw = secrets.token_bytes(32)
    session_id = secrets.token_hex(16)
    with _transaction(connection, write=True):
        connection.execute('INSERT INTO s2_sessions VALUES (?, ?)', (session_id, sha256(raw).hexdigest()))
    return session_id, sha256(b'csrf:' + raw).hexdigest(), raw.hex()


def owner(connection, session_id, dossier_id):
    identifier(dossier_id)
    row = connection.execute('SELECT current_revision FROM s2_dossiers WHERE dossier_id=? AND session_id=?',
                             (dossier_id, session_id)).fetchone()
    if not row:
        raise Denied('Dossier inaccessible')
    return row[0]


def binding(dossier_id, revision, digest):
    return {'dossier_id': dossier_id, 'revision': revision, 'package_sha256': digest}


def package_check(store, dossier_id, revision, package, digest):
    if sha256(encode(package).encode()).hexdigest() != digest:
        raise IntegrityError('Empreinte du paquet divergente')
    _fields(package, ('instruction', 'deliverables', 'criteria', 'acceptable_ambiguities',
                      'human_work', 'limits', 'pieces'), 'package')
    for field in ('instruction', 'human_work'):
        _text(package[field], field)
    for field in ('deliverables', 'criteria', 'acceptable_ambiguities', 'limits'):
        if type(package[field]) is not list:
            raise IntegrityError('Liste de présentation requise')
        for text in package[field]:
            _text(text, field)
    if not package['deliverables'] or not package['criteria'] or not package['pieces']:
        raise IntegrityError('Paquet incomplet')
    ids = set()
    for piece in package['pieces']:
        _fields(piece, ('id', 'name', 'sha256', 'size_bytes'), 'piece')
        identifier(piece['id'])
        if piece['id'] in ids:
            raise IntegrityError('Pièce répétée')
        ids.add(piece['id'])
        meta = store.get_piece(piece['id'])
        if (meta['dossier_id'], meta['revision'], meta['role']) != (dossier_id, revision, 'candidate'):
            raise IntegrityError('Pièce étrangère ou réservée')
        if piece != {key: meta['piece_id'] if key == 'id' else meta[key] for key in piece}:
            raise IntegrityError('Métadonnées divergentes')
        store.read_piece(piece['id'])
    actual = {row[0] for row in store._connection.execute(
        "SELECT piece_id FROM pieces WHERE dossier_id=? AND revision=? AND role='candidate'",
        (dossier_id, revision))}
    if actual != ids:
        raise IntegrityError('Pièces candidates hors du paquet')
    return sorted(ids)


def view(store, session_id, dossier_id, revision=None):
    connection = connection_for(store)
    with _transaction(connection):
        current = owner(connection, session_id, dossier_id)
        if revision is None:
            revision = current
        _identity(dossier_id, revision)
        row = connection.execute('SELECT stage,explanation,package_json,package_sha256,changes_json,checks_json '
                                 'FROM s2_revisions WHERE dossier_id=? AND revision=?', (dossier_id, revision)).fetchone()
        if not row:
            raise Denied('Révision inaccessible')
        stage, explanation, raw, digest, changes, checks = row
        package = None if raw is None else json.loads(raw)
        if package is not None:
            package_check(store, dossier_id, revision, package, digest)
        validated = connection.execute('SELECT 1 FROM s2_validations WHERE dossier_id=? AND revision=? '
                                       'AND package_sha256=? AND session_id=?',
                                       (dossier_id, revision, digest, session_id)).fetchone()
        result = dict(dossier_id=dossier_id, revision=revision, payload=store.get_dossier(dossier_id, revision),
                      stage=stage, explanation=explanation, package=package, package_sha256=digest,
                      fictional=True, validation=binding(dossier_id, revision, digest) if validated else None,
                      qualified=False, changes=json.loads(changes), checks=json.loads(checks))
        result['rechecked'] = result['checks'].get('fields', [])
        completed = connection.execute('SELECT a.request_json,o.observed_cost_json FROM s2_actions a '
                                       'JOIN operations o USING(operation_id) WHERE a.dossier_id=? '
                                       'AND a.input_revision=? AND o.state=?',
                                       (dossier_id, revision - 1, 'RECEIVED')).fetchone()
        result['message'] = None if completed is None else json.loads(completed[0])
        result['observed_cost'] = None if completed is None else json.loads(completed[1])
        # Historic views are stable; only the current view projects an unfinished action
        if revision == current:
            pending = connection.execute('SELECT o.state FROM s2_actions a JOIN operations o USING(operation_id) '
                                         'WHERE a.dossier_id=? AND a.input_revision=? AND o.state!=?',
                                         (dossier_id, revision, 'RECEIVED')).fetchall()
            if pending:
                ambiguous = any(r[0] == 'AMBIGUOUS' for r in pending)
                blocked_intent = (any(r[0] == 'INTENT_RECORDED' for r in pending)
                                  and (admission(store, connection) is None or os.path.lexists(store._root / 'restore.json')))
                result['stage'] = 'suspended' if ambiguous or blocked_intent else 'waiting'
                result['explanation'] = (
                    'Effets inconnus : préparation suspendue, aucun rejeu autorisé.' if ambiguous else
                    'Admission fermée : intention conservée sans émission ni reprise automatique.' if blocked_intent else
                    'Préparation en attente. Actualisez pour consulter son avancement ; aucun appel ne sera relancé.')
                result['validation'] = None
        if connection.execute("SELECT 1 FROM sqlite_schema WHERE name='s3_control'").fetchone():
            from .qualification import projection
            result['qualification'] = projection(store, connection, dossier_id, revision,
                                                  eligible=result['validation'] is not None)
            result['qualified'] = result['qualification']['status'] in ('QUALIFIED', 'APPROVED')
        if connection.execute("SELECT 1 FROM sqlite_schema WHERE name='s4_control'").fetchone():
            from .campaigns import projection
            result['campaigns'] = projection(store, connection, dossier_id)
        return result


def piece_bytes(store, session_id, dossier_id, revision, piece_id):
    identifier(piece_id)
    current = view(store, session_id, dossier_id, revision)
    if current['package'] is None or piece_id not in {p['id'] for p in current['package']['pieces']}:
        raise Denied('Pièce inaccessible')
    return store.read_piece(piece_id)


def submit(store, session_id, dossier_id, body, source, transport_present):
    connection = connection_for(store)
    identifier(dossier_id)
    identifier(body['action_id'])
    create = 'request' in body
    kind = 'create' if create else body['kind']
    if kind not in ('create', 'clarify', 'correct'):
        raise ValueError('Action inconnue')
    message = body['request'] if create else body['message']
    _text(message, 'message')
    if not message.strip():
        raise ValueError('Message vide')
    if not create:
        _identity(dossier_id, body['revision'])
    request_json = encode(body)
    with _transaction(connection, write=True):
        existing = connection.execute('SELECT session_id,current_revision FROM s2_dossiers WHERE dossier_id=?',
                                      (dossier_id,)).fetchone()
        if existing and existing[0] != session_id:
            raise Denied('Dossier inaccessible')
        if not create and not existing:
            raise Denied('Dossier inaccessible')
        if existing:
            previous = connection.execute('SELECT request_json,operation_id FROM s2_actions WHERE dossier_id=? AND action_id=?',
                                          (dossier_id, body['action_id'])).fetchone()
            if previous:
                if previous[0] != request_json:
                    raise ConflictError('Identité déjà utilisée avec un autre contenu')
                return previous[1], False
            if create:
                raise ConflictError('Dossier déjà créé')
            if body['revision'] != existing[1]:
                raise ConflictError('Révision périmée')
        authority = admission(store, connection)
        if not authority or not transport_present or os.path.lexists(store._root / 'restore.json'):
            raise Denied('Admission fermée ou transport absent')
        # S2 admits one effect at a time; no restart drains a durable queue
        if connection.execute("SELECT 1 FROM s2_actions a JOIN operations o USING(operation_id) "
                              "WHERE o.state != 'RECEIVED' LIMIT 1").fetchone():
            raise ConflictError('Préparation active ou suspendue')
        revision = existing[1] if existing else 1
        if create:
            payload = dict(request=message, clarifications=[], reformulation='', validated_assumptions=[],
                           fictional_parameters={}, state='EN_ATTENTE')
            store.save_dossier(dossier_id, revision, payload)
            connection.execute('INSERT INTO s2_dossiers VALUES (?,?,?)', (dossier_id, session_id, revision))
            connection.execute('INSERT INTO s2_revisions VALUES (?,?,?, ?,NULL,NULL,?,?)',
                               (dossier_id, revision, 'draft', '', '[]', '{}'))
        operation_id = secrets.token_hex(16)
        context = store.get_dossier(dossier_id, revision)
        row = connection.execute('SELECT stage,explanation,package_json FROM s2_revisions WHERE dossier_id=? AND revision=?',
                                 (dossier_id, revision)).fetchone()
        # Exact context lives in immutable operation resources, distinct from the candidate package
        request = dict(message=message, kind=kind, payload=context, stage=row[0], explanation=row[1],
                       package=None if row[2] is None else json.loads(row[2]))
        request['pieces_seen'] = []
        for piece in (request['package'] or {}).get('pieces', []):
            request['pieces_seen'].append({'id': piece['id'], 'sha256': piece['sha256'],
                                           'content': store.read_piece(piece['id']).decode('utf-8')})
        resources = [encode(request)]
        operation = dict(operation_id=operation_id, phase='correction' if kind == 'correct' else 'preparation',
                         dossier_id=dossier_id, revision=revision, authority=authority['authority_id'],
                         engine_version=source, requested_configuration=authority['requested_configuration'], resources=resources)
        store._reserve_intent(connection, operation, authority['budget_id'], authority['reserve_amount'])
        connection.execute('INSERT INTO s2_actions VALUES (?,?,?,?,?,?)',
                           (dossier_id, body['action_id'], revision, kind, request_json, operation_id))
        return operation_id, True


def validate(store, session_id, dossier_id, body):
    _identity(dossier_id, body['revision'])
    if body['dossier_id'] != dossier_id:
        raise ConflictError('Dossier divergent')
    if type(body['package_sha256']) is not str or re.fullmatch('[0-9a-f]{64}', body['package_sha256']) is None:
        raise ValueError('Empreinte invalide')
    connection = connection_for(store)
    with _transaction(connection, write=True):
        revision = owner(connection, session_id, dossier_id)
        if revision != body['revision']:
            raise ConflictError('Révision périmée')
        if connection.execute("SELECT 1 FROM s2_actions a JOIN operations o USING(operation_id) "
                              "WHERE a.dossier_id=? AND o.state!='RECEIVED'", (dossier_id,)).fetchone():
            raise ConflictError('Préparation inachevée')
        stage, raw, digest = connection.execute('SELECT stage,package_json,package_sha256 FROM s2_revisions '
                                               'WHERE dossier_id=? AND revision=?', (dossier_id, revision)).fetchone()
        if stage != 'preview' or raw is None or digest != body['package_sha256']:
            raise ConflictError('Paquet divergent ou non validable')
        package_check(store, dossier_id, revision, json.loads(raw), digest)
        connection.execute('INSERT OR IGNORE INTO s2_validations VALUES (?,?,?,?,?)',
                           (dossier_id, revision, digest, session_id, datetime.now(timezone.utc).isoformat()))
        return binding(dossier_id, revision, digest)


def execute(data, operation_id, transport):
    """Only the submitting executor starts this work, never inspection or startup."""
    with closing(Store(data)) as store:
        connection = connection_for(store)
        emitted = False
        try:
            proof = store.verify_storage()
            if not proof['integrity_ok'] or proof['orphan_files']:
                close_admission(store)
                return
            with _transaction(connection, write=True):
                operation = store._operation_for_update(connection, operation_id, ('INTENT_RECORDED',))
                authority = admission(store, connection)
                if (transport is None or authority is None or os.path.lexists(store._root / 'restore.json')
                        or authority != dict(authority_id=operation['authority'], budget_id=operation['budget_id'],
                                             reserve_amount=operation['reserved_amount'],
                                             requested_configuration=operation['requested_configuration'])):
                    return
                budget = store._budget(connection, operation['budget_id'], store._operations(connection))
                if budget['unknown_cost_operations'] or _sum_money((_money(budget['reserved']), _money(budget['spent']))) > _money(budget['limit']):
                    return
                if any(row['operation_id'] != operation_id and row['budget_id'] == operation['budget_id']
                       and row['state'] in ('EMISSION_POSSIBLE', 'AMBIGUOUS') for row in store._operations(connection)):
                    return
                connection.execute("UPDATE operations SET state='EMISSION_POSSIBLE' WHERE operation_id=?", (operation_id,))
            emitted = True
            operation['state'] = 'EMISSION_POSSIBLE'
            request = json.loads(operation['resources'][0])
            response = transport(deepcopy(operation), deepcopy(request))
            _fields(response, ('receipt', 'cost'), 'transport response')
            try:
                publish(store, operation, request, response)
            except Exception:
                # Publication rolled back; keep the original receipt with an unusable revision
                # RECEIVED and closed admission become visible in the same commit
                with _transaction(connection, write=True):
                    dossier_id, before = operation['dossier_id'], operation['revision']
                    current = connection.execute('SELECT current_revision FROM s2_dossiers WHERE dossier_id=?',
                                                 (dossier_id,)).fetchone()[0]
                    if current != before:
                        raise ConflictError('Révision changée pendant la préparation')
                    revision = before + 1
                    store._record_receipt(connection, operation_id, response['receipt'], response['cost'])
                    store.save_dossier(dossier_id, revision, request['payload'])
                    connection.execute('INSERT INTO s2_revisions VALUES (?,?,?,?,NULL,NULL,?,?)',
                                       (dossier_id, revision, 'suspended',
                                        'Résultat reçu non utilisable : préparation suspendue. '
                                        'Reçu et coût conservés ; aucune reprise automatique.',
                                        encode(['stage', 'explanation']), encode({'result_verified': False})))
                    connection.execute('UPDATE s2_dossiers SET current_revision=? WHERE dossier_id=?',
                                       (revision, dossier_id))
                    connection.execute('UPDATE s2_control SET admission_json=NULL WHERE singleton=1')
        except Exception:
            # Never log request/response/exception text, which may contain private data
            if emitted:
                store.mark_ambiguous(operation_id, 'PREPARATION_RESULT_NOT_VERIFIED')


def publish(store, operation, request, response):
    result = response['receipt']['result']
    _fields(result, ('stage', 'explanation', 'reformulation', 'fictional_parameters', 'package'), 'preparation result')
    stage = result['stage']
    if stage not in ('clarification', 'preview', 'scope_confirmation', 'suspended'):
        raise ValueError('État inconnu')
    if type(result['explanation']) is not str or (stage != 'preview' and not result['explanation']):
        raise ValueError('Explication requise')
    if (stage == 'preview') != (result['package'] is not None):
        raise ValueError('Paquet incohérent avec l’état')
    dossier_id, before = operation['dossier_id'], operation['revision']
    payload = deepcopy(request['payload'])
    if request['kind'] == 'clarify':
        payload['clarifications'].append(request['message'])
        # The answer remains attributed user input, never an assistant-invented agreement
        payload['validated_assumptions'].append({'question': request['explanation'], 'answer': request['message']})
    payload['reformulation'] = result['reformulation']
    payload['fictional_parameters'] = result['fictional_parameters']
    _payload_json(payload)
    connection = connection_for(store)
    with _transaction(connection, write=True):
        current = connection.execute('SELECT current_revision FROM s2_dossiers WHERE dossier_id=?', (dossier_id,)).fetchone()[0]
        if current != before:
            raise ConflictError('Révision changée pendant la préparation')
        revision = before + 1
        store.save_dossier(dossier_id, revision, payload)
        package, digest, checks = None, None, {}
        if result['package'] is not None:
            source = result['package']
            _fields(source, ('instruction', 'deliverables', 'criteria', 'acceptable_ambiguities',
                             'human_work', 'limits', 'pieces'), 'package')
            package = {key: deepcopy(value) for key, value in source.items() if key != 'pieces'}
            package['pieces'] = []
            checked = []
            if type(source['pieces']) is not list:
                raise ValueError('Pièces requises')
            roles = set()
            for piece in source['pieces']:
                _fields(piece, ('name', 'role', 'content'), 'transport piece')
                if type(piece['content']) is not str:
                    raise ValueError('Texte de pièce requis')
                raw = piece['content'].encode('utf-8')
                meta = store._put_piece(connection, dossier_id, revision, secrets.token_hex(16),
                                       name=piece['name'], role=piece['role'], media_type='text/plain; charset=utf-8', content=raw)
                if store.read_piece(meta['piece_id']) != raw:
                    raise IntegrityError('Pièce divergente')
                roles.add(meta['role'])
                checked.append({'id': meta['piece_id'], 'sha256': meta['sha256']})
                if meta['role'] == 'candidate':
                    package['pieces'].append(dict(id=meta['piece_id'], name=meta['name'],
                                                  sha256=meta['sha256'], size_bytes=meta['size_bytes']))
            if roles != {'candidate', 'judge'}:
                raise IntegrityError('Pièces candidates et référence distincte requises')
            digest = sha256(encode(package).encode()).hexdigest()
            package_check(store, dossier_id, revision, package, digest)
            # Do not expose judge piece identities in the requester projection
            checks = {'method': 'stored-bytes-sha256-and-package-structure/v1', 'package_sha256': digest,
                      'pieces': [item for item in checked if item['id'] in {p['id'] for p in package['pieces']}],
                      'reference_bytes_verified': True, 'reference_qualification': 'NON VÉRIFIÉ'}
        old_package = request['package'] or {}
        changes = [key for key in (package or {}) if (package or {})[key] != old_package.get(key)]
        if package is None:
            changes = ['stage', 'explanation']
        checks['fields'] = changes
        connection.execute('INSERT INTO s2_revisions VALUES (?,?,?,?,?,?,?,?)',
                           (dossier_id, revision, stage, result['explanation'], None if package is None else encode(package),
                            digest, encode(changes), encode(checks)))
        store._record_receipt(connection, operation['operation_id'], response['receipt'], response['cost'])
        connection.execute('UPDATE s2_dossiers SET current_revision=? WHERE dossier_id=?', (revision, dossier_id))


def verify_preparation(store, connection):
    """Check the S2 joins and actual package bytes in the caller's snapshot."""
    admission(store, connection)
    for dossier_id, session_id, current in connection.execute('SELECT * FROM s2_dossiers').fetchall():
        identifier(dossier_id)
        if not connection.execute('SELECT 1 FROM s2_revisions WHERE dossier_id=? AND revision=?', (dossier_id, current)).fetchone():
            raise IntegrityError('Pointeur S2 sans révision publiée')
    for dossier_id, revision, stage, explanation, raw, digest, changes, checks in connection.execute('SELECT * FROM s2_revisions').fetchall():
        if not connection.execute('SELECT 1 FROM s2_dossiers WHERE dossier_id=?', (dossier_id,)).fetchone():
            raise IntegrityError('Révision sans propriétaire')
        if type(json.loads(changes)) is not list or type(json.loads(checks)) is not dict:
            raise IntegrityError('Contrôles de révision invalides')
        if raw is not None:
            package_check(store, dossier_id, revision, json.loads(raw), digest)
    for dossier_id, revision, digest, session_id, date in connection.execute('SELECT * FROM s2_validations').fetchall():
        if not connection.execute('SELECT 1 FROM s2_dossiers d JOIN s2_revisions r USING(dossier_id) '
                                  'WHERE d.dossier_id=? AND d.session_id=? AND r.revision=? AND r.package_sha256=? AND r.stage=?',
                                  (dossier_id, session_id, revision, digest, 'preview')).fetchone():
            raise IntegrityError('Validation étrangère ou divergente')
    for dossier_id, action_id, revision, kind, raw, operation_id in connection.execute('SELECT * FROM s2_actions').fetchall():
        identifier(action_id)
        if not connection.execute('SELECT 1 FROM operations WHERE operation_id=? AND dossier_id=? AND revision=? '
                                  'AND phase=?', (operation_id, dossier_id, revision,
                                                'correction' if kind == 'correct' else 'preparation')).fetchone():
            raise IntegrityError('Action sans intention attribuée')
        encode(json.loads(raw, object_pairs_hook=_unique_object))


def dispatch(store, method, path, token, body, source, transport_present):
    """Executor-side authorization: HTTP fields can never claim an operator role."""
    if method == 'GET' and path == '/preparation':
        session_id, csrf, token = session(store, token, create=True)
        rows = connection_for(store).execute('SELECT dossier_id,current_revision FROM s2_dossiers WHERE session_id=? ORDER BY dossier_id',
                                            (session_id,)).fetchall()
        return 200, {'csrf_token': csrf, 'dossiers': [{'dossier_id': d, 'revision': r} for d, r in rows]}, token, None
    session_id, csrf, _ = session(store, token)
    if method == 'POST':
        if type(body) is not dict:
            raise ValueError('Formulaire requis')
        supplied = body.get('csrf_token')
        if type(supplied) is not str or not hmac.compare_digest(supplied.encode(), csrf.encode()):
            raise Denied('Protection CSRF requise')
        body = {key: value for key, value in body.items() if key != 'csrf_token'}
    if method == 'POST' and path == '/preparation/dossiers':
        _fields(body, ('dossier_id', 'action_id', 'request'), 'create')
        operation_id, start = submit(store, session_id, body['dossier_id'], body, source, transport_present)
        return 202, {'operation_id': operation_id, 'dossier_id': body['dossier_id']}, None, operation_id if start else None
    match = re.fullmatch(r'/preparation/dossiers/([A-Za-z0-9_-]{1,128})(?:/(messages|validation)|/revisions/([1-9][0-9]*)(?:/pieces/([A-Za-z0-9_-]{1,128}))?)?', path)
    if not match:
        raise Denied('Ressource inaccessible')
    dossier_id, action, revision, piece_id = match.groups()
    owner(connection_for(store), session_id, dossier_id)
    revision = None if revision is None else int(revision)
    if method == 'GET' and action is None:
        if piece_id:
            return 200, piece_bytes(store, session_id, dossier_id, revision, piece_id), None, None
        result = view(store, session_id, dossier_id, revision)
        # The CSRF token travels independently in HTML rendering through the web's session query
        return 200, result, None, None
    if method == 'POST' and action == 'messages':
        _fields(body, ('action_id', 'revision', 'kind', 'message'), 'message')
        operation_id, start = submit(store, session_id, dossier_id, body, source, transport_present)
        return 202, {'operation_id': operation_id, 'dossier_id': dossier_id}, None, operation_id if start else None
    if method == 'POST' and action == 'validation':
        _fields(body, ('dossier_id', 'revision', 'package_sha256'), 'validation')
        return 200, validate(store, session_id, dossier_id, body), None, None
    raise Denied('Action inaccessible')


def render(value, csrf, path='/preparation', *, error=False):
    """Native HTML forms: no script, no untrusted HTML and no external resources."""
    def text(value):
        return escape(str(value), quote=True)

    def hidden(name, value):
        return f'<input type="hidden" name="{text(name)}" value="{text(value)}">'

    def form(url, fields, content):
        return (f'<form method="post" action="{text(url)}">' + hidden('csrf_token', csrf)
                + ''.join(hidden(k, v) for k, v in fields.items()) + content + '</form>')

    def section(title, content):
        return f'<section><h2>{text(title)}</h2>{content}</section>'

    def listing(values):
        return '<ul>' + ''.join(f'<li>{text(v)}</li>' for v in values) + '</ul>'

    title = 'Préparer un exemple fictif'
    if error:
        content = '<p role="alert">' + text(value['error']) + '</p><p><a href="/preparation">Retrouver mes dossiers</a></p>'
    elif 'dossiers' in value:
        content = section('Mes dossiers dans ce navigateur', '<ul>' + ''.join(
            f'<li><a href="/preparation/dossiers/{text(d["dossier_id"])}">Dossier {text(d["dossier_id"])} — révision {d["revision"]}</a></li>'
            for d in value['dossiers']) + '</ul>')
        content += section('Décrire mon besoin', form('/preparation/dossiers',
            {'dossier_id': secrets.token_hex(16), 'action_id': secrets.token_hex(16)},
            '<label for="request">Une tâche de votre travail</label><p id="request-help">Décrivez le travail et le résultat utile, sans donnée personnelle ni information confidentielle. Aucun dossier réel, même anonymisé.</p>'
            '<textarea id="request" name="request" required rows="5" aria-describedby="request-help"></textarea>'
            '<button type="submit">Préparer cet exemple</button>'))
    elif 'operation_id' in value:
        title = 'Demande enregistrée'
        url = '/preparation/dossiers/' + value['dossier_id']
        content = '<p role="status">Préparation en attente. L’envoi a été enregistré.</p>'
        content += f'<p><a href="{text(url)}">Consulter le dossier et son avancement</a></p>'
    else:
        dossier_id, revision = value['dossier_id'], value['revision']
        url = '/preparation/dossiers/' + dossier_id
        title = f'Dossier fictif — révision {revision}'
        stages = {'draft': 'Brouillon', 'waiting': 'Préparation en attente', 'clarification': 'Précision nécessaire',
                  'preview': 'Exemple à examiner', 'scope_confirmation': 'Périmètre à confirmer', 'suspended': 'Préparation suspendue'}
        content = '<p role="status">' + text(stages[value['stage']]) + '</p>'
        content += '<p>' + text(value['explanation']) + '</p>'
        content += f'<p><a href="{text(path)}">Actualiser cet état</a> · <a href="{text(url)}">Révision courante</a></p>'
        if revision > 1:
            content += f'<p><a href="{text(url)}/revisions/{revision - 1}">Consulter la révision précédente</a></p>'
        payload = value['payload']
        content += section('Besoin conservé', '<p>' + text(payload['request']) + '</p>')
        if value.get('message') and 'message' in value['message']:
            content += section('Message à l’origine de cette révision', '<p>' + text(value['message']['message']) + '</p>')
        content += section('Précisions et accords conservés', listing(payload['clarifications']) +
                           listing(encode(a) if type(a) is dict else a for a in payload['validated_assumptions']))
        if payload['reformulation']:
            content += section('Reformulation', '<p>' + text(payload['reformulation']) + '</p>')
        content += section('Paramètres entièrement inventés', listing(f'{k} : {v}' for k, v in payload['fictional_parameters'].items()))
        package = value['package']
        if package:
            content += section('Consigne exacte du paquet', '<p>' + text(package['instruction']) + '</p>')
            for field, label in (('deliverables', 'Livrables attendus'), ('criteria', 'Critères compréhensibles'),
                                 ('acceptable_ambiguities', 'Ambiguïtés recevables'), ('limits', 'Limites de l’exemple')):
                content += section(label, listing(package[field]))
            content += section('Travail humain restant', '<p>' + text(package['human_work']) + '</p>')
            content += section('Pièces du paquet à ouvrir', '<ul>' + ''.join(
                f'<li><a href="{text(url)}/revisions/{revision}/pieces/{text(p["id"])}">{text(p["name"])} (texte, {p["size_bytes"]} octets)</a></li>'
                for p in package['pieces']) + '</ul><p>La référence privée de jugement est séparée des pièces présentées.</p>')
            content += section('Changements et vérifications', listing(value['changes']) +
                               '<p>Les octets des pièces et l’empreinte du paquet ont été vérifiés.</p>')
            content += '<p>Empreinte du paquet : <code>' + text(value['package_sha256']) + '</code></p>'
        if value.get('observed_cost'):
            cost = value['observed_cost']
            content += '<p>Coût observé de cette préparation : ' + text(
                'INCONNU' if cost['status'] == 'UNKNOWN' else cost['amount'] + ' ' + cost['currency']) + '. Source : ' + text(cost['source']) + '.</p>'
        else:
            content += '<p>Coût observé : INCONNU en l’absence de reçu de coût.</p>'
        if value['validation']:
            content += '<p role="status">Votre validation est enregistrée pour ce dossier, cette révision et cette empreinte.</p>'
        else:
            content += '<p role="status">Validation du besoin : nouvelle validation requise pour le paquet présenté.</p>'
        qualification = value.get('qualification', {})
        labels = {'PENDING': 'En attente', 'QUALIFIED': 'Contrôles requis prouvés',
                  'BLOCKED': 'Bloquée : référence ou contrôles insuffisamment prouvés',
                  'APPROVED': 'Approuvée par action opérateur locale'}
        content += section('Qualification', '<p>' + text(labels.get(
            qualification.get('qualification_status'), 'En attente')) + '</p>')
        content += section('Approbation', '<p>' + text(labels.get(
            qualification.get('approval_status'), 'En attente')) + '</p>'
            '<p>La validation du besoin, la qualification et l’approbation restent distinctes. '
            'Aucun appel ni publication n’est autorisé par cet état. Les preuves, la référence '
            'et les limites de jugement sont réservées à l’inspection locale du responsable.</p>')
        if qualification.get('contract_sha256'):
            content += '<p>Contrat : <code>' + text(qualification['contract_sha256']) + '</code></p>'
        if 'campaigns' in value:
            campaigns = '<p>Suivi privé des comparaisons fictives de ce dossier. '
            campaigns += 'L’acquisition conserve des reçus ; elle ne juge pas le contenu des sorties.</p>'
            technical = {'NOT_STARTED': 'Non lancée : aucune tentative', 'INTENT_RECORDED': 'Intention enregistrée',
                         'EMISSION_POSSIBLE': 'Appel actif ou émission possible, reçu en attente',
                         'AMBIGUOUS': 'Effets inconnus : reprise bloquée', 'RECEIVED': 'Reçu conservé'}
            for campaign in value['campaigns']:
                task = campaign['task']
                campaigns += '<article><h3>Campagne ' + text(campaign['campaign_id']) + '</h3>'
                campaigns += '<p>Tâche ' + text(task['dossier_id']) + ', version ' + text(task['version'])
                campaigns += ', révision du dossier ' + text(task['revision']) + '.</p>'
                for label, digest in (('Manifeste', campaign['manifest_sha256']), ('Contrat', campaign['contract_sha256']),
                                      ('Paquet', task['package_sha256'])):
                    campaigns += '<p>' + label + ' : <code>' + text(digest) + '</code></p>'
                campaigns += '<h4>Configurations demandées</h4>' + listing(
                    f'{c["id"]} : {c["model"]}, révision {c["revision"]}, fournisseur {c["provider"]}, '
                    f'accès {c["access"]}, canal {c["channel_id"]}, route {c["route"]}, effort {c["effort"]}, '
                    f'paramètres {encode(c["parameters"])} ; observations exigées : {", ".join(c["required_observations"])}'
                    for c in campaign['panel'])
                conditions = campaign['conditions']
                pi = conditions['pi']
                campaigns += '<h4>Conditions Pi communes</h4><p>' + text(
                    f'{pi["package"]} {pi["version"]} ; état {pi["status"]} ; gel {conditions["frozen_at"]}') + '</p>'
                campaigns += '<p>Empreinte Pi : <code>' + text(pi['sha256']) + '</code></p>'
                campaigns += '<details><summary>Contexte et environnement communs</summary>' + listing(
                    f'{k} : {encode(conditions[k])}' for k in ('context_sha256', 'packages', 'tools', 'skills', 'defaults', 'environment')) + '</details>'
                campaigns += '<h4>Autorités et budget</h4><p>' + (
                    'Admission opérateur ouverte pour les cellules : ' + text(', '.join(campaign['allowed_cells'])) if campaign['admission_open'] else
                    'Admission fermée. Autorités à fournir ou renouveler par l’opérateur : ' + text(', '.join(campaign['missing_authorities']))) + '.</p>'
                if campaign['restore_pending']:
                    campaigns += '<p>Restauration à rapprocher : toute nouvelle admission reste bloquée.</p>'
                if campaign['stop_reason']:
                    campaigns += '<p>Motif d’arrêt : ' + text(campaign['stop_reason']) + '.</p>'
                budget = campaign['budget']
                if budget:
                    campaigns += '<p>' + text(f'Enveloppe {budget["budget_id"]} : {budget["limit"]} {budget["currency"]}. '
                        f'Sous-total des coûts connus : {budget["spent"]}. Réservations conservées : {budget["reserved"]}. '
                        f'Solde disponible : {budget["available"] if budget["balance_status"] == "KNOWN" else "INCONNU"}.') + '</p>'
                else:
                    campaigns += '<p>Budget prévu : INCONNU, enveloppe à désigner par l’opérateur.</p>'
                campaigns += '<p>Prévisions de réserve par cellule : ' + text(
                    encode(campaign['reserve_amounts']) if campaign['reserve_amounts'] else 'INCONNU, autorité attendue') + '.</p>'
                campaigns += '<p>Base de coût : ' + text(encode(campaign['cost_basis'])) + '.</p>'
                campaigns += '<p>La réservation ne prouve pas un plafond de facturation. Préparation et jugement conservent leurs opérations propres.</p>'
                campaigns += '<h4>Cellules prévues</h4>' + listing(
                    f'{c["cell_id"]} — cas {c["case_id"]}, configuration {c["configuration_id"]} : {technical[c["state"]]}'
                    for c in campaign['cells'])
                for attempt in campaign['attempts']:
                    campaigns += '<details><summary>Tentative ' + text(attempt['operation_id']) + ' — ' + text(technical[attempt['state']]) + '</summary>'
                    campaigns += '<p>Exécution ' + text(attempt['execution_id']) + ', cellule ' + text(attempt['cell_id']) + '.</p>'
                    campaigns += '<p>Intention : ' + text(attempt['created_at']) + '. Émission possible : ' + text(attempt['emitted_at'] or 'Non lancée')
                    campaigns += '. Réception : ' + text(attempt['received_at'] or 'INCONNU') + '.</p>'
                    campaigns += '<p>Reçu : ' + text(attempt['receipt_id'] or 'Absent') + '. Preuve d’émission : ' + text(attempt['emission']) + '.</p>'
                    campaigns += '<p>Configuration observée : ' + text(encode(attempt['observed_configuration'])) + '.</p>'
                    campaigns += '<p>Sources des observations : ' + text(encode(attempt['observation_sources'])) + '.</p>'
                    cost = attempt['observed_cost']
                    campaigns += '<p>Coût observé : ' + text('INCONNU' if cost is None or cost['status'] == 'UNKNOWN' else cost['amount'] + ' ' + cost['currency'])
                    campaigns += '. Source : ' + text(cost['source'] if cost else 'INCONNU') + '.</p>'
                    if attempt['incident']:
                        campaigns += '<p>Incident technique : ' + text(attempt['incident']) + '.</p>'
                    if attempt['attribution_incident']:
                        campaigns += '<p>Attribution non prouvée : ' + text(', '.join(attempt['attribution_incident'])) + '.</p>'
                    campaigns += '<p>Sortie brute réservée à l’inspection opérateur. Aucun verdict de contenu produit.</p></details>'
                campaigns += '</article>'
            if not value['campaigns']:
                campaigns += '<p>Aucune campagne liée à ce dossier.</p>'
            content += section('Comparaisons de ce dossier', campaigns)
        if value['stage'] != 'waiting':
            content += section('Préciser ou corriger cet exemple', form(url + '/messages',
                {'action_id': secrets.token_hex(16), 'revision': revision},
                '<label for="kind">Objet du message</label><select id="kind" name="kind">'
                '<option value="clarify">Répondre à la clarification ou confirmer le périmètre</option>'
                '<option value="correct">Modifier cet exemple</option></select>'
                '<label for="message">Votre précision ou correction</label>'
                '<textarea id="message" name="message" rows="4" required></textarea><button type="submit">Envoyer ce message</button>'))
        if package and value['stage'] == 'preview' and value['validation'] is None:
            content += section('Valider le besoin représenté', '<p>Cette validation concerne uniquement ce paquet. Elle n’approuve ni contrat, ni appel, ni dépense, ni publication.</p>' +
                form(url + '/validation', binding(dossier_id, revision, value['package_sha256']),
                     '<button type="submit">Valider cette révision et ce paquet exacts</button>'))
    template = Path(__file__).with_name('preparation.html').read_text()
    return template.replace('{{title}}', text(title)).replace('{{content}}', content).encode('utf-8')
