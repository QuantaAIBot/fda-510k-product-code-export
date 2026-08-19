import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
SERVER_JSON = ROOT / "server.json"


class RegistryMetadataTests(unittest.TestCase):
    def test_remote_metadata_is_exact_and_non_secret(self):
        metadata = json.loads(SERVER_JSON.read_text(encoding="utf-8"))

        self.assertEqual(
            "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
            metadata["$schema"],
        )
        self.assertEqual(
            "io.github.QuantaAIBot/fda-510k-product-code-export",
            metadata["name"],
        )
        self.assertEqual("0.3.1", metadata["version"])
        self.assertEqual(
            {
                "url": "https://github.com/QuantaAIBot/fda-510k-product-code-export",
                "source": "github",
            },
            metadata["repository"],
        )
        self.assertEqual(
            [
                {
                    "type": "streamable-http",
                    "url": "https://briefs.94.130.204.220.sslip.io/mcp",
                }
            ],
            metadata["remotes"],
        )
        self.assertNotIn("packages", metadata)
        rendered = json.dumps(metadata).lower()
        for forbidden in ("token", "secret", "api_key", "authorization", "header"):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("autonomous ai research agent", rendered)

        remote = urlsplit(metadata["remotes"][0]["url"])
        self.assertEqual("https", remote.scheme)
        self.assertEqual("briefs.94.130.204.220.sslip.io", remote.hostname)
        self.assertEqual("/mcp", remote.path)
        self.assertFalse(remote.query)
        self.assertFalse(remote.fragment)


if __name__ == "__main__":
    unittest.main()
