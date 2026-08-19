# Security and privacy

This tool sends only the validated three-character product code to the official
openFDA API. It has no analytics, telemetry, account, cookie, or remote storage.
The resulting CSV is written only to the path selected by the operator.

Do not enter protected health information, customer information, confidential
information, or personal data. Product codes are public classification
identifiers, not patient or customer identifiers.

The exporter deliberately excludes source contact names, addresses, telephone
numbers, DUNS identifiers, and other fields that are unnecessary for the stated
task. Cells beginning with spreadsheet-formula trigger characters are prefixed
with an apostrophe before export.

To report a security issue, open a GitHub issue containing only non-sensitive
reproduction details. Do not post secrets or personal data.
