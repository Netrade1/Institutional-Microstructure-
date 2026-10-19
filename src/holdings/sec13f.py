"""SEC 13F discovery and strict modern-XML submission normalization.

No order, broker, approval, model, or L2 dependencies. A filing proves what a
manager reported, not beneficial ownership, present holdings or trader identity.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

MAX_BYTES = 32 * 1024 * 1024
FORMS = {'13F-HR', '13F-HR/A', '13F-NT', '13F-NT/A'}
LIMITATIONS = (
    'Manager-reported historical investment discretion, not independently verified ownership.',
    'Public 13F disclosure is incomplete: limited securities, omitted/confidential positions, no short book.',
    'Filings are delayed; absence of a security does not establish zero ownership.',
    'Amendments are separate evidence; no automatic consolidation or current-position inference.',
    'Neither these filings nor Level 2 patterns identify the sender of an individual market order.',
)


class EvidenceError(ValueError):
    """Unavailable, unsupported, or contradictory evidence: no usable report."""


def cik(value: str) -> str:
    if not re.fullmatch(r'\d{1,10}', str(value)) or int(value) == 0:
        raise EvidenceError('Invalid manager CIK')
    return str(value).zfill(10)


def accession(value: str) -> str:
    if not re.fullmatch(r'\d{10}-\d{2}-\d{6}', value):
        raise EvidenceError('Invalid accession')
    return value


def filing_url(manager_cik: str, acc: str) -> str:
    return (f'https://www.sec.gov/Archives/edgar/data/{int(cik(manager_cik))}/'
            f'{accession(acc).replace("-", "")}/{acc}.txt')


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EvidenceError('Timezone-aware timestamp required')
    return value.astimezone(timezone.utc)


def number(value: str, integer: bool = False) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise EvidenceError('Invalid reported number') from exc
    if not result.is_finite() or result < 0 or (integer and result != result.to_integral_value()):
        raise EvidenceError('Nonfinite, negative or nonintegral reported number')
    return result


def xml_date(value: str) -> date:
    try:
        return datetime.strptime(value, '%m-%d-%Y').date()
    except ValueError as exc:
        raise EvidenceError('Invalid XML report date') from exc


def field(root: ET.Element, path: str, optional: bool = False) -> str | None:
    nodes = root.findall(path)
    if not nodes and optional:
        return None
    if len(nodes) != 1 or not (nodes[0].text or '').strip():
        raise EvidenceError(f'Missing or ambiguous XML field: {path}')
    return nodes[0].text.strip()


def boolean(value: str) -> bool:
    if value not in {'true', 'false', '1', '0'}:
        raise EvidenceError('Invalid boolean')
    return value in {'true', '1'}


@dataclass(frozen=True)
class Evidence:
    url: str
    retrieved_at: str
    sha256: str
    byte_count: int
    origin: str  # sec_https, authentic_fixture, or synthetic_fixture


@dataclass(frozen=True)
class Document:
    data: bytes
    evidence: Evidence


def document(data: bytes, url: str, retrieved_at: datetime, origin: str) -> Document:
    if not data or len(data) > MAX_BYTES:
        raise EvidenceError('Empty or oversized source')
    if origin not in {'sec_https', 'authentic_fixture', 'synthetic_fixture'}:
        raise EvidenceError('Unknown evidence origin')
    return Document(data, Evidence(url, aware(retrieved_at).isoformat(),
                                  hashlib.sha256(data).hexdigest(), len(data), origin))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise EvidenceError('Redirect refused; use an explicit SEC source')


class SecClient:
    """Sequential GET only; process-wide 5 req/s cap; no silent retries or fallback.

    Operator must coordinate the SEC aggregate limit across other processes.
    A contact identifier is supplied explicitly, never taken from personal memory.
    """
    _lock = threading.Lock()
    _last_request = 0.0

    def __init__(self, user_agent: str):
        if not user_agent.strip() or not re.search(r'[^\s@]+@[^\s@]+\.[^\s@]+', user_agent):
            raise EvidenceError('Supply an operator-approved SEC User-Agent with contact email')
        if '\n' in user_agent or '\r' in user_agent:
            raise EvidenceError('Invalid User-Agent')
        self.user_agent = user_agent
        self._opener = urllib.request.build_opener(_NoRedirect())

    def get(self, url: str) -> Document:
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or parsed.netloc not in {'www.sec.gov', 'data.sec.gov'}
                or parsed.query or parsed.fragment or '..' in parsed.path or '%' in parsed.path
                or not (parsed.path.startswith('/Archives/edgar/data/')
                        or parsed.path.startswith('/submissions/'))):
            raise EvidenceError('Only SEC submissions and filing archive URLs are permitted')
        try:
            with self._lock:
                time.sleep(max(0, 0.2 - (time.monotonic() - SecClient._last_request)))
                SecClient._last_request = time.monotonic()
                req = urllib.request.Request(url, headers={'User-Agent': self.user_agent,
                                                         'Accept-Encoding': 'identity'})
                with self._opener.open(req, timeout=30) as response:
                    raw = response.read(MAX_BYTES + 1)
            return document(raw, url, datetime.now(timezone.utc), 'sec_https')
        except (OSError, ValueError) as exc:
            raise EvidenceError(f'SEC source unavailable: {url}: {exc}') from exc


def discover(client: SecClient, manager_cik: str, include_history: bool = False) -> dict:
    """Return available filings and source evidence; default scope is recent only."""
    manager_cik = cik(manager_cik)
    source = client.get(f'https://data.sec.gov/submissions/CIK{manager_cik}.json')
    try:
        data = json.loads(source.data)
        if cik(str(data['cik'])) != manager_cik:
            raise EvidenceError('Submissions CIK mismatch')
        pages = [(data['filings']['recent'], source.evidence)]
        history = data['filings']['files']
        if include_history:
            for item in history:
                name = item['name']
                if not re.fullmatch(r'CIK\d{10}-submissions-\d+\.json', name):
                    raise EvidenceError('Invalid historical submissions filename')
                page = client.get(f'https://data.sec.gov/submissions/{name}')
                pages.append((json.loads(page.data), page.evidence))
        records = {}
        for page, evidence in pages:
            keys = ('accessionNumber', 'form', 'filingDate', 'reportDate')
            if any(not isinstance(page[k], list) for k in keys):
                raise EvidenceError('Invalid discovery arrays')
            if len({len(page[k]) for k in keys}) != 1:
                raise EvidenceError('Misaligned discovery arrays')
            for acc, form, filed, period in zip(*(page[k] for k in keys)):
                if form not in FORMS:
                    continue
                date.fromisoformat(filed)
                date.fromisoformat(period)
                record = {'accession': accession(acc), 'form': form, 'filing_date': filed,
                          'report_period': period, 'url': filing_url(manager_cik, acc)}
                if acc in records and records[acc] != record:
                    raise EvidenceError('Contradictory discovery records')
                records[acc] = record
        return {'manager_cik': manager_cik, 'current_directory_name': data['name'],
                'scope': 'all_listed_submission_pages' if include_history else 'recent_only',
                'unfetched_history_pages': 0 if include_history else len(history),
                'filings': sorted(records.values(), key=lambda r: (r['filing_date'], r['accession'])),
                'provenance': [asdict(e) for _, e in pages], 'limitations': list(LIMITATIONS)}
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidenceError(f'Invalid submissions source: {exc}') from exc


def reconcile(cusip: str, figi: str | None, period: date, mappings: list[dict]) -> dict:
    """Only exact identifiers, date-bounded mappings with source provenance; no fuzzy names."""
    matches = []
    for mapping in mappings:
        if not ((mapping.get('cusip') == cusip) or (figi and mapping.get('figi') == figi)):
            continue
        try:
            start, end = date.fromisoformat(mapping['valid_from']), date.fromisoformat(mapping['valid_to'])
            if start > end:
                raise EvidenceError('Invalid mapping validity range')
            if not start <= period <= end:
                continue
            if not mapping['source_url'].startswith('https://') or not re.fullmatch(r'[0-9a-f]{64}', mapping['source_sha256']):
                raise EvidenceError('Mapping requires source URL and SHA256')
            aware(datetime.fromisoformat(mapping['verified_at']))
            if not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-/]{0,19}', mapping['symbol']):
                raise EvidenceError('Invalid mapped symbol')
            if mapping.get('cusip', cusip) != cusip or (figi and mapping.get('figi', figi) != figi):
                return {'status': 'conflicting_identifiers', 'symbol': None, 'evidence': []}
            matches.append(mapping)
        except (KeyError, TypeError, ValueError) as exc:
            raise EvidenceError(f'Invalid security mapping: {exc}') from exc
    symbols = {m['symbol'] for m in matches}
    if len(symbols) != 1:
        return {'status': 'ambiguous' if symbols else 'unresolved', 'symbol': None, 'evidence': matches}
    return {'status': 'matched_external_mapping', 'symbol': next(iter(symbols)), 'evidence': matches}


def parse_submission(source: Document, manager_cik: str, acc: str, *,
                     as_of: datetime, mappings: list[dict] | None = None,
                     expected: dict | None = None) -> dict:
    """All-or-nothing filing parse. Caller catches EvidenceError and must not use stale output."""
    try:
        return _parse(source, cik(manager_cik), accession(acc), aware(as_of), mappings or [], expected)
    except (ValueError, TypeError, KeyError, ET.ParseError, UnicodeError) as exc:
        raise EvidenceError(f'Invalid filing evidence: {exc}') from exc


def _parse(source, manager_cik, acc, as_of, mappings, expected):
    if source.evidence.url != filing_url(manager_cik, acc):
        raise EvidenceError('Source URL/identity mismatch')
    if hashlib.sha256(source.data).hexdigest() != source.evidence.sha256 or len(source.data) != source.evidence.byte_count:
        raise EvidenceError('Source digest mismatch')
    retrieved = aware(datetime.fromisoformat(source.evidence.retrieved_at))
    if retrieved > as_of:
        raise EvidenceError('Evidence was not retrieved by the requested as-of time')
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise EvidenceError("Security mappings must be objects")
        verified = mapping.get("verified_at")
        if verified and aware(datetime.fromisoformat(verified)) > as_of:
            raise EvidenceError("Security mapping verified after as-of time")
    text = source.data.decode('utf-8')
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise EvidenceError('DTD and entity declarations prohibited')
    headers = re.findall(r'<SEC-HEADER>(.*?)</SEC-HEADER>', text, re.S)
    if len(headers) != 1:
        raise EvidenceError('Missing SEC header')
    def header(key):
        values = re.findall(r'^\s*' + re.escape(key) + r':\s*([^\r\n]+)', headers[0], re.M)
        if len(values) != 1:
            raise EvidenceError(f'Missing or ambiguous SEC header: {key}')
        return values[0].strip()
    if header('ACCESSION NUMBER') != acc or cik(header('CENTRAL INDEX KEY')) != manager_cik:
        raise EvidenceError('SEC header identity mismatch')
    form = header('CONFORMED SUBMISSION TYPE')
    if form not in FORMS:
        raise EvidenceError('Unsupported form')
    period = datetime.strptime(header('CONFORMED PERIOD OF REPORT'), '%Y%m%d').date()
    filed = datetime.strptime(header('FILED AS OF DATE'), '%Y%m%d').date()
    accepted_values = re.findall(r'<ACCEPTANCE-DATETIME>(\d{14})', headers[0])
    if len(accepted_values) != 1:
        raise EvidenceError('Missing acceptance timestamp')
    accepted = datetime.strptime(accepted_values[0], '%Y%m%d%H%M%S').replace(tzinfo=ZoneInfo('America/New_York'))
    if accepted.astimezone(timezone.utc) > retrieved or not period <= filed <= as_of.date():
        raise EvidenceError('Future or contradictory filing timestamps')
    if expected and any(expected[k] != v for k, v in {
        'accession': acc, 'form': form, 'filing_date': filed.isoformat(), 'report_period': period.isoformat()
    }.items()):
        raise EvidenceError('Discovery and filing metadata disagree')
    docs = []
    filenames = set()
    for block in re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>', text, re.S):
        kind = re.search(r'<TYPE>([^\r\n]+)', block)
        filename = re.search(r'<FILENAME>([^\r\n]+)', block)
        if not kind or kind[1].strip() not in {form, 'INFORMATION TABLE'}:
            continue
        bodies = re.findall(r'<XML>\s*(.*?)\s*</XML>', block, re.S)
        if not filename or len(bodies) != 1 or not re.fullmatch(r'[A-Za-z0-9_.-]+', filename[1].strip()):
            raise EvidenceError('Unsupported non-XML or ambiguous document')
        if filename[1].strip() in filenames:
            raise EvidenceError("Duplicate filing document filename")
        filenames.add(filename[1].strip())
        root = ET.fromstring(bodies[0])
        for node in root.iter():
            node.tag = node.tag.split('}')[-1]
        docs.append((kind[1].strip(), filename[1].strip(), root))
    primaries = [r for t, _, r in docs if t == form]
    if len(primaries) != 1 or primaries[0].tag != 'edgarSubmission':
        raise EvidenceError('Missing or ambiguous primary document')
    root = primaries[0]
    if field(root, 'headerData/submissionType') != form or cik(field(root, 'headerData/filerInfo/filer/credentials/cik')) != manager_cik:
        raise EvidenceError('Primary XML identity mismatch')
    if any(xml_date(field(root, p)) != period for p in (
        'headerData/filerInfo/periodOfReport', 'formData/coverPage/reportCalendarOrQuarter')):
        raise EvidenceError('Reporting period mismatch')
    cover = root.find('formData/coverPage')
    name = field(cover, 'filingManager/name')
    if ' '.join(name.upper().split()) != ' '.join(header('COMPANY CONFORMED NAME').upper().split()):
        raise EvidenceError('Manager name mismatch')
    amended = boolean(field(cover, 'isAmendment'))
    if amended != form.endswith('/A'):
        raise EvidenceError('Amendment flag mismatch')
    amend_type = field(cover, 'amendmentInfo/amendmentType', True)
    amend_number = field(cover, 'amendmentNo', True)
    if amended:
        if amend_type not in {'RESTATEMENT', 'NEW HOLDINGS'} or not amend_number or number(amend_number, True) < 1:
            raise EvidenceError('Missing or unsupported amendment metadata')
    elif amend_type or amend_number:
        raise EvidenceError('Unexpected amendment metadata')
    report_type = field(cover, 'reportType')
    if report_type not in {'13F HOLDINGS REPORT', '13F COMBINATION REPORT', '13F NOTICE'}:
        raise EvidenceError('Unsupported report type')
    notice = form.startswith('13F-NT')
    if notice != (report_type == '13F NOTICE'):
        raise EvidenceError('Form/report type disagreement')
    confidential = field(root, 'formData/summaryPage/isConfidentialOmitted', True)
    confidential = boolean(confidential) if confidential is not None else None
    multiplier = 1 if filed >= date(2023, 1, 3) else 1000
    rows = []
    for kind, filename, table in docs:
        if kind != 'INFORMATION TABLE':
            continue
        if table.tag != 'informationTable':
            raise EvidenceError('Invalid information table root')
        for row in table.findall('infoTable'):
            cusip = field(row, 'cusip').upper()
            if not re.fullmatch(r'[A-Z0-9*@#]{9}', cusip):
                raise EvidenceError('Invalid CUSIP')
            figi = field(row, 'figi', True) or field(row, 'FIGI', True)
            if figi and not re.fullmatch(r'[A-Z0-9]{12}', figi):
                raise EvidenceError('Invalid FIGI')
            quantity_type = field(row, 'shrsOrPrnAmt/sshPrnamtType')
            put_call = field(row, 'putCall', True)
            if quantity_type not in {'SH', 'PRN'} or put_call not in {None, 'Put', 'Call'}:
                raise EvidenceError('Unknown quantity or option type')
            reported = number(field(row, 'value'), True)
            rows.append({'issuer_name': field(row, 'nameOfIssuer'), 'security_class': field(row, 'titleOfClass'),
                         'cusip': cusip, 'figi': figi, 'put_call': put_call,
                         'quantity': str(number(field(row, 'shrsOrPrnAmt/sshPrnamt'), True)),
                         'quantity_type': quantity_type, 'reported_value': str(reported),
                         'reported_value_unit': 'USD' if multiplier == 1 else 'USD_THOUSANDS',
                         'value_usd': str(reported * multiplier),
                         'investment_discretion': field(row, 'investmentDiscretion'),
                         'other_managers': field(row, 'otherManager', True),
                         'voting_authority': {k: str(number(field(row, 'votingAuthority/' + k), True))
                                              for k in ('Sole', 'Shared', 'None')},
                         'document_filename': filename, 'row_number': len(rows) + 1,
                         'security_match': reconcile(cusip, figi, period, mappings)})
    if notice:
        if rows or any(t == 'INFORMATION TABLE' for t, _, _ in docs):
            raise EvidenceError('Notice unexpectedly contains holdings')
    else:
        total = number(field(root, 'formData/summaryPage/tableValueTotal'), True)
        count = number(field(root, 'formData/summaryPage/tableEntryTotal'), True)
        if count != len(rows) or total != sum(Decimal(r['reported_value']) for r in rows):
            raise EvidenceError('Information table count/value totals disagree')
        if count and not any(t == 'INFORMATION TABLE' for t, _, _ in docs):
            raise EvidenceError('Information table unavailable')
    flags = ['not_a_complete_portfolio', 'amendments_not_consolidated']
    if notice:
        flags.append('notice_not_zero_holdings')
    if report_type == '13F COMBINATION REPORT':
        flags.append('other_managers_report_some_holdings')
    if confidential is not False:
        flags.append('confidential_omissions_reported' if confidential else 'confidential_omission_status_unknown')
    return {'schema_version': 'sec13f.v1', 'status': 'notice_only' if notice else 'reported_holdings',
            'evidence_kind': 'public_filing_reported_history', 'manager_cik': manager_cik,
            'manager_name': name, 'accession': acc, 'form': form, 'report_type': report_type,
            'filing_date': filed.isoformat(), 'report_period': period.isoformat(),
            'accepted_at': accepted.isoformat(), 'as_of': as_of.isoformat(),
            'report_age_days': (as_of.date() - period).days,
            'filing_age_days': (as_of.date() - filed).days,
            'disclosure_lag_days': (filed - period).days,
            'age_label': 'historical_disclosure_not_live',
            'amendment': {'is_amendment': amended, 'number': amend_number, 'type': amend_type,
                          'base_accession': None, 'consolidation_status': 'not_attempted'},
            'holdings': rows, 'coverage_flags': flags, 'limitations': list(LIMITATIONS),
            'provenance': asdict(source.evidence),
            'use_policy': {'research_only': True, 'paper_only': True, 'live_execution': False,
                           'human_approval_required': True, 'risk_governor_final_veto': True,
                           'automatic_model_promotion': False, 'order_identity_attribution': False}}


def retrieve(client: SecClient, manager_cik: str, acc: str, *, as_of: datetime | None = None,
             mappings: list[dict] | None = None, expected: dict | None = None) -> dict:
    source = client.get(filing_url(manager_cik, acc))
    return parse_submission(source, manager_cik, acc, as_of=as_of or datetime.now(timezone.utc),
                            mappings=mappings, expected=expected)
