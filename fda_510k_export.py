#!/usr/bin/env python3
"""Export a bounded, minimized openFDA 510(k) product-code cohort to CSV."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OPENFDA_510K_ENDPOINT = "https://api.fda.gov/device/510k.json"
FDA_DETAIL_ENDPOINT = (
    "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm"
)
USER_AGENT = (
    "Quanta-AI-Research-Agent-FDA510kExport/1.0 "
    "(+https://github.com/QuantaAIBot/fda-510k-product-code-export)"
)
MAX_RECORDS = 25
TIMEOUT_SECONDS = 15
__version__ = "0.1.0"
PRODUCT_CODE_PATTERN = re.compile(r"[A-Z0-9]{3}")
K_NUMBER_PATTERN = re.compile(r"K\d{6}", re.IGNORECASE)
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
FORMULA_PREFIXES = ("=", "+", "-", "@")
CSV_FIELDS = (
    "product_code",
    "k_number",
    "device_name",
    "applicant",
    "decision_date",
    "decision_description",
    "clearance_type",
    "fda_detail_url",
    "openfda_query_url",
)


def validate_product_code(value: str) -> str:
    """Return a normalized three-character public FDA product code."""
    code = value.strip().upper()
    if not PRODUCT_CODE_PATTERN.fullmatch(code):
        raise ValueError("product code must contain exactly three letters or digits")
    return code


def build_query_url(product_code: str) -> str:
    """Build the single, bounded official openFDA query URL."""
    code = validate_product_code(product_code)
    params = urlencode(
        {
            "search": f"product_code:{code}",
            "sort": "decision_date:desc",
            "limit": MAX_RECORDS,
        }
    )
    return f"{OPENFDA_510K_ENDPOINT}?{params}"


def _plain(value: Any) -> str:
    if value is None:
        return ""
    return CONTROL_CHARACTERS.sub("", str(value)).strip()


def _spreadsheet_safe(value: str) -> str:
    stripped = value.lstrip()
    if stripped.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def normalize_records(
    payload: dict[str, Any], product_code: str, query_url: str
) -> list[dict[str, str]]:
    """Select the documented non-contact fields and cap the returned rows."""
    code = validate_product_code(product_code)
    raw_results = payload.get("results", [])
    if not isinstance(raw_results, list):
        return []

    records: list[dict[str, str]] = []
    for raw_record in raw_results[:MAX_RECORDS]:
        if not isinstance(raw_record, dict):
            continue
        k_number = _plain(raw_record.get("k_number")).upper()
        detail_url = ""
        if K_NUMBER_PATTERN.fullmatch(k_number):
            detail_url = f"{FDA_DETAIL_ENDPOINT}?ID={k_number}"

        record = {
            "product_code": code,
            "k_number": k_number,
            "device_name": _plain(raw_record.get("device_name")),
            "applicant": _plain(raw_record.get("applicant")),
            "decision_date": _plain(raw_record.get("decision_date")),
            "decision_description": _plain(
                raw_record.get("decision_description")
            ),
            "clearance_type": _plain(raw_record.get("clearance_type")),
            "fda_detail_url": detail_url,
            "openfda_query_url": query_url,
        }
        records.append({key: _spreadsheet_safe(value) for key, value in record.items()})
    return records


def fetch_records(
    product_code: str,
    *,
    allow_network: bool,
    opener=urlopen,
) -> tuple[list[dict[str, str]], str]:
    """Make one official request when the operator explicitly enables network."""
    if not allow_network:
        raise RuntimeError("network disabled; pass --allow-network to query openFDA")

    code = validate_product_code(product_code)
    query_url = build_query_url(code)
    request = Request(
        query_url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            if exc.code == 404:
                return [], query_url
            raise RuntimeError(f"openFDA returned HTTP {exc.code}") from exc
        finally:
            exc.close()
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("openFDA response was unavailable or invalid") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("openFDA response was not a JSON object")
    return normalize_records(payload, code, query_url), query_url


def write_csv(
    records: list[dict[str, str]], output_path: Path, *, overwrite: bool = False
) -> None:
    """Write a local UTF-8 CSV atomically and refuse accidental replacement."""
    destination = output_path.expanduser().resolve()
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"output already exists: {destination}; pass --overwrite to replace it"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8-sig",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        os.replace(temporary_name, destination)
    except Exception:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export at most 25 newest returned openFDA 510(k) rows for one "
            "three-character product code."
        )
    )
    parser.add_argument("--product-code", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--version", action="version", version=f"fda_510k_export {__version__}"
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="permit the single official openFDA request",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the output file if it already exists",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        records, query_url = fetch_records(
            args.product_code, allow_network=args.allow_network
        )
        write_csv(records, args.output, overwrite=args.overwrite)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}")
        return 2

    print(f"wrote {len(records)} row(s) to {args.output.resolve()}")
    print(f"source: {query_url}")
    print("candidate rows only; no predicate, comparability, or regulatory conclusion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
