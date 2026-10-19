"""Offline deterministic tests; mutations of the real source are explicitly synthetic."""
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.holdings.sec13f import (
    Document, EvidenceError, SecClient, discover, document, filing_url,
    parse_submission, reconcile, retrieve,
)

FIXTURES = Path(__file__).parent / 'fixtures' / 'sec13f'
RAW = (FIXTURES / 'authentic.txt').read_bytes()
META = json.loads((FIXTURES / 'authentic.provenance.json').read_text())
AS_OF = datetime(2026, 10, 20, tzinfo=timezone.utc)
RETRIEVED = datetime.fromisoformat(META['retrieved_at'])
CIK, ACC = '1397076', '0001104659-23-116968'


def source(raw=RAW):
    return document(raw, META['url'], RETRIEVED,
                    'authentic_fixture' if raw == RAW else 'synthetic_fixture')


def parse(raw=RAW, **kwargs):
    return parse_submission(source(raw), CIK, ACC, as_of=AS_OF, **kwargs)


def mutate(old, new):
    assert old.encode() in RAW
    return RAW.replace(old.encode(), new.encode())


def test_authentic_public_filing():
    assert hashlib.sha256(RAW).hexdigest() == META['sha256']
    result = parse()
    assert result['manager_name'] == 'Stilwell Value LLC'
    assert result['manager_cik'] == '0001397076'
    assert result['report_period'] == '2023-09-30'
    assert result['filing_date'] == '2023-11-13'
    assert result['disclosure_lag_days'] == 44
    assert result['report_age_days'] == 1116
    assert result['filing_age_days'] == 1072
    assert len(result['holdings']) == 39
    assert sum(int(r['value_usd']) for r in result['holdings']) == 183087736
    row = result['holdings'][0]
    assert (row['cusip'], row['quantity'], row['value_usd']) == ('28253R105', '50000', '352750')
    assert row['security_match']['symbol'] is None
    assert result['provenance']['origin'] == 'authentic_fixture'
    assert result['use_policy']['live_execution'] is False
    assert result['use_policy']['human_approval_required'] is True


@pytest.mark.parametrize('old,new', [
    ('<value>352750</value>', '<value>NaN</value>'),
    ('<value>352750</value>', '<value>Infinity</value>'),
    ('<value>352750</value>', '<value>-1</value>'),
    ('<value>352750</value>', '<value>1.5</value>'),
    ('<value>352750</value>', '<value>352751</value>'),
    ('<tableEntryTotal>39', '<tableEntryTotal>38'),
    ('<sshPrnamt>50000', '<sshPrnamt>-50000'),
    ('<sshPrnamt>50000', '<sshPrnamt>1.5'),
    ('<cusip>28253R105', '<cusip>INVALID'),
    ('<sshPrnamtType>SH', '<sshPrnamtType>UNKNOWN'),
    ('<isAmendment>false', '<isAmendment>true'),
    ('<isAmendment>false', '<isAmendment>maybe'),
    ('<cik>0001397076', '<cik>0000000001'),
    ('<name>Stilwell Value LLC</name>', '<name>Other LLC</name>'),
    ('<reportCalendarOrQuarter>09-30-2023', '<reportCalendarOrQuarter>06-30-2023'),
    ('<reportType>13F HOLDINGS REPORT', '<reportType>13F NOTICE'),
    ('<submissionType>13F-HR', '<submissionType>13F-NT'),
    ('<nameOfIssuer>1895 BANCORP OF WIS INC</nameOfIssuer>', ''),
    ('<value>352750</value>', '<value>352750</value><value>352750</value>'),
    ('<informationTable ', '<!DOCTYPE x [<!ENTITY x "y">]><informationTable '),
])
def test_contradictory_or_malformed_filings_fail_closed(old, new):
    with pytest.raises(EvidenceError):
        parse(mutate(old, new))


def test_missing_table_never_means_zero():
    raw = re.sub(rb'<DOCUMENT>\s*<TYPE>INFORMATION TABLE.*?</DOCUMENT>', b'', RAW, flags=re.S)
    with pytest.raises(EvidenceError):
        parse(raw)


def test_digest_url_and_time_gates():
    doc = source()
    for bad in [replace(doc, data=RAW + b' '),
                replace(doc, evidence=replace(doc.evidence, url='https://example.com'))]:
        with pytest.raises(EvidenceError):
            parse_submission(bad, CIK, ACC, as_of=AS_OF)
    for when in [datetime(2020, 1, 1, tzinfo=timezone.utc), datetime(2026, 10, 20)]:
        with pytest.raises(EvidenceError):
            parse_submission(doc, CIK, ACC, as_of=when)
    with pytest.raises(EvidenceError):
        parse_submission(doc, '123', ACC, as_of=AS_OF)


@pytest.mark.parametrize('kind', ['RESTATEMENT', 'NEW HOLDINGS'])
def test_amendment_retained_without_consolidation(kind):
    raw = RAW.replace(b'13F-HR', b'13F-HR/A').replace(b'<isAmendment>false</isAmendment>',
        f'<isAmendment>true</isAmendment><amendmentNo>1</amendmentNo><amendmentInfo><amendmentType>{kind}</amendmentType></amendmentInfo>'.encode())
    result = parse(raw)
    assert result['amendment']['type'] == kind
    assert result['amendment']['base_accession'] is None
    assert result['amendment']['consolidation_status'] == 'not_attempted'
    assert result['provenance']['origin'] == 'synthetic_fixture'


def test_legacy_value_units_depend_on_filing_date():
    raw = RAW.replace(b'2023', b'2022')
    result = parse(raw)
    assert result['holdings'][0]['value_usd'] == '352750000'
    assert result['holdings'][0]['reported_value_unit'] == 'USD_THOUSANDS'
    # A post-transition filing for an older period still reports dollars.
    raw = RAW.replace(b'20230930', b'20220930').replace(b'09-30-2023', b'09-30-2022')
    assert parse(raw)['holdings'][0]['value_usd'] == '352750'


def test_notice_is_not_zero_holdings():
    raw = re.sub(rb'<DOCUMENT>\s*<TYPE>INFORMATION TABLE.*?</DOCUMENT>', b'', RAW, flags=re.S)
    raw = raw.replace(b'13F-HR', b'13F-NT').replace(b'13F HOLDINGS REPORT', b'13F NOTICE')
    raw = re.sub(rb'<summaryPage>.*?</summaryPage>', b'', raw, flags=re.S)
    result = parse(raw)
    assert result['status'] == 'notice_only'
    assert 'notice_not_zero_holdings' in result['coverage_flags']


def test_options_principal_combination_confidential():
    raw = RAW.replace(b'<cusip>28253R105</cusip>', b'<cusip>28253R105</cusip><putCall>Put</putCall>')
    raw = raw.replace(b'<sshPrnamtType>SH', b'<sshPrnamtType>PRN')
    raw = raw.replace(b'13F HOLDINGS REPORT', b'13F COMBINATION REPORT')
    raw = raw.replace(b'<summaryPage>', b'<summaryPage><isConfidentialOmitted>true</isConfidentialOmitted>')
    result = parse(raw)
    assert result['holdings'][0]['put_call'] == 'Put'
    assert result['holdings'][0]['quantity_type'] == 'PRN'
    assert 'confidential_omissions_reported' in result['coverage_flags']
    assert 'other_managers_report_some_holdings' in result['coverage_flags']


def mapping(symbol='TEST'):
    return {'cusip': '28253R105', 'symbol': symbol, 'valid_from': '2023-01-01',
            'valid_to': '2023-12-31', 'source_url': 'https://example.org/test-mapping',
            'source_sha256': 'a' * 64, 'verified_at': '2023-11-01T12:00:00+00:00'}


def test_exact_identifier_reconciliation_with_provenance():
    result = parse(mappings=[mapping()])
    assert result['holdings'][0]['security_match']['symbol'] == 'TEST'
    assert result['holdings'][1]['security_match']['symbol'] is None
    assert parse(mappings=[mapping(), mapping('OTHER')])['holdings'][0]['security_match']['status'] == 'ambiguous'
    old = mapping(); old['valid_to'] = '2023-01-02'
    assert parse(mappings=[old])['holdings'][0]['security_match']['status'] == 'unresolved'
    bad = mapping(); del bad['source_sha256']
    with pytest.raises(EvidenceError):
        parse(mappings=[bad])
    conflicting = mapping(); conflicting['figi'] = 'WRONG'
    result = reconcile('28253R105', 'BBG000000001', datetime(2023, 9, 30).date(), [conflicting])
    assert result['status'] == 'conflicting_identifiers'


def discovery_page():
    return {'accessionNumber': [ACC], 'form': ['13F-HR'], 'filingDate': ['2023-11-13'], 'reportDate': ['2023-09-30']}


def discovery_client(page=None, history=None):
    data = {'cik': 1397076, 'name': 'Stilwell Value LLC',
            'filings': {'recent': page or discovery_page(), 'files': history or []}}
    client = Mock()
    client.get.return_value = document(json.dumps(data).encode(),
        'https://data.sec.gov/submissions/CIK0001397076.json', RETRIEVED, 'synthetic_fixture')
    return client


def test_discovery_scope_and_retrieval_contract():
    result = discover(discovery_client(history=[{'name': 'CIK0001397076-submissions-001.json'}]), CIK)
    assert result['scope'] == 'recent_only'
    assert result['unfetched_history_pages'] == 1
    client = Mock(); client.get.return_value = source()
    parsed = retrieve(client, CIK, ACC, as_of=AS_OF, expected=result['filings'][0])
    assert len(parsed['holdings']) == 39
    bad = dict(result['filings'][0], report_period='2023-06-30')
    with pytest.raises(EvidenceError):
        retrieve(client, CIK, ACC, as_of=AS_OF, expected=bad)


def test_discovery_history_dedup_and_contradictions():
    client = discovery_client(history=[{'name': 'CIK0001397076-submissions-001.json'}])
    first = client.get.return_value
    page = document(json.dumps(discovery_page()).encode(),
        'https://data.sec.gov/submissions/CIK0001397076-submissions-001.json', RETRIEVED, 'synthetic_fixture')
    client.get.side_effect = [first, page]
    assert len(discover(client, CIK, True)['filings']) == 1
    bad = discovery_page(); bad['form'] = ['13F-HR/A']
    client.get.side_effect = [first, document(json.dumps(bad).encode(), page.evidence.url, RETRIEVED, 'synthetic_fixture')]
    with pytest.raises(EvidenceError):
        discover(client, CIK, True)
    bad = discovery_page(); bad['reportDate'] = []
    with pytest.raises(EvidenceError):
        discover(discovery_client(page=bad), CIK)


@pytest.mark.parametrize('url', ['http://www.sec.gov/Archives/edgar/data/a',
    'https://evil.com/Archives/edgar/data/a', 'https://www.sec.gov@evil.com/submissions/a',
    'https://www.sec.gov/Archives/edgar/data/../a', 'https://www.sec.gov:443/submissions/a'])
def test_transport_rejects_non_sec_sources_without_request(url):
    client = SecClient('Test research operator@example.org')
    client._opener = Mock()
    with pytest.raises(EvidenceError):
        client.get(url)
    client._opener.open.assert_not_called()


def test_transport_outage_returns_no_evidence():
    client = SecClient('Test research operator@example.org')
    client._opener = Mock(); client._opener.open.side_effect = OSError('403 forbidden')
    with pytest.raises(EvidenceError):
        retrieve(client, CIK, ACC)


def test_offline_cli_and_failure_exit():
    from src.holdings.__main__ import main
    assert main(['--cik', CIK, '--accession', ACC, '--fixture', str(FIXTURES/'authentic.txt'),
                 '--provenance', str(FIXTURES/'authentic.provenance.json')]) == 0
    assert main(['--cik', CIK]) == 2


def test_live_configuration_fails_closed():
    env = dict(os.environ, EXECUTION_MODE='live')
    result = subprocess.run([sys.executable, '-c', 'import src.config'], env=env, capture_output=True)
    assert result.returncode != 0
    assert b'paper-only' in result.stderr


def test_holdings_never_import_trading_pipeline():
    import ast
    imports = []
    for path in Path('src/holdings').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom): imports.append(node.module or '')
            if isinstance(node, ast.Import): imports.extend(n.name for n in node.names)
    assert not any(name.startswith(('src.agents', 'src.orchestrator', 'alpaca', 'src.features')) for name in imports)
