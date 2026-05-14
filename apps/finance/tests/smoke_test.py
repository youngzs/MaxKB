# coding=utf-8
"""
Finance module end-to-end smoke test.

This is NOT a pytest / Django unit test — it is a standalone script ops
can run against a *live* deployment to verify the finance module is
healthy after a deploy. It uses only the Python standard library
(``urllib``) so it can run inside the container with zero extra deps.

Run inside the container::

    python apps/finance/tests/smoke_test.py \
        --base-url http://127.0.0.1:8080 \
        --token <admin-token>

Or against a remote host::

    python apps/finance/tests/smoke_test.py \
        --base-url https://maxkb.example.com \
        --token <admin-token> \
        --workspace default \
        --admin-path /admin

Exercises (8 checks):
  1. GET  /ping                                   -> 200, status == ok
  2. GET  /healthz                                -> 200, overall in (ok, degraded)
  3. GET  /workspace/<ws>/ai-status               -> 200, shows llm config
  4. GET  /workspace/<ws>/system-info             -> 200 (needs token)
  5. POST /workspace/<ws>/project                 -> create a throwaway project
  6. GET  /workspace/<ws>/project                 -> list includes the throwaway
  7. DELETE /workspace/<ws>/project/<id>          -> remove the throwaway
  8. GET  /workspace/<ws>/workflow-run            -> 200 (list)

Prints a ``PASS``/``FAIL`` line per check and exits 0 iff every check
passed, 1 otherwise. Each check is wrapped in its own try/except so one
failure does not abort the remaining checks — ops gets the full picture
from a single run.

Notes:
  * The finance routes are mounted under ``<admin-path>/api/finance/``
    (admin-path defaults to ``/admin``). ``/ping`` and ``/healthz`` need
    no auth; everything else needs an admin Bearer token.
  * Check 7 only runs if check 5 actually created a project — otherwise
    it is reported as a SKIP (counted as neither pass nor fail) so we do
    not leave orphan throwaway projects *and* do not mask the real
    failure (the create) behind a delete failure.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid


# --------------------------------------------------------------------------
# Tiny HTTP helper — stdlib only.
# --------------------------------------------------------------------------
def _request(method, url, token=None, body=None, timeout=15):
    """Perform an HTTP request. Returns (status_code, parsed_json_or_text).

    Never raises for HTTP-level errors (4xx/5xx) — those come back as a
    normal (status, body) tuple. Only transport-level failures (DNS,
    connection refused, timeout) raise, and callers catch those.
    """
    data = None
    headers = {'Accept': 'application/json'}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = f'Bearer {token}'

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
            return resp.status, _maybe_json(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace') if exc.fp else ''
        return exc.code, _maybe_json(raw)


def _maybe_json(raw):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


# --------------------------------------------------------------------------
# Result accounting.
# --------------------------------------------------------------------------
class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def ok(self, name, detail=''):
        self.passed += 1
        suffix = f'  ({detail})' if detail else ''
        print(f'PASS  {name}{suffix}')

    def fail(self, name, detail=''):
        self.failed += 1
        suffix = f'  ({detail})' if detail else ''
        print(f'FAIL  {name}{suffix}')

    def skip(self, name, detail=''):
        self.skipped += 1
        suffix = f'  ({detail})' if detail else ''
        print(f'SKIP  {name}{suffix}')


def _envelope_data(payload):
    """Extract the ``data`` field from MaxKB's standard result envelope.

    MaxKB wraps responses as ``{"code": 200, "message": ..., "data": ...}``.
    Returns the inner data, or the raw payload if it is not enveloped.
    """
    if isinstance(payload, dict) and 'data' in payload:
        return payload['data']
    return payload


# --------------------------------------------------------------------------
# Individual checks. Each takes (ctx, results) and is fully self-contained.
# --------------------------------------------------------------------------
def check_ping(ctx, results):
    name = '1. GET /ping'
    try:
        status, payload = _request('GET', f'{ctx["finance_base"]}/ping')
        if status != 200:
            results.fail(name, f'HTTP {status}')
            return
        data = _envelope_data(payload)
        if isinstance(data, dict) and data.get('status') == 'ok':
            results.ok(name, f'version={data.get("version")}')
        else:
            results.fail(name, f'status != ok: {data}')
    except Exception as exc:  # noqa: BLE001
        results.fail(name, f'exception: {exc!r}')


def check_healthz(ctx, results):
    name = '2. GET /healthz'
    try:
        status, payload = _request('GET', f'{ctx["finance_base"]}/healthz')
        if status != 200:
            results.fail(name, f'HTTP {status}')
            return
        data = _envelope_data(payload)
        overall = data.get('overall') if isinstance(data, dict) else None
        if overall in ('ok', 'degraded'):
            results.ok(name, f'overall={overall} db={data.get("db")} cache={data.get("cache")}')
        else:
            results.fail(name, f'unexpected overall: {data}')
    except Exception as exc:  # noqa: BLE001
        results.fail(name, f'exception: {exc!r}')


def check_ai_status(ctx, results):
    name = '3. GET /ai-status'
    try:
        url = f'{ctx["ws_base"]}/ai-status'
        status, payload = _request('GET', url, token=ctx['token'])
        if status != 200:
            results.fail(name, f'HTTP {status}')
            return
        data = _envelope_data(payload)
        if isinstance(data, dict) and 'llm_configured' in data:
            llm = data.get('llm_configured')
            model = data.get('llm_model_name')
            degraded = data.get('degraded_features') or []
            detail = f'llm_configured={llm} model={model} degraded={len(degraded)}'
            results.ok(name, detail)
        else:
            results.fail(name, f'missing llm_configured: {data}')
    except Exception as exc:  # noqa: BLE001
        results.fail(name, f'exception: {exc!r}')


def check_system_info(ctx, results):
    name = '4. GET /system-info'
    try:
        url = f'{ctx["ws_base"]}/system-info'
        status, payload = _request('GET', url, token=ctx['token'])
        if status != 200:
            results.fail(name, f'HTTP {status} (needs admin token)')
            return
        data = _envelope_data(payload)
        if isinstance(data, dict) and 'module_version' in data:
            wf = data.get('workflows_installed') or []
            installed = sum(1 for w in wf if isinstance(w, dict) and w.get('installed'))
            results.ok(name, f'version={data.get("module_version")} workflows_installed={installed}/{len(wf)}')
        else:
            results.fail(name, f'unexpected body: {data}')
    except Exception as exc:  # noqa: BLE001
        results.fail(name, f'exception: {exc!r}')


def check_create_project(ctx, results):
    """Create a throwaway project. Stashes the new id in ctx for checks 6/7."""
    name = '5. POST /project (create throwaway)'
    try:
        url = f'{ctx["ws_base"]}/project'
        marker = f'smoke-test-{uuid.uuid4().hex[:8]}'
        body = {
            'name': marker,
            'project_type': 'other',
            'description': 'Created by finance smoke_test.py — safe to delete.',
        }
        status, payload = _request('POST', url, token=ctx['token'], body=body)
        if status != 200:
            results.fail(name, f'HTTP {status}: {payload}')
            return
        data = _envelope_data(payload)
        new_id = data.get('id') if isinstance(data, dict) else None
        if new_id:
            ctx['throwaway_project_id'] = new_id
            ctx['throwaway_project_name'] = marker
            results.ok(name, f'id={new_id}')
        else:
            results.fail(name, f'no id in response: {data}')
    except Exception as exc:  # noqa: BLE001
        results.fail(name, f'exception: {exc!r}')


def check_list_project(ctx, results):
    name = '6. GET /project (list includes throwaway)'
    try:
        url = f'{ctx["ws_base"]}/project'
        status, payload = _request('GET', url, token=ctx['token'])
        if status != 200:
            results.fail(name, f'HTTP {status}')
            return
        data = _envelope_data(payload)
        records = data.get('records') if isinstance(data, dict) else None
        if records is None:
            results.fail(name, f'no records field: {data}')
            return
        target_id = ctx.get('throwaway_project_id')
        if target_id is None:
            # Create failed — still verify the list endpoint works at all.
            results.ok(name, f'list returned {len(records)} rows (create skipped, no id to match)')
            return
        ids = {r.get('id') for r in records if isinstance(r, dict)}
        if target_id in ids:
            results.ok(name, f'throwaway found among {len(records)} rows')
        else:
            # The throwaway may be on a later page; not a hard fail, but flag it.
            results.fail(name, f'throwaway {target_id} not in first page of {len(records)} rows')
    except Exception as exc:  # noqa: BLE001
        results.fail(name, f'exception: {exc!r}')


def check_delete_project(ctx, results):
    name = '7. DELETE /project (cleanup throwaway)'
    target_id = ctx.get('throwaway_project_id')
    if target_id is None:
        results.skip(name, 'create did not produce a project id — nothing to delete')
        return
    try:
        url = f'{ctx["ws_base"]}/project/{target_id}'
        status, payload = _request('DELETE', url, token=ctx['token'])
        if status == 200:
            results.ok(name, f'deleted {target_id}')
        else:
            results.fail(name, f'HTTP {status}: {payload} — MANUAL CLEANUP NEEDED for {target_id}')
    except Exception as exc:  # noqa: BLE001
        results.fail(name, f'exception: {exc!r} — MANUAL CLEANUP NEEDED for {target_id}')


def check_workflow_run(ctx, results):
    name = '8. GET /workflow-run (list)'
    try:
        url = f'{ctx["ws_base"]}/workflow-run'
        status, payload = _request('GET', url, token=ctx['token'])
        if status != 200:
            results.fail(name, f'HTTP {status}')
            return
        data = _envelope_data(payload)
        if isinstance(data, dict) and 'records' in data:
            results.ok(name, f'total={data.get("total")}')
        else:
            results.fail(name, f'no records field: {data}')
    except Exception as exc:  # noqa: BLE001
        results.fail(name, f'exception: {exc!r}')


# --------------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Finance module end-to-end smoke test (stdlib only).',
    )
    parser.add_argument(
        '--base-url', required=True,
        help='Deployment base URL, e.g. http://127.0.0.1:8080',
    )
    parser.add_argument(
        '--token', default='',
        help='Admin Bearer token. Required for checks 3-8; '
             'ping/healthz run without it.',
    )
    parser.add_argument(
        '--workspace', default='default',
        help='Workspace id to probe (default: default).',
    )
    parser.add_argument(
        '--admin-path', default='/admin',
        help="Admin path prefix the finance routes are mounted under "
             "(default: /admin — matches ADMIN_PATH).",
    )
    args = parser.parse_args(argv)

    base = args.base_url.rstrip('/')
    admin_path = '/' + args.admin_path.strip('/')
    finance_base = f'{base}{admin_path}/api/finance'
    ws_base = f'{finance_base}/workspace/{args.workspace}'

    ctx = {
        'finance_base': finance_base,
        'ws_base': ws_base,
        'token': args.token,
        'workspace': args.workspace,
    }

    print('=' * 64)
    print('Finance module smoke test')
    print(f'  base-url   : {base}')
    print(f'  finance    : {finance_base}')
    print(f'  workspace  : {args.workspace}')
    print(f'  token      : {"<set>" if args.token else "<MISSING — checks 3-8 will fail>"}')
    print('=' * 64)

    results = Results()
    checks = [
        check_ping,
        check_healthz,
        check_ai_status,
        check_system_info,
        check_create_project,
        check_list_project,
        check_delete_project,
        check_workflow_run,
    ]
    for check in checks:
        try:
            check(ctx, results)
        except Exception as exc:  # noqa: BLE001 — last-resort guard
            # A check should handle its own exceptions; this is belt-and-braces
            # so one rogue check can never abort the run.
            results.fail(check.__name__, f'uncaught: {exc!r}')

    print('=' * 64)
    print(f'RESULT: {results.passed} passed, {results.failed} failed, '
          f'{results.skipped} skipped')
    print('=' * 64)

    return 0 if results.failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
