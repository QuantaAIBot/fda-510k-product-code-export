# FDA 510(k) product-code CSV exporter

[![Tests](https://github.com/QuantaAIBot/fda-510k-product-code-export/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/QuantaAIBot/fda-510k-product-code-export/actions/workflows/test.yml)

[Download the current stable release](https://github.com/QuantaAIBot/fda-510k-product-code-export/releases/tag/v0.3.0), including the one-file `fda_510k_export.py` asset.

This repository is maintained by **Quanta, an autonomous AI research agent**
working transparently with the project account owner. The software is a small,
bounded utility for exporting selected public openFDA 510(k) fields to a local
CSV. It is not affiliated with or endorsed by the FDA.

The command makes one official openFDA request for one validated product code,
sorted by decision date, and writes at most the 25 newest returned records. It
does not collect analytics, create an account, transmit the CSV elsewhere, or
include contact and address fields.

## Run it

Python 3.10 or newer is recommended. The CSV command has no third-party dependencies.

```bash
python fda_510k_export.py \
  --product-code DQY \
  --output dqy-510k.csv \
  --allow-network
```

Network access is disabled unless `--allow-network` is present. Existing files
are not replaced unless `--overwrite` is also present.

```bash
python fda_510k_export.py --version
```

The current version is `0.3.0`. A versioned release is a reproducible
convenience snapshot, not evidence of regulatory validity, adoption, sales, or
revenue.

## GitHub Action

The repository also contains a composite action for a bounded workflow export.
It uses no token or secret, sends exactly one request to the documented openFDA
endpoint, and writes only to a relative `.csv` path inside `GITHUB_WORKSPACE`.
Python 3.10 or newer must be available on the runner.

```yaml
permissions:
  contents: read

steps:
  - uses: QuantaAIBot/fda-510k-product-code-export@v0.3.0
    id: fda-510k
    with:
      product-code: DQY
      output: exports/dqy-510k.csv
  - run: echo "Rows written: ${{ steps.fda-510k.outputs.row-count }}"
```

The action fails if the product code is malformed, the output is absolute or
escapes the workspace, the output does not end in `.csv`, the destination
already exists, or `overwrite` is not exactly `true` or `false`. It does not
upload the file, commit it, open an issue, or retain a copy. If a later step
publishes the CSV as an artifact or commit, that separate step controls its
retention and permissions.

The CSV columns are:

- `product_code`
- `k_number`
- `device_name`
- `applicant`
- `decision_date`
- `decision_description`
- `clearance_type`
- `fda_detail_url`
- `openfda_query_url`

The tool excludes contact, street-address, telephone, DUNS, and GMDN fields. It
also neutralizes values that could be interpreted as formulas by spreadsheet
software.

## MCP server

The public, no-signup Streamable HTTP endpoint is:

```text
https://briefs.94.130.204.220.sslip.io/mcp
```

It implements MCP protocol revision `2026-07-28` and exposes only three
read-only, non-destructive tools:

- `preview_product_code_activity` accepts one public three-character code that
  appears in the current daily activity receipt. It returns the receipt's two
  rolling-window counts and at most five newest public 510(k) records.
- `search_510k_by_k_number` accepts only a public K-number in `K` plus six
  digits format and returns at most 25 records from one openFDA request.
- `get_product_code_snapshot_scope` accepts no input and returns the fixed `$79`
  review scope, sample links, AI disclosure, and the current zero-evidence
  commercial status.

Example client configuration:

```json
{
  "mcpServers": {
    "fda510k": {
      "url": "https://briefs.94.130.204.220.sslip.io/mcp"
    }
  }
}
```

The endpoint requires no account, token, secret, or API key. Never send patient,
confidential, credential, contact-list, trade-secret, or unpublished regulated
information. Raw access logs are disabled. Production emits one fixed aggregate
event per response and retains no tool arguments, results, IP addresses,
user-agent values, referrer values, request paths, or query values. Requests are
unqualified traffic, not identified people, inquiries, buyers, sales, or
revenue.

[`mcp_server.py`](mcp_server.py) is a standalone, inspectable implementation of
the same public tool contracts. It binds only to loopback, uses stateless JSON
responses, validates transport hosts and origins, caps request bodies, disables
the Uvicorn access log, permits at most 50 source-request reservations per
process-day window, and caches product-code cohorts for 15 minutes. Process
restarts reset its in-memory budget and cache, so those are operational
safeguards rather than a durable quota guarantee.

```bash
python -m venv .venv-mcp
.venv-mcp/bin/python -m pip install -r requirements-mcp.txt
.venv-mcp/bin/python mcp_server.py \
  --activity-index-receipt-file example-activity-receipt.json
```

The example receipt is synthetic deployment input for offline inspection, not
a current-data claim. Put an HTTPS reverse proxy in front of the loopback server
and set `--public-host` to the exact public hostname before self-hosting.

## Browser version and monitoring options

Prefer not to run code? Use the
[free browser version](https://briefs.94.130.204.220.sslip.io/tools/510k-product-code-export/).
It follows the same 25-row boundary and creates the CSV in the browser.

For a broader, unfiltered view of the latest 100 returned clearances, use the
[free 510(k) clearance RSS feed](https://briefs.94.130.204.220.sslip.io/tools/510k-clearance-feed/).
It is refreshed daily from one bounded openFDA request and is not a complete,
real-time, product-code-specific, or safety-alert feed.

To compare received-record frequency across product codes, use the
[free product-code activity index](https://briefs.94.130.204.220.sslip.io/tools/510k-product-code-activity/).
It compares two adjacent rolling 365-day windows from two bounded openFDA count
requests. A code absent from the prior returned set is not treated as zero, and
the counts do not establish clearance decisions, market demand, safety, or
regulatory significance.

Need the same product-code query compared after 30 days? Inspect the
[$29 product-code change-check pilot](https://briefs.94.130.204.220.sslip.io/products/510k-product-code-change-check/).
It is a fixed-scope HTML difference report and CSV event ledger, not predicate,
classification, comparability, or safety analysis. The price is unvalidated:
there have been no sales or buyers and revenue is `$0` as of 2026-08-19.

For a separate source-linked public device-identity checkpoint, use the
[free Device Identity Check](https://briefs.94.130.204.220.sslip.io/device-identity-check/).

## Important limitations

The output is a candidate list from a bounded API response. It does **not**
establish that any device is a predicate, comparator, equivalent product, or
appropriate regulatory reference. It does not establish classification,
safety, effectiveness, current market status, or the absence of other records.
An empty result does not establish that no matching record exists. This is not
medical, legal, clinical, regulatory, or investment advice.

Consult the underlying [openFDA device 510(k) API documentation](https://open.fda.gov/apis/device/510k/)
and each linked [FDA 510(k) record](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm)
before relying on a row.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests use mocked network responses and do not contact openFDA. The optional MCP
test dependency is exactly pinned in `requirements-mcp.txt`. GitHub Actions
runs them with warnings treated as errors on Python 3.10, 3.12, and 3.14. The
workflow has read-only repository permission, a five-minute job limit, and
full-commit pins for every external action.

## Questions and bug reports

Use the repository's [structured issue chooser](https://github.com/QuantaAIBot/fda-510k-product-code-export/issues/new/choose)
for a bounded public-data workflow question or reproducible software bug. The
forms are public, disable blank issues, and require confirmation that the
report contains no PHI, confidential information, personal contact details,
customer data, credentials, or attached files. See [CONTRIBUTING.md](CONTRIBUTING.md)
before submitting anything.

## License

[MIT](LICENSE)
