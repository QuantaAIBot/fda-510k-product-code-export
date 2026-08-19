#!/usr/bin/env python3
"""Standalone reference server for Quanta's bounded public FDA 510(k) MCP tools."""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import anyio
import uvicorn
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations


__version__ = "0.3.0"
OPENFDA_510K_ENDPOINT = "https://api.fda.gov/device/510k.json"
DEFAULT_PUBLIC_HOST = "briefs.94.130.204.220.sslip.io"
DEFAULT_RECEIPT = "/var/lib/quelle-510k-product-code-activity/current.json"
MCP_PATH = "/mcp"
MAX_BODY_BYTES = 16_384
MAX_SOURCE_RESPONSE_BYTES = 2_000_000
MAX_RECEIPT_BYTES = 2_000_000
MAX_SOURCE_REQUESTS_PER_PROCESS_DAY = 50
MINIMUM_SOURCE_INTERVAL_SECONDS = 2.0
CACHE_TTL_SECONDS = 900.0
PRODUCT_CODE_PATTERN = re.compile(r"[A-Za-z0-9]{3}")
K_NUMBER_PATTERN = re.compile(r"K\d{6}", re.IGNORECASE)
PUBLIC_RECORD_FIELDS = (
    "k_number",
    "device_name",
    "applicant",
    "product_code",
    "decision_date",
    "decision_description",
    "clearance_type",
    "detail_url",
)
AI_DISCLOSURE = (
    "Quanta is an autonomous AI research agent working transparently with the "
    "account owner. Outputs require qualified human review."
)
CLAIM_BOUNDARY = (
    "Public-source retrieval only. This does not establish device identity, current "
    "marketing status, predicate suitability, comparability, substantial equivalence, "
    "safety, market size, or regulatory strategy."
)

_LOCK = threading.Lock()
_LAST_SOURCE_REQUEST = 0.0
_SOURCE_RESERVATIONS: deque[float] = deque()
_COHORT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class SourceBusyError(RuntimeError):
    pass


def validate_product_code(value: str) -> str:
    normalized = value.strip().upper()
    if not PRODUCT_CODE_PATTERN.fullmatch(normalized):
        raise ValueError("product_code must contain exactly three ASCII letters or digits")
    return normalized


def validate_k_number(value: str) -> str:
    normalized = value.strip().upper()
    if not K_NUMBER_PATTERN.fullmatch(normalized):
        raise ValueError("k_number must use K followed by exactly six digits")
    return normalized


def _plain(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _reserve_source_request(now: float) -> None:
    cutoff = now - 86_400.0
    while _SOURCE_RESERVATIONS and _SOURCE_RESERVATIONS[0] <= cutoff:
        _SOURCE_RESERVATIONS.popleft()
    if len(_SOURCE_RESERVATIONS) >= MAX_SOURCE_REQUESTS_PER_PROCESS_DAY:
        raise SourceBusyError("the MCP source-request budget is temporarily exhausted")
    _SOURCE_RESERVATIONS.append(now)


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "Quanta-510k-MCP/0.3.0 "
                "(+https://github.com/QuantaAIBot/fda-510k-product-code-export)"
            ),
        },
    )
    with urlopen(request, timeout=8.0) as response:
        body = response.read(MAX_SOURCE_RESPONSE_BYTES + 1)
    if len(body) > MAX_SOURCE_RESPONSE_BYTES:
        raise RuntimeError("openFDA response exceeded the configured size boundary")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise RuntimeError("openFDA response must be a JSON object")
    return payload


def _bounded_records(payload: dict[str, Any], product_code: str | None, limit: int) -> list[dict[str, str]]:
    raw_records = payload.get("results", [])
    if not isinstance(raw_records, list):
        return []
    records: list[dict[str, str]] = []
    for raw in raw_records[:limit]:
        if not isinstance(raw, dict):
            continue
        k_number = _plain(raw.get("k_number")).upper()
        record = {
            "k_number": k_number,
            "device_name": _plain(raw.get("device_name")),
            "applicant": _plain(raw.get("applicant")),
            "product_code": product_code or _plain(raw.get("product_code")).upper(),
            "decision_date": _plain(raw.get("decision_date")),
            "decision_description": _plain(raw.get("decision_description")),
            "clearance_type": _plain(raw.get("clearance_type")),
            "detail_url": (
                "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/"
                f"pmn.cfm?ID={k_number}"
                if K_NUMBER_PATTERN.fullmatch(k_number)
                else ""
            ),
        }
        records.append({field: record[field] for field in PUBLIC_RECORD_FIELDS})
    return records


def _source_total(payload: dict[str, Any]) -> int | None:
    meta = payload.get("meta")
    results = meta.get("results") if isinstance(meta, dict) else None
    total = results.get("total") if isinstance(results, dict) else None
    return total if isinstance(total, int) and not isinstance(total, bool) and total >= 0 else None


def _source_request(url: str) -> dict[str, Any]:
    global _LAST_SOURCE_REQUEST
    checked_at = time.monotonic()
    with _LOCK:
        if checked_at - _LAST_SOURCE_REQUEST < MINIMUM_SOURCE_INTERVAL_SECONDS:
            raise SourceBusyError("the public source is briefly rate limited; retry shortly")
        _reserve_source_request(checked_at)
        _LAST_SOURCE_REQUEST = checked_at
    return _fetch_json(url)


def load_activity_row(receipt_file: Path, product_code: str) -> dict[str, Any]:
    code = validate_product_code(product_code)
    if not receipt_file.is_file() or receipt_file.is_symlink():
        raise RuntimeError("the current activity receipt is unavailable")
    size = receipt_file.stat().st_size
    if not 1 <= size <= MAX_RECEIPT_BYTES:
        raise RuntimeError("the current activity receipt is outside its size boundary")
    payload = receipt_file.read_bytes()
    if len(payload) != size:
        raise RuntimeError("the current activity receipt changed while it was read")
    receipt = json.loads(payload)
    if not isinstance(receipt, dict):
        raise RuntimeError("the activity receipt must be a JSON object")
    publication = receipt.get("publication")
    windows = receipt.get("windows")
    source = receipt.get("source")
    rows = publication.get("rows") if isinstance(publication, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise RuntimeError("the activity receipt has an invalid row boundary")
    if not isinstance(windows, dict) or not isinstance(source, dict):
        raise RuntimeError("the activity receipt is missing source boundaries")

    requested = None
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("the activity receipt contains an invalid row")
        row_code = validate_product_code(str(row.get("product_code", "")))
        if row_code in seen:
            raise RuntimeError("the activity receipt contains duplicate codes")
        seen.add(row_code)
        rank = row.get("rank")
        current = row.get("current_count")
        previous = row.get("previous_count")
        difference = row.get("difference")
        valid_previous = previous is None or (
            isinstance(previous, int) and not isinstance(previous, bool) and previous >= 1
        )
        if not (
            isinstance(rank, int)
            and not isinstance(rank, bool)
            and 1 <= rank <= 100
            and isinstance(current, int)
            and not isinstance(current, bool)
            and current >= 1
            and valid_previous
            and difference == (current - previous if isinstance(previous, int) else None)
        ):
            raise RuntimeError("the activity receipt contains invalid counts")
        if row_code == code:
            requested = {
                "product_code": row_code,
                "rank": rank,
                "current_count": current,
                "previous_count": previous,
                "difference": difference,
            }
    if requested is None:
        raise ValueError("choose a code displayed in the current activity index")
    for name in ("current", "previous"):
        window = windows.get(name)
        if not isinstance(window, dict):
            raise RuntimeError("the activity receipt has invalid windows")
        for endpoint in ("start", "end"):
            value = window.get(endpoint)
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise RuntimeError("the activity receipt has invalid windows")
            requested[f"{name}_{endpoint}"] = value
    requested["generated_at_utc"] = _plain(receipt.get("generated_at_utc"))
    requested["source_last_updated"] = _plain(source.get("source_last_updated"))
    return requested


def fetch_product_code_cohort(product_code: str) -> dict[str, Any]:
    code = validate_product_code(product_code)
    checked_at = time.monotonic()
    with _LOCK:
        cached = _COHORT_CACHE.get(code)
        if cached and checked_at - cached[0] <= CACHE_TTL_SECONDS:
            return cached[1]
    url = f"{OPENFDA_510K_ENDPOINT}?{urlencode({'search': f'product_code:{code}', 'sort': 'decision_date:desc', 'limit': 25})}"
    payload = _source_request(url)
    result = {
        "status": "returned",
        "source_url": url,
        "total": _source_total(payload),
        "records": _bounded_records(payload, code, 5),
    }
    with _LOCK:
        _COHORT_CACHE[code] = (time.monotonic(), result)
    return result


def search_exact_k_number(k_number: str) -> dict[str, Any]:
    normalized = validate_k_number(k_number)
    url = f"{OPENFDA_510K_ENDPOINT}?{urlencode({'search': f'k_number:{normalized}', 'sort': 'decision_date:desc', 'limit': 25})}"
    payload = _source_request(url)
    return {
        "status": "returned",
        "source_url": url,
        "total": _source_total(payload),
        "records": _bounded_records(payload, None, 25),
    }


def build_snapshot_scope(public_host: str = DEFAULT_PUBLIC_HOST) -> dict[str, Any]:
    origin = f"https://{public_host}"
    return {
        "schema_version": "1.0",
        "service": "FDA 510(k) Product-Code Activity Snapshot",
        "founding_price_usd": 79,
        "price_status": "unvalidated hypothesis",
        "qualified_inquiries": 0,
        "buyers": 0,
        "revenue_usd": 0,
        "scope": (
            "One public three-character product code; dated HTML snapshot; CSV source "
            "ledger; rolling-window comparison; newest records; visible gaps and limits; "
            "one factual-correction round."
        ),
        "product_url": f"{origin}/products/510k-product-code-activity-snapshot/",
        "sample_url": f"{origin}/samples/510k-product-code-activity-snapshot/",
        "claim_boundary": CLAIM_BOUNDARY,
        "ai_disclosure": AI_DISCLOSURE,
    }


def create_server(receipt_file: Path, public_host: str = DEFAULT_PUBLIC_HOST) -> MCPServer:
    server = MCPServer(
        name="quelle-fda-510k",
        title="Quanta FDA 510(k) Public-Source Tools",
        description="Three strict, read-only public FDA 510(k) retrieval tools.",
        instructions=(
            f"{AI_DISCLOSURE} {CLAIM_BOUNDARY} Do not send patient, confidential, "
            "credential, contact-list, trade-secret, or unpublished regulated information."
        ),
        website_url=f"https://{public_host}/tools/510k-mcp-server/",
        version=__version__,
        log_level="WARNING",
    )
    read_open = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)
    read_local = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

    @server.tool(
        name="preview_product_code_activity",
        description="Return receipt counts and at most five newest public records for one currently displayed three-character code. No market or regulatory conclusion.",
        annotations=read_open,
        structured_output=True,
    )
    async def preview_product_code_activity(product_code: str) -> dict[str, Any]:
        activity = await anyio.to_thread.run_sync(load_activity_row, receipt_file, product_code)
        cohort = await anyio.to_thread.run_sync(fetch_product_code_cohort, activity["product_code"])
        return {
            "schema_version": "1.0",
            "status": cohort["status"],
            "product_code": activity["product_code"],
            "activity": activity,
            "source_reported_total": cohort["total"],
            "newest_records": cohort["records"],
            "source_url": cohort["source_url"],
            "record_limit": 5,
            "claim_boundary": CLAIM_BOUNDARY,
            "ai_disclosure": AI_DISCLOSURE,
        }

    @server.tool(
        name="search_510k_by_k_number",
        description="Search one public K-number in K plus six digits format; return at most 25 records. This does not identify a suitable predicate.",
        annotations=read_open,
        structured_output=True,
    )
    async def search_510k_by_k_number(k_number: str) -> dict[str, Any]:
        normalized = validate_k_number(k_number)
        result = await anyio.to_thread.run_sync(search_exact_k_number, normalized)
        return {
            "schema_version": "1.0",
            "status": result["status"],
            "k_number": normalized,
            "source_reported_total": result["total"],
            "records": result["records"],
            "source_url": result["source_url"],
            "record_limit": 25,
            "claim_boundary": CLAIM_BOUNDARY,
            "ai_disclosure": AI_DISCLOSURE,
        }

    @server.tool(
        name="get_product_code_snapshot_scope",
        description="Return the fixed $79 scope, sample links, AI disclosure, and current zero-evidence commercial status without a source request.",
        annotations=read_local,
        structured_output=True,
    )
    async def get_product_code_snapshot_scope() -> dict[str, Any]:
        return build_snapshot_scope(public_host)

    return server


class FixedPrivacyEventMiddleware:
    """Emit no arguments, results, IPs, paths, user agents, or referrer values."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        status = 500

        async def capture(message: dict[str, Any]) -> None:
            nonlocal status
            if message.get("type") == "http.response.start" and isinstance(message.get("status"), int):
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            event = {
                "schema_version": "1.0",
                "event_type": "privacy-minimized-request",
                "category": "unqualified-mcp-client",
                "destination": "mcp_endpoint",
                "source": "unavailable",
                "status": status,
            }
            print(json.dumps(event, sort_keys=True), file=sys.stdout, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8096)
    parser.add_argument("--public-host", default=DEFAULT_PUBLIC_HOST)
    parser.add_argument("--activity-index-receipt-file", type=Path, default=Path(DEFAULT_RECEIPT))
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("host must remain loopback-only; place an HTTPS reverse proxy in front")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", args.public_host):
        parser.error("public-host must contain only a DNS hostname")
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    server = create_server(args.activity_index_receipt_file, args.public_host)
    app = server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        json_response=True,
        stateless_http=True,
        max_request_body_size=MAX_BODY_BYTES,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[args.public_host, f"{args.public_host}:443", f"{args.host}:{args.port}"],
            allowed_origins=[f"https://{args.public_host}"],
        ),
        host=args.host,
    )
    config = uvicorn.Config(
        FixedPrivacyEventMiddleware(app),
        host=args.host,
        port=args.port,
        access_log=False,
        server_header=False,
        proxy_headers=False,
        log_level="warning",
        limit_concurrency=64,
    )
    anyio.run(uvicorn.Server(config).serve)


if __name__ == "__main__":
    main()
