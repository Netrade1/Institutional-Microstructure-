# SEC Form 13F holdings research

This interface answers **what an identifiable investment manager publicly reported for a historical reporting period**. It does not independently verify ownership, identify beneficial owners, distinguish every underlying fund, reveal current holdings, or identify who placed an intraday order. Level 2 classifications remain separate heuristic behavioral research. Neither source establishes trading intent or an economic edge.

## Run

The adapter and CLI use Python 3.10+ standard library only (IANA timezone data must be available; Windows users may need `tzdata`). Full project tests additionally require the dependencies used by the existing project.

```bash
# Offline: authentic saved filing; no network or account credentials needed.
python -m src.holdings --cik 1397076 --accession 0001104659-23-116968 --fixture tests/fixtures/sec13f/authentic.txt --provenance tests/fixtures/sec13f/authentic.provenance.json

# Online: replace placeholder with your organization and approved SEC contact.
python -m src.holdings --cik 1397076 --user-agent 'YOUR_ORGANIZATION YOUR_APPROVED_CONTACT_EMAIL'
# Add --include-history to retrieve every historical page listed by the submissions API.
python -m src.holdings --cik 1397076 --accession 0001104659-23-116968 --user-agent 'YOUR_ORGANIZATION YOUR_APPROVED_CONTACT_EMAIL'
```

Discovery uses the investment **manager's CIK**, not the issuer CIK or ticker. Default discovery is recent-only, explicitly reports unfetched history pages, and does not claim latest complete ownership. `--include-history` traverses the listed submissions pages; a failed page fails the entire request rather than silently returning a complete-looking subset. Direct retrieval fetches the complete accession text and extracts its primary XML and information tables.

Success emits JSON on stdout. Failure emits `status=unavailable`, `usable=false`, and `holdings=null` on stderr and exits 2. Do not reuse an old result as if it were fresh after a failure. No background polling, broker connections, account changes, orders, fills or model promotion occur. SEC GET requests use a process-wide cap of five requests/second, 30-second timeout, 32 MiB response cap, explicit contact-bearing User-Agent, TLS, and no redirects. Coordinate rate limits across other processes and machines. HTTP restrictions require operator investigation; do not bypass them.

## Evidence and normalization

Each filing retains accession, CIK, contemporaneous manager name, filing date, reporting period, acceptance timestamp, retrieval timestamp, source URL, SHA256 and byte count. SEC acceptance timestamps are interpreted in America/New_York and exported with an offset. As-of parsing refuses evidence retrieved later than the requested time. This is not a point-in-time backtest dataset: a newly downloaded old filing was not locally available in the past.

Each security row retains issuer, class, CUSIP, optional FIGI, share/principal amount and type, Put/Call, investment discretion, other managers, voting authority, original reported value, unit and dollar-normalized value. Rows are not merged by CUSIP: classes, options and discretion can differ. Financial quantities are decimal strings, avoiding float rounding. Filing date determines the January 3, 2023 dollar-unit transition, including late amendments to older periods. Earlier values are multiplied by 1,000.

The parser checks primary/header identity, report dates, amendment flags, and exact entry/value totals. Missing, nonfinite, negative, malformed or contradictory fields reject the whole filing. Strict matching may reject legitimate name variations or rounding inconsistencies; such sources require review, never silent repair. Pre-XML filings and unsupported structures fail closed. This is a supported-field validator, not a full SEC XSD validator.

`report_age_days`, `filing_age_days` and `disclosure_lag_days` are evaluated against explicit `as_of`. Every result says `historical_disclosure_not_live`; age does not turn a filing into a live signal. A current submissions-directory name is not substituted for the original manager name.

## Amendments and disclosure coverage

Original reports, restatements and new-holdings amendments remain separate accessions. Amendment number/type are normalized, but base accession is unresolved and consolidation is deliberately **not attempted**. Do not add a restatement to its original or treat a new-holdings amendment as the whole portfolio. Discover and review the complete amendment history before any later consolidation.

13F notices are `notice_only`, never proof of zero holdings. Combination reports explicitly flag other-manager reporting. Confidential-omission flags are preserved; an absent flag is **unknown**, not false. All reports carry `not_a_complete_portfolio`. Short positions, non-reportable securities and confidential/omitted positions prevent complete exposure estimates. Reported securities are not evidence of purchases made on the filing date. Managers may report investment discretion across multiple underlying accounts or funds.

## Security reconciliation

CUSIP/FIGI are kept as reported; there is no issuer-name guessing, ticker scraping or implicit CIK-to-CUSIP mapping. Optional `--mappings mappings.json` takes a reviewed list:

```json
[{
  "cusip": "28253R105",
  "symbol": "YOUR_VERIFIED_SYMBOL",
  "valid_from": "2023-01-01",
  "valid_to": "2023-12-31",
  "source_url": "https://your-authorized-source.example/security-master",
  "source_sha256": "REPLACE_WITH_64_LOWERCASE_HEX_CHARACTERS",
  "verified_at": "2023-11-01T12:00:00+00:00"
}]
```

This is an illustrative template, not valid mapping evidence. Replace all placeholders. Mappings must match exact identifiers, cover the reporting period and carry provenance. Status is `matched_external_mapping`, `unresolved`, `ambiguous` or `conflicting_identifiers`; unresolved/conflicting symbols stay null. Invalid mapping evidence fails parsing. A mapping supplied by an operator is not independently authenticated by this adapter; its source must be reviewed before use. No production security master is bundled. The tests' `TEST` mapping is fabricated and marked as such.

## Review and repeatable validation

1. Discover manager accessions, recording scope and provenance; identify notices and amendments.
2. Retrieve the complete source and retain raw bytes plus the SHA256/retrieval-time manifest when building a fixture. Label synthetic transformations explicitly.
3. Run offline parsing; check CIK, period, unit, count and totals against the actual primary document and table. Never edit authentic bytes to make a test pass.
4. Review mappings and coverage limitations separately. Keep holdings out of order identity and voting logic.
5. Run `python -m pytest -q` in a project test environment before publishing changes. Examine the failure contract as well as successful rows.

No schema, corporate-action mapping or amendment-consolidation changes should be accepted solely because the existing single authentic fixture passes. Add representative authentic evidence and adversarial fixtures for the changed cases.

## Official references checked October 19, 2026

- [SEC 13F FAQ](https://www.sec.gov/rules-regulations/staff-guidance/frequently-asked-questions-about-form-13f): scope, limitations, amendments and unit changes.
- [SEC Form 13F](https://www.sec.gov/about/forms/form13f.pdf): generally 45-day filing deadline; historical reporting scope.
- [EDGAR Release 22.4.1](https://www.sec.gov/filergroup/announcements-old/edgar-release-2241): January 3, 2023 value-unit transition.
- [SEC data access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data): request identification and fair access.
- [SEC submissions API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces): recent and historical filing pages.
- [Authentic filing index](https://www.sec.gov/Archives/edgar/data/1397076/000110465923116968/0001104659-23-116968-index.htm).
