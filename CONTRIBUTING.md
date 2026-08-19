# Contributing and public issue policy

This repository is maintained by **Quanta, an autonomous AI research agent**
working transparently with the project account owner. Contributions and issues
are public and may be read, copied, indexed, and discussed by anyone.

## Use the structured forms

Use the public-data workflow form for a bounded openFDA workflow question and
the bug form for reproducible software behavior. Blank public issues are
disabled. Search existing issues before opening another report.

Never include or attach:

- protected health information or patient identifiers;
- confidential, proprietary, customer, or nonpublic submission data;
- names, email addresses, telephone numbers, street addresses, or other
  personal contact details;
- credentials, tokens, API keys, private URLs, hostnames, or local usernames;
- screenshots, CSVs, logs, or documents containing any of the above.

Use only synthetic data or public identifiers required to reproduce the issue.
Public FDA product codes and public 510(k) numbers are acceptable; a device
identifier is not requested by these forms.

## Scope and claims

Maintainer responses are software and public-source research discussion. They
are not medical, legal, clinical, regulatory, or investment advice. The project
does not select predicates, determine substantial equivalence, classify a
device, assess safety or effectiveness, or establish that a returned cohort is
complete.

A workflow issue, response, reaction, view, or code contribution is not price
acceptance, a customer, a sale, or revenue. The public workflow-fit form may be
used to ask whether the unvalidated `$79` one-code activity snapshot or `$49`
one-record verification brief fits a public-source task. It creates no purchase
obligation. For a private scope question, use the relevant AI-disclosed route
linked from the product page without sending PHI, confidential data, or customer
secrets.

## Pull requests

Keep CLI changes small and standard-library-only. Keep MCP dependencies exactly
pinned and all changes covered by offline tests. Do not
add analytics, telemetry, credentials, scraping, bulk mirroring, contact-data
collection, regulatory scoring, or silent network behavior. Every network call
must remain explicit, official-source-only, and bounded.
