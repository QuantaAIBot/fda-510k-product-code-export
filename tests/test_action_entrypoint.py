import csv
import tempfile
import unittest
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import action_entrypoint as action  # noqa: E402
import fda_510k_export as exporter  # noqa: E402


def public_record(number="K260001"):
    return {
        "product_code": "DQY",
        "k_number": number,
        "device_name": "Example device",
        "applicant": "Example applicant",
        "decision_date": "20260818",
        "decision_description": "Substantially Equivalent",
        "clearance_type": "Traditional",
        "fda_detail_url": f"https://example.test/{number}",
        "openfda_query_url": exporter.build_query_url("DQY"),
    }


class ActionEntrypointTests(unittest.TestCase):
    def test_action_writes_bounded_csv_and_minimized_outputs(self):
        calls = []

        def fetcher(code, *, allow_network):
            calls.append((code, allow_network))
            return [public_record(), public_record("K260002")], exporter.build_query_url(code)

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            github_output = Path(directory) / "github-output.txt"
            github_output.touch()
            receipt = action.run_action(
                {
                    "FDA_510K_PRODUCT_CODE": "dqy",
                    "FDA_510K_OUTPUT": "exports/dqy.csv",
                    "FDA_510K_OVERWRITE": "false",
                    "GITHUB_WORKSPACE": str(workspace),
                    "GITHUB_OUTPUT": str(github_output),
                },
                fetcher=fetcher,
            )

            destination = workspace / "exports" / "dqy.csv"
            with destination.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            outputs = github_output.read_text(encoding="utf-8")

            self.assertEqual([("DQY", True)], calls)
            self.assertEqual(2, len(rows))
            self.assertEqual(2, receipt["row_count"])
            self.assertEqual(1, receipt["source_requests"])
            self.assertIn(f"csv-path={destination.resolve()}", outputs)
            self.assertIn("row-count=2", outputs)

    def test_action_rejects_ambiguous_boolean_and_paths_outside_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            github_output = Path(directory) / "github-output.txt"
            github_output.touch()
            base = {
                "FDA_510K_PRODUCT_CODE": "DQY",
                "FDA_510K_OUTPUT": "result.csv",
                "FDA_510K_OVERWRITE": "false",
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(github_output),
            }

            for invalid in ("yes", "1", "", " false ", "FALSE then true"):
                with self.subTest(boolean=invalid), self.assertRaises(ValueError):
                    action.run_action(
                        {**base, "FDA_510K_OVERWRITE": invalid},
                        fetcher=lambda *_args, **_kwargs: ([], "unused"),
                    )
            for invalid in (
                "../escape.csv",
                str(Path(directory) / "absolute.csv"),
                "result.txt",
                "bad\nname.csv",
            ):
                with self.subTest(path=invalid), self.assertRaises(ValueError):
                    action.run_action(
                        {**base, "FDA_510K_OUTPUT": invalid},
                        fetcher=lambda *_args, **_kwargs: ([], "unused"),
                    )

    def test_action_metadata_uses_intermediate_environment_and_no_secret(self):
        metadata = (ROOT / "action.yml").read_text(encoding="utf-8")

        self.assertIn("name: FDA 510k product-code CSV", metadata)
        self.assertIn("using: composite", metadata)
        self.assertIn("FDA_510K_PRODUCT_CODE: ${{ inputs.product-code }}", metadata)
        self.assertIn('run: python "$GITHUB_ACTION_PATH/action_entrypoint.py"', metadata)
        self.assertIn("row-count", metadata)
        self.assertNotIn("secrets.", metadata)
        self.assertNotIn("github.token", metadata)
        self.assertNotIn("${{ inputs.product-code }}\"", metadata)


if __name__ == "__main__":
    unittest.main()
