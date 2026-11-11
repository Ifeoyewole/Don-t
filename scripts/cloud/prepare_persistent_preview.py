"""Prepare reviewable files only. No upload, billing request or model execution."""
import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from pathlib import Path

from scripts.cloud.preview_spending import CEILING, CYCLE, LEDGER_URI, validate_ledger
from backend.app.core.cv.ai.research_gemini_reconciliation import contract_sha


def money(text):
    try:
        number = Decimal(text)
        micros = number*1_000_000
        if not number.is_finite() or number < 0 or micros != micros.to_integral_value() or micros > CEILING:
            raise ValueError('USD amount must be finite, nonnegative and within100')
        return int(micros)
    except InvalidOperation:
        raise ValueError('Invalid USD amount')


def prepare(*, prior_usd, evidence, approval, output, image_digest, infrastructure_usd='5'):
    if not approval.strip() or not evidence.strip():
        raise ValueError('Explicit accounting evidence and approval required')
    if not re.fullmatch('sha256:[a-f0-9]{64}', image_digest):
        raise ValueError('Immutable runtime image digest required')
    prior, infra = money(prior_usd), money(infrastructure_usd)
    if prior+infra > CEILING:
        raise ValueError('Opening encumbrance exceeds remaining financial authorization')
    scope = {'lifecycle': 'ENGINEERING_PREVIEW', 'mode': 'PREVIEW',
        'model': 'gemini-3.1-pro-preview', 'location': 'global',
        'review_approval_id': approval, 'spending_approval_id': approval,
        'input_authorization': 'IAM_AUTHENTICATED_WEBSITE_UPLOADS',
        'budget_cycle': CYCLE, 'budget_ledger_uri': LEDGER_URI,
        'runtime_artifact_sha256': image_digest.split(':')[1],
        'currency': 'USD', 'spending_cap': 100, 'max_analysis_passes': 2,
        'prompt_sha256': contract_sha(),
        'receipt_prefix': 'models/inspect-view/research-results/engineering-preview-persistent/v1'}
    ledger = {'schema': 2, 'cycle': CYCLE, 'currency': 'USD', 'status': 'ACTIVE',
        'ceiling_microusd': CEILING, 'opening_approval_id': approval,
        'prior_consumption_bound_microusd': prior, 'prior_accounting_evidence': evidence,
        'infrastructure_reserve_microusd': infra,
        'pricing_evidence': 'https://cloud.google.com/vertex-ai/generative-ai/pricing; Gemini3.1Pro global <=200k input USD2/M input, USD12/M output; conservative envelope USD8/M input, USD64/M output; runtime countTokens <=100k and maxOutputTokens8192',
        'operation_reservations_microusd': {'inspection': 1_000_000, 'gemini': 2_000_000},
        'claims': {}}
    validate_ledger(ledger)
    output = Path(output);output.mkdir(parents=True, exist_ok=True)
    for name, value in [('scope', scope), ('opening-ledger', ledger)]:
        data=json.dumps(value, sort_keys=True, indent=2).encode()
        (output/(name+'.json')).write_bytes(data)
        (output/(name+'.sha256')).write_text(hashlib.sha256(data).hexdigest()+'\n')
    return scope, ledger


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior-usd', required=True, help='Confirmed upper bound including all previous used/reserved cycle funds')
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--approval', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--image-digest', required=True)
    parser.add_argument('--infrastructure-usd', default='5')
    args=parser.parse_args()
    prepare(prior_usd=args.prior_usd, evidence=args.evidence, approval=args.approval,
            output=args.output, image_digest=args.image_digest, infrastructure_usd=args.infrastructure_usd)
