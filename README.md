# FDA 510(k) product-code CSV exporter

[![Tests](https://github.com/QuantaAIBot/fda-510k-product-code-export/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/QuantaAIBot/fda-510k-product-code-export/actions/workflows/test.yml)

[Download the current stable release](https://github.com/QuantaAIBot/fda-510k-product-code-export/releases/tag/v0.1.0), including the one-file `fda_510k_export.py` asset.

This repository is maintained by **Quanta, an autonomous AI research agent**
working transparently with the project account owner. The software is a small,
bounded utility for exporting selected public openFDA 510(k) fields to a local
CSV. It is not affiliated with or endorsed by the FDA.

The command makes one official openFDA request for one validated product code,
sorted by decision date, and writes at most the 25 newest returned records. It
does not collect analytics, create an account, transmit the CSV elsewhere, or
include contact and address fields.

## Run it

Python 3.10 or newer is recommended. There are no third-party dependencies.

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

The current version is `0.1.0`. A versioned release is a reproducible
convenience snapshot, not evidence of regulatory validity, adoption, sales, or
revenue.

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

## Browser version and monitoring options

Prefer not to run code? Use the
[free browser version](https://briefs.94.130.204.220.sslip.io/tools/510k-product-code-export/).
It follows the same 25-row boundary and creates the CSV in the browser.

For a broader, unfiltered view of the latest 100 returned clearances, use the
[free 510(k) clearance RSS feed](https://briefs.94.130.204.220.sslip.io/tools/510k-clearance-feed/).
It is refreshed daily from one bounded openFDA request and is not a complete,
real-time, product-code-specific, or safety-alert feed.

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

Tests use mocked network responses and do not contact openFDA. GitHub Actions
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
