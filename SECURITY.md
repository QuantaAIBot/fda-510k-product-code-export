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

The optional MCP server accepts only a public product code, a public K-number,
or no input. It binds to loopback and is intended to sit behind an HTTPS reverse
proxy. Its Uvicorn access log is disabled; its fixed event excludes arguments,
results, client addresses, user-agent values, referrer values, paths, and query
values. Do not weaken the host/origin checks, body cap, source budget, cache
boundary, or public-field allowlist.
