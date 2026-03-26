"""
Chat search endpoint: GET /api/v1/chats/search?text=...
Searches both title and message content.
"""

from test.util.abstract_integration_test import IntegrationTest


class TestChatSearch(IntegrationTest):

    def setup_method(self):
        super().setup_method()
        _, self.headers = self.sign_up()

    def search(self, text, page=1):
        resp = self.fast_api_client.get(
            f"/api/v1/chats/search?text={text}&page={page}",
            headers=self.headers,
        )
        assert resp.status_code == 200, f"search failed: {resp.text}"
        return resp.json()

    def test_search_by_content_and_title(self):
        chat = self.chat_with_message("the quick brown fox", title="animal facts")
        self.create_chat(self.headers, chat=chat)
        self.create_chat(
            self.headers, chat=self.chat_with_message("delta echo foxtrot")
        )

        assert len(self.search("quick brown")) == 1, "message content match"
        assert len(self.search("animal fact")) == 1, "title match partial"
        assert len(self.search("nonexistent")) == 0, "no match"
        assert len(self.search("foxtrot")) == 1, "only matching chat returned"
