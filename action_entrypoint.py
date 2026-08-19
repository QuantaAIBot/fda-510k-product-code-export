#!/usr/bin/env python3
"""Fail-closed GitHub Action adapter for the bounded openFDA CSV exporter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Mapping

import fda_510k_export as exporter


TRUE_VALUES = {"true"}
FALSE_VALUES = {"false"}


def parse_boolean(value: str, name: str) -> bool:
    """Parse an action boolean without accepting ambiguous truthy values."""
    normalized = value.lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be exactly true or false")


def resolve_workspace_output(workspace: Path, value: str) -> Path:
    """Resolve one CSV path strictly below the GitHub workspace."""
    if not value or any(ord(character) < 32 for character in value):
        raise ValueError("output must be a non-empty single-line relative path")
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("output must be relative to GITHUB_WORKSPACE")

    root = workspace.expanduser().resolve()
    destination = (root / relative).resolve()
    if root not in destination.parents:
        raise ValueError("output must stay inside GITHUB_WORKSPACE")
    if destination.suffix.lower() != ".csv":
        raise ValueError("output must use a .csv extension")
    return destination


def append_github_output(path: Path, key: str, value: str | int) -> None:
    """Append one line-safe action output to GitHub's runner-managed file."""
    rendered = str(value)
    if any(character in rendered for character in ("\r", "\n")):
        raise ValueError(f"GitHub output {key} must fit on one line")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{key}={rendered}\n")


def run_action(
    environment: Mapping[str, str],
    *,
    fetcher: Callable[..., tuple[list[dict[str, str]], str]] = exporter.fetch_records,
) -> dict[str, object]:
    """Run the bounded export and return a minimized operational receipt."""
    product_code = environment.get("FDA_510K_PRODUCT_CODE", "")
    output_value = environment.get("FDA_510K_OUTPUT", "fda-510k.csv")
    overwrite_value = environment.get("FDA_510K_OVERWRITE", "false")
    workspace_value = environment.get("GITHUB_WORKSPACE", "")
    github_output_value = environment.get("GITHUB_OUTPUT", "")

    if not workspace_value:
        raise ValueError("GITHUB_WORKSPACE is required")
    if not github_output_value:
        raise ValueError("GITHUB_OUTPUT is required")

    code = exporter.validate_product_code(product_code)
    overwrite = parse_boolean(overwrite_value, "overwrite")
    destination = resolve_workspace_output(Path(workspace_value), output_value)
    records, query_url = fetcher(code, allow_network=True)
    exporter.write_csv(records, destination, overwrite=overwrite)

    github_output = Path(github_output_value).expanduser().resolve()
    append_github_output(github_output, "csv-path", destination)
    append_github_output(github_output, "row-count", len(records))

    return {
        "product_code": code,
        "csv_path": str(destination),
        "row_count": len(records),
        "query_url": query_url,
        "source_requests": 1,
    }


def main() -> int:
    try:
        receipt = run_action(os.environ)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}")
        return 2

    print(f"wrote {receipt['row_count']} row(s) to {receipt['csv_path']}")
    print(f"source: {receipt['query_url']}")
    print("candidate rows only; no predicate, comparability, or regulatory conclusion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
