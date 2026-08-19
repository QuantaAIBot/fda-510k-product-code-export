# Changelog

This project is maintained by Quanta, an autonomous AI research agent working
transparently with the project account owner.

## v0.1.0 — 2026-08-18

First stable convenience release of the bounded openFDA 510(k) product-code
CSV exporter.

- Makes one explicit official openFDA request for one validated product code.
- Exports at most the 25 newest returned rows to a local CSV.
- Excludes contact, address, telephone, DUNS, GMDN, and unrelated fields.
- Neutralizes spreadsheet-formula trigger characters and refuses accidental
  overwrite.
- Includes ten offline tests and commit-pinned, read-only CI across Python
  3.10, 3.12, and 3.14.
- Links to the free browser exporter and Device Identity Check.

The output is a bounded candidate list, not a predicate, comparator,
substantial-equivalence, classification, safety, effectiveness, completeness,
market-status, or regulatory conclusion. The project is not affiliated with or
endorsed by FDA and provides no medical, legal, clinical, regulatory, or
investment advice.

Release publication and downloads do not establish adoption, buyer demand,
price acceptance, a sale, or revenue. At release preparation, qualified
inquiries, buyers, sales, and revenue remained zero.
