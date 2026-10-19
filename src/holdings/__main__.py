"""Read-only SEC research CLI: python -m src.holdings --help."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .sec13f import EvidenceError, SecClient, discover, document, filing_url, parse_submission, retrieve


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cik', required=True, help='Investment manager CIK, not issuer ticker')
    parser.add_argument('--accession', help='Omit to discover filings')
    parser.add_argument('--user-agent', help='Explicitly approved organization + contact email for SEC requests')
    parser.add_argument('--include-history', action='store_true')
    parser.add_argument('--fixture', type=Path, help='Parse a saved complete submission offline')
    parser.add_argument('--provenance', type=Path, help='Saved URL, SHA256, retrieved_at JSON for --fixture')
    parser.add_argument('--mappings', type=Path, help='Reviewed, date-bounded identifier mapping JSON list')
    args = parser.parse_args(argv)
    try:
        mappings = json.loads(args.mappings.read_text()) if args.mappings else []
        if not isinstance(mappings, list):
            raise EvidenceError('Mappings must be a list')
        if args.fixture:
            if not args.accession or not args.provenance:
                raise EvidenceError('Offline parse requires accession and provenance')
            metadata = json.loads(args.provenance.read_text())
            src = document(args.fixture.read_bytes(), metadata['url'],
                           datetime.fromisoformat(metadata['retrieved_at']), 'authentic_fixture'
                           if metadata.get('classification') == 'authentic_public_sec_filing' else 'synthetic_fixture')
            if src.evidence.sha256 != metadata['sha256']:
                raise EvidenceError('Fixture digest mismatch')
            result = parse_submission(src, args.cik, args.accession,
                                      as_of=datetime.now(timezone.utc), mappings=mappings)
        else:
            client = SecClient(args.user_agent or '')
            result = retrieve(client, args.cik, args.accession, mappings=mappings) if args.accession else discover(
                client, args.cik, args.include_history)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (EvidenceError, OSError, ValueError, KeyError, TypeError) as exc:
        # No empty-success or previous holdings result on failure.
        print(json.dumps({'status': 'unavailable', 'usable': False, 'reason': str(exc),
                          'holdings': None}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
