import json

import compression.zstd as zstd

from open_webui.test.util.abstract_integration_test import IntegrationTest
from open_webui.utils.zstd import ZstdMiddleware


class TestZstdMiddleware(IntegrationTest):
    @classmethod
    def setup_class(cls):
        from open_webui.main import app
        from starlette.testclient import TestClient

        cls.app = app
        cls.fast_api_client = TestClient(ZstdMiddleware(app, minimum_size=500))

    def test_compresses_large_response(self):
        _, headers = self.sign_up()
        for _ in range(5):
            self.create_chat(headers, chat={"messages": [{"content": "a" * 200}]})

        resp = self.fast_api_client.get(
            "/api/v1/chats/",
            headers={**headers, "Accept-Encoding": "zstd"},
        )
        assert resp.status_code == 200, f"request failed: {resp.text}"
        assert resp.headers.get("content-encoding") == "zstd", "expect zstd encoding"

        data = json.loads(zstd.decompress(resp.content))
        assert len(data) == 5, "all chats returned"

    def test_skips_small_response(self):
        resp = self.fast_api_client.get(
            "/health",
            headers={"Accept-Encoding": "zstd"},
        )
        assert resp.status_code == 200, f"health check failed: {resp.text}"
        assert (
            resp.headers.get("content-encoding") is None
        ), "no encoding for small body"
        assert resp.json()["status"] is True, "health check passes"

    def test_no_compression_without_zstd_accept(self):
        _, headers = self.sign_up()
        for _ in range(5):
            self.create_chat(headers, chat={"messages": [{"content": "a" * 200}]})

        resp = self.fast_api_client.get(
            "/api/v1/chats/",
            headers={**headers, "Accept-Encoding": "gzip"},
        )
        assert (
            resp.headers.get("content-encoding") is None
        ), "no zstd without zstd accept"
        assert len(resp.json()) == 5, "all chats returned uncompressed"
