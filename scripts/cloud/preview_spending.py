"""Private GCS generation-CAS cumulative financial authorization; no daily quotas.

No resource or ledger is implicitly created. Scope revisions, new days, restarts
and failed provider calls cannot restore financial authorization.
"""
import copy
import hashlib
import json
import re
import time

LEDGER_URI = 'gs://joint-inspection-510310-data/models/inspect-view/research-results/engineering-preview-control/research-usd100-ledger.json'
CYCLE = 'jointinspect-research-usd100'
CEILING = 100_000_000  # integer micro-USD; never floating point
LIFECYCLE = 'ENGINEERING_PREVIEW'
RESULT_PREFIX = 'models/inspect-view/research-results/engineering-preview-persistent/v1'
MAX_INPUT_TOKENS = 100_000
MAX_OUTPUT_TOKENS = 8192
# Conservative approved pricing envelope, not a provider billing-account cap.
INPUT_MICROUSD_PER_TOKEN = 8
OUTPUT_MICROUSD_PER_TOKEN = 64
MIN_GEMINI_RESERVATION = MAX_INPUT_TOKENS*INPUT_MICROUSD_PER_TOKEN + MAX_OUTPUT_TOKENS*OUTPUT_MICROUSD_PER_TOKEN


class PreviewBudgetDenied(ValueError):
    pass


class LedgerConflict(Exception):
    pass


def persistent(scope):
    return scope.get('lifecycle') == LIFECYCLE


def validate_policy(scope):
    if (not persistent(scope) or scope.get('mode') != 'PREVIEW'
            or scope.get('budget_ledger_uri') != LEDGER_URI or scope.get('budget_cycle') != CYCLE
            or scope.get('currency') != 'USD' or scope.get('spending_cap') != 100
            or scope.get('input_authorization') != 'IAM_AUTHENTICATED_WEBSITE_UPLOADS'
            or any(k in scope for k in ('expires_unix', 'max_requests', 'max_inspections'))
            or scope.get('max_analysis_passes') not in (1, 2)
            or not isinstance(scope.get('runtime_artifact_sha256'), str)
            or not re.fullmatch('[a-f0-9]{64}', scope['runtime_artifact_sha256'])):
        raise PreviewBudgetDenied('Invalid persistent PREVIEW policy')
    if scope.get('receipt_prefix') != RESULT_PREFIX:
        raise PreviewBudgetDenied('Private research result prefix required')


def validate_ledger(value):
    if (not isinstance(value, dict) or value.get('schema') not in (1, 2) or value.get('cycle') != CYCLE
            or value.get('currency') != 'USD' or value.get('ceiling_microusd') != CEILING
            or value.get('status') != 'ACTIVE' or not value.get('opening_approval_id')
            or not value.get('prior_accounting_evidence') or not value.get('pricing_evidence')):
        raise PreviewBudgetDenied('Budget accounting unavailable or preview paused')
    for field in ('prior_consumption_bound_microusd', 'infrastructure_reserve_microusd'):
        if type(value.get(field)) is not int or not 0 <= value[field] <= CEILING:
            raise PreviewBudgetDenied('Verified conservative opening balance required')
    for kind, minimum in [('inspection', 100_000), ('gemini', MIN_GEMINI_RESERVATION)]:
        cost = value.get('operation_reservations_microusd', {}).get(kind)
        if type(cost) is not int or not minimum <= cost <= CEILING:
            raise PreviewBudgetDenied('Conservative spending envelope required')
    claims = value.get('claims')
    if not isinstance(claims, dict):
        raise PreviewBudgetDenied('Invalid persistent accounting state')
    used = value['prior_consumption_bound_microusd']+value['infrastructure_reserve_microusd']
    for key, row in claims.items():
        if (not re.fullmatch(r'(inspection|gemini):[a-f0-9]{64}', key) or not isinstance(row, dict)
                or type(row.get('reserved_microusd')) is not int or row['reserved_microusd'] < 100_000):
            raise PreviewBudgetDenied('Invalid financial claim')
        used += row['reserved_microusd']
    if used > CEILING:
        raise PreviewBudgetDenied('Accounting integrity check failed')
    return used


def remove_daily_quotas(value):
    """Lossless financial migration: retain every reservation and its audit data."""
    before = validate_ledger(value)
    updated = copy.deepcopy(value)
    updated['schema'] = 2
    for field in ('period_seconds', 'period_limits', 'period_usage'):
        updated.pop(field, None)
    if validate_ledger(updated) != before:
        raise PreviewBudgetDenied('Migration must preserve all financial reservations')
    return updated


class GcsLedger:
    def __init__(self, bucket):
        if bucket.name != 'joint-inspection-510310-data':
            raise PreviewBudgetDenied('Private project ledger required')
        self.blob = bucket.blob(LEDGER_URI.split('/', 3)[3])

    def read(self):
        from google.api_core.exceptions import NotFound, PreconditionFailed
        try:
            self.blob.reload(timeout=10, retry=None)
            if self.blob.size is None or self.blob.size > 256*1024:
                raise PreviewBudgetDenied('Ledger exceeds accounting limit')
            generation = int(self.blob.generation)
            data = self.blob.download_as_bytes(if_generation_match=generation, timeout=10, retry=None)
            return json.loads(data), generation
        except NotFound:
            raise PreviewBudgetDenied('Budget ledger missing; never initialize or replenish automatically')
        except PreconditionFailed:
            raise LedgerConflict()

    def replace(self, value, generation):
        from google.api_core.exceptions import PreconditionFailed
        try:
            self.blob.upload_from_string(json.dumps(value, sort_keys=True, allow_nan=False),
                content_type='application/json', if_generation_match=generation, timeout=10, retry=None)
        except PreconditionFailed:
            raise LedgerConflict()


def reserve(scope, store, kind, key, *, now=None, ledger=None):
    """Exactly one claim wins across processes; a denied budget makes no write."""
    validate_policy(scope)
    if kind not in ('inspection', 'gemini') or not re.fullmatch('[a-f0-9]{64}', key):
        raise PreviewBudgetDenied('Invalid metered operation')
    ledger = ledger or GcsLedger(store.bucket)
    now = int(time.time()) if now is None else now
    if type(now) is not int or now < 0:
        raise PreviewBudgetDenied('Valid audit clock required')
    claim_key = kind+':'+key
    for _ in range(8):
        try:
            current, generation = ledger.read()
            used = validate_ledger(current)
            if claim_key in current['claims']:
                raise PreviewBudgetDenied('Previously reserved request; no automatic retry')
            cost = current['operation_reservations_microusd'][kind]
            if used+cost > CEILING:
                raise PreviewBudgetDenied('Cumulative research allowance exhausted')
            updated = remove_daily_quotas(current)
            updated['claims'][claim_key] = {'reserved_microusd': cost,
                'issued_at': now, 'scope_sha256': hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest(),
                'status': 'ENCUMBERED_NO_AUTOMATIC_REFUND'}
            ledger.replace(updated, generation)
            return
        except LedgerConflict:
            continue
    raise PreviewBudgetDenied('Accounting contention; no work started')
