"""
User story: 10 chats, shift-delete 2 quickly, all chats disappear until refresh.

Each shift-click delete fires this request sequence:
  1. DELETE /chats/{id}
  2. GET /chats/all/tags
  3. GET /chats/all/tags    (initChatList)
  4. GET /chats/pinned      (initChatList)
  5. GET /chats/?page=1     (initChatList)

Two rapid clicks = 10 requests, many overlapping.
"""

from concurrent.futures import ThreadPoolExecutor

from test.util.abstract_integration_test import IntegrationTest


class TestChatDeleteRace(IntegrationTest):
    BASE_PATH = "/api/v1/chats"

    def _create_chat(self, headers, title="test"):
        resp = self.fast_api_client.post(
            "/api/v1/chats/new",
            json={"chat": {"messages": [], "title": title}},
            headers=headers,
        )
        assert resp.status_code == 200, f"create chat failed: {resp.text}"
        return resp.json()["id"]

    def _frontend_delete_click(self, chat_id, headers):
        """Exact HTTP sequence one shift-click delete triggers in the frontend."""
        # ChatItem.deleteChatHandler
        delete_resp = self.fast_api_client.delete(
            f"/api/v1/chats/{chat_id}", headers=headers
        )
        self.fast_api_client.get("/api/v1/chats/all/tags", headers=headers)

        # Sidebar.initChatList (fired by dispatch('change'))
        self.fast_api_client.get("/api/v1/chats/all/tags", headers=headers)
        self.fast_api_client.get("/api/v1/chats/?include_pinned=true", headers=headers)
        list_resp = self.fast_api_client.get("/api/v1/chats/?page=1", headers=headers)
        return delete_resp, list_resp

    def test_rapid_delete_2_of_10(self):
        _, headers = self.sign_up()
        chat_ids = [self._create_chat(headers, f"Chat {i}") for i in range(10)]

        resp = self.fast_api_client.get("/api/v1/chats/?page=1", headers=headers)
        assert len(resp.json()) == 10, "setup: expect 10 chats"

        # Two rapid shift-clicks, concurrent
        results = {}

        def click(n):
            d, l = self._frontend_delete_click(chat_ids[n], headers)
            results[n] = {"delete_status": d.status_code, "list": l.json()}

        with ThreadPoolExecutor(max_workers=2) as pool:
            f0 = pool.submit(click, 0)
            f1 = pool.submit(click, 1)
            f0.result()
            f1.result()

        assert results[0]["delete_status"] == 200, "first delete should succeed"
        assert results[1]["delete_status"] == 200, "second delete should succeed"

        # What the frontend would set into $chats — the last list response
        for n in (0, 1):
            assert (
                len(results[n]["list"]) >= 8
            ), f"click {n} list returned {len(results[n]['list'])}, expect >= 8"

        # Final truth: what the server has
        final = self.fast_api_client.get("/api/v1/chats/?page=1", headers=headers)
        assert len(final.json()) == 8, f"expect 8 chats, got {len(final.json())}"
