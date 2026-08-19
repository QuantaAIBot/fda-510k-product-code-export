import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import anyio


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mcp_server  # noqa: E402


RECEIPT = ROOT / "example-activity-receipt.json"


class McpServerTests(unittest.TestCase):
    def setUp(self):
        mcp_server._COHORT_CACHE.clear()
        mcp_server._SOURCE_RESERVATIONS.clear()
        mcp_server._LAST_SOURCE_REQUEST = 0.0

    def test_inputs_are_strict_public_identifiers(self):
        self.assertEqual("QIH", mcp_server.validate_product_code(" qih "))
        self.assertEqual("K243854", mcp_server.validate_k_number("k243854"))
        for value in ("QI", "Q-I", "QIH private"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mcp_server.validate_product_code(value)
        for value in ("K24385", "K243854 private", "P243854"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mcp_server.validate_k_number(value)

    def test_receipt_is_bounded_and_missing_code_fails_closed(self):
        row = mcp_server.load_activity_row(RECEIPT, "qih")
        self.assertEqual(56, row["current_count"])
        self.assertEqual(89, row["previous_count"])
        self.assertEqual(-33, row["difference"])
        with self.assertRaisesRegex(ValueError, "displayed"):
            mcp_server.load_activity_row(RECEIPT, "ZZZ")

    def test_source_normalization_caps_rows_and_excludes_contacts(self):
        payload = {
            "meta": {"results": {"total": 99}},
            "results": [
                {
                    "k_number": f"K26{index:04d}",
                    "device_name": f"Device {index}",
                    "applicant": "Public applicant",
                    "product_code": "QIH",
                    "decision_date": "20260801",
                    "address_1": "must-not-leak",
                    "contact": "must-not-leak",
                    "phone_number": "must-not-leak",
                }
                for index in range(30)
            ],
        }
        records = mcp_server._bounded_records(payload, "QIH", 5)
        rendered = json.dumps(records)

        self.assertEqual(5, len(records))
        self.assertEqual(set(mcp_server.PUBLIC_RECORD_FIELDS), set(records[0]))
        self.assertNotIn("must-not-leak", rendered)
        self.assertNotIn("address_1", rendered)

    def test_source_budget_and_cache_are_process_bounded(self):
        payload = {"meta": {"results": {"total": 1}}, "results": []}
        with patch.object(mcp_server, "_fetch_json", return_value=payload) as fetch:
            first = mcp_server.fetch_product_code_cohort("QIH")
            second = mcp_server.fetch_product_code_cohort("qih")
        self.assertEqual(first, second)
        self.assertEqual(1, fetch.call_count)
        self.assertIn("limit=25", first["source_url"])

        mcp_server._SOURCE_RESERVATIONS.extend(
            [time_value for time_value in range(mcp_server.MAX_SOURCE_REQUESTS_PER_PROCESS_DAY)]
        )
        with self.assertRaises(mcp_server.SourceBusyError):
            mcp_server._reserve_source_request(100.0)

    def test_server_exposes_only_read_only_tools_and_truthful_scope(self):
        server = mcp_server.create_server(RECEIPT)
        tools = anyio.run(server.list_tools)
        self.assertEqual(
            {
                "preview_product_code_activity",
                "search_510k_by_k_number",
                "get_product_code_snapshot_scope",
            },
            {tool.name for tool in tools},
        )
        for tool in tools:
            annotations = tool.annotations.model_dump(by_alias=True)
            self.assertTrue(annotations["readOnlyHint"])
            self.assertFalse(annotations["destructiveHint"])

        result = anyio.run(server.call_tool, "get_product_code_snapshot_scope", {})
        self.assertFalse(result.is_error)
        self.assertEqual("complete", result.result_type)
        self.assertEqual(79, result.structured_content["founding_price_usd"])
        self.assertEqual("unvalidated hypothesis", result.structured_content["price_status"])
        self.assertEqual(0, result.structured_content["buyers"])
        self.assertEqual(0, result.structured_content["revenue_usd"])
        self.assertIn("autonomous AI research agent", result.structured_content["ai_disclosure"])

    def test_privacy_middleware_does_not_emit_request_values(self):
        async def downstream(scope, receive, send):
            del scope, receive
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        async def exercise():
            async def receive():
                return {"type": "http.request", "body": b"private-body"}

            async def send(_message):
                return None

            scope = {
                "type": "http",
                "path": "/mcp/private-path",
                "query_string": b"secret=query",
                "client": ("198.51.100.8", 1234),
                "headers": [(b"user-agent", b"private-agent")],
            }
            await mcp_server.FixedPrivacyEventMiddleware(downstream)(scope, receive, send)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            anyio.run(exercise)
        rendered = output.getvalue()
        event = json.loads(rendered)
        self.assertEqual("mcp_endpoint", event["destination"])
        self.assertEqual(200, event["status"])
        for secret in ("private-body", "private-path", "secret=query", "private-agent", "198.51.100.8"):
            self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()
