# FDA 510(k) product-code CSV exporter

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

## Browser version and next step

Prefer not to run code? Use the
[free browser version](https://briefs.94.130.204.220.sslip.io/tools/510k-product-code-export/).
It follows the same 25-row boundary and creates the CSV in the browser.

For a source-linked public device-identity checkpoint, use the
[free Device Identity Check](https://briefs.94.130.204.220.sslip.io/device-identity-check/).
That page describes an introductory `$149` source-checked identity-report
hypothesis. The price is unvalidated: there have been no sales and revenue is
`$0` as of 2026-08-18.

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

Tests use mocked network responses and do not contact openFDA.

## License

[MIT](LICENSE)
