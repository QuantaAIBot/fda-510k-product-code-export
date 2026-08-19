import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fda_510k_export as exporter  # noqa: E402


def sample_payload(count=30):
    return {
        "meta": {"results": {"total": 70}},
        "results": [
            {
                "k_number": f"K26{index:04d}",
                "device_name": "=DANGEROUS" if index == 0 else f"Device {index}",
                "applicant": f"Applicant {index}",
                "decision_date": "20260818",
                "decision_description": "Substantially Equivalent",
                "clearance_type": "Traditional",
                "address_1": "Excluded address",
                "contact": "Excluded person",
                "phone_number": "Excluded phone",
                "duns_number": "Excluded DUNS",
                "gmdn_terms": ["Excluded GMDN"],
            }
            for index in range(count)
        ],
    }


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ExporterTests(unittest.TestCase):
    def test_product_code_is_normalized_and_strict(self):
        self.assertEqual("DQY", exporter.validate_product_code(" dqy "))
        for invalid in ("DQ", "DQYY", "D-Q", "=1+1", ""):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                exporter.validate_product_code(invalid)

    def test_query_is_official_sorted_and_bounded(self):
        url = exporter.build_query_url("dqy")
        self.assertTrue(url.startswith(exporter.OPENFDA_510K_ENDPOINT + "?"))
        self.assertIn("search=product_code%3ADQY", url)
        self.assertIn("sort=decision_date%3Adesc", url)
        self.assertIn("limit=25", url)

    def test_network_requires_explicit_flag(self):
        with self.assertRaisesRegex(RuntimeError, "network disabled"):
            exporter.fetch_records("DQY", allow_network=False)

    def test_version_is_machine_readable_without_network_or_required_args(self):
        output = io.StringIO()
        with patch("sys.stdout", new=output), self.assertRaises(SystemExit) as raised:
            exporter.parse_args(["--version"])

        self.assertEqual(0, raised.exception.code)
        self.assertEqual("fda_510k_export 0.1.0", output.getvalue().strip())
        self.assertEqual("0.1.0", exporter.__version__)

    def test_fetch_makes_one_identified_request(self):
        calls = []

        def opener(request, timeout):
            calls.append((request, timeout))
            return FakeResponse(sample_payload(1))

        records, query_url = exporter.fetch_records(
            "dqy", allow_network=True, opener=opener
        )
        self.assertEqual(1, len(calls))
        self.assertEqual(exporter.TIMEOUT_SECONDS, calls[0][1])
        self.assertEqual(exporter.USER_AGENT, calls[0][0].get_header("User-agent"))
        self.assertEqual(query_url, records[0]["openfda_query_url"])

    def test_normalization_caps_rows_excludes_contacts_and_neutralizes_formulas(self):
        url = exporter.build_query_url("DQY")
        records = exporter.normalize_records(sample_payload(), "dqy", url)
        rendered = json.dumps(records)

        self.assertEqual(25, len(records))
        self.assertEqual("'=DANGEROUS", records[0]["device_name"])
        self.assertEqual("DQY", records[0]["product_code"])
        self.assertTrue(records[0]["fda_detail_url"].endswith("ID=K260000"))
        for excluded in (
            "Excluded address",
            "Excluded person",
            "Excluded phone",
            "Excluded DUNS",
            "Excluded GMDN",
        ):
            self.assertNotIn(excluded, rendered)
        self.assertEqual(set(exporter.CSV_FIELDS), set(records[0]))

    def test_empty_or_malformed_results_are_empty(self):
        url = exporter.build_query_url("DQY")
        self.assertEqual([], exporter.normalize_records({}, "DQY", url))
        self.assertEqual(
            [], exporter.normalize_records({"results": "invalid"}, "DQY", url)
        )

    def test_openfda_not_found_becomes_empty_result(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 404, "not found", {}, io.BytesIO(b"{}"))

        records, _ = exporter.fetch_records(
            "DQY", allow_network=True, opener=opener
        )
        self.assertEqual([], records)

    def test_csv_is_local_complete_and_refuses_accidental_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cohort.csv"
            records = exporter.normalize_records(
                sample_payload(2), "DQY", exporter.build_query_url("DQY")
            )
            exporter.write_csv(records, output)

            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(list(exporter.CSV_FIELDS), list(rows[0]))
            self.assertEqual(2, len(rows))
            self.assertEqual("'=DANGEROUS", rows[0]["device_name"])

            with self.assertRaises(FileExistsError):
                exporter.write_csv(records, output)
            exporter.write_csv([], output, overwrite=True)
            with output.open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual([], list(csv.DictReader(handle)))

    def test_readme_discloses_ai_and_bounds_claims(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("autonomous AI research agent", text)
        self.assertIn("at most the 25 newest", text)
        self.assertIn("does **not**", text)
        self.assertIn("revenue is", text)
        self.assertIn("no sales", text)
        self.assertIn("Device Identity Check", text)
        self.assertIn("actions/workflows/test.yml/badge.svg", text)
        self.assertIn("releases/tag/v0.1.0", text)

    def test_changelog_discloses_ai_and_preserves_release_claim_boundaries(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("autonomous AI research agent", text)
        self.assertIn("v0.1.0", text)
        self.assertIn("at most the 25 newest", text)
        self.assertIn("not a predicate", text)
        self.assertIn("revenue remained zero", text)

    def test_issue_forms_are_structured_public_data_only_and_fail_closed(self):
        template_dir = ROOT / ".github" / "ISSUE_TEMPLATE"
        workflow = (template_dir / "workflow-question.yml").read_text(
            encoding="utf-8"
        )
        bug = (template_dir / "bug-report.yml").read_text(encoding="utf-8")
        config = (template_dir / "config.yml").read_text(encoding="utf-8")

        for text in (workflow, bug):
            self.assertIn("autonomous AI research agent", text)
            self.assertIn("Issues are public", text)
            self.assertIn("protected health information", text)
            self.assertIn("personal contact details", text)
            self.assertIn("required: true", text)
            self.assertNotIn("type: upload", text)
            self.assertNotIn("id: contact", text)

        self.assertIn("public FDA data workflow", workflow)
        self.assertIn("not a purchase or price commitment", workflow)
        self.assertIn("not regulatory advice", workflow)
        self.assertIn("synthetic or public identifiers", bug)
        self.assertIn("Do not attach files", bug)
        self.assertIn("blank_issues_enabled: false", config)
        self.assertIn("Private paid-scope inquiry", config)

    def test_contributing_policy_blocks_sensitive_and_unbounded_scope(self):
        text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        for required in (
            "autonomous AI research agent",
            "protected health information",
            "personal contact details",
            "is not price acceptance",
            "standard-library-only",
            "silent network behavior",
        ):
            self.assertIn(required, normalized)

    def test_ci_is_read_only_bounded_and_commit_pinned(self):
        text = (ROOT / ".github" / "workflows" / "test.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("contents: read", text)
        self.assertIn("timeout-minutes: 5", text)
        self.assertIn('python-version: ["3.10", "3.12", "3.14"]', text)
        self.assertIn("PYTHONWARNINGS: error", text)
        self.assertIn(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", text
        )
        self.assertIn(
            "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", text
        )
        self.assertNotIn("permissions: write", text)
        self.assertNotIn("pull_request_target", text)
        self.assertNotIn("secrets.", text)


if __name__ == "__main__":
    unittest.main()
