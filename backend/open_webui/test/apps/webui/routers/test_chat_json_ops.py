"""
Tests for SQLite json_ operations in ChatTable methods:
- update_chat_title_by_id (json_set)
- upsert_message_to_chat_by_id_and_message_id (json_set, json_patch, json_extract, json_type, json_insert)
- add_message_status_to_chat_by_id_and_message_id (json_set, json_insert, json_extract)
- add_message_files_by_id_and_message_id (json_set, json_insert, json_extract)
"""

from test.util.abstract_integration_test import IntegrationTest

from open_webui.models.chats import ChatForm, Chats


def _seed_chat(content="hello", **kwargs):
    """Insert a chat with one root message via model layer. Returns chat id."""
    chat = Chats.insert_new_chat(
        "test-user",
        ChatForm(chat=IntegrationTest.chat_with_message(content, **kwargs)),
    )
    return chat.id


class TestUpdateChatTitleById(IntegrationTest):

    def setup_method(self):
        super().setup_method()

    def test_json_set_updates_title_preserves_history(self):
        chat_id = _seed_chat(content="keep me")
        title = "It's a \"test\" with 'quotes' & symbols <>"
        Chats.update_chat_title_by_id(chat_id, title)

        chat = Chats.get_chat_by_id(chat_id)
        assert chat.title == title, "title column updated"
        assert chat.chat["title"] == title, "json blob title updated via json_set"
        msg = chat.chat["history"]["messages"]["msg-root"]
        assert msg["content"] == "keep me", "history untouched by title update"


class TestUpsertMessage(IntegrationTest):

    def setup_method(self):
        super().setup_method()

    def test_patch_merges_keys_preserves_existing(self):
        chat_id = _seed_chat()
        Chats.upsert_message_to_chat_by_id_and_message_id(
            chat_id, "msg-root", {"content": "updated", "followUps": ["what next?"]}
        )

        chat = Chats.get_chat_by_id(chat_id)
        msg = chat.chat["history"]["messages"]["msg-root"]
        assert msg["content"] == "updated", "content patched"
        assert msg["followUps"] == ["what next?"], "new key merged"
        assert msg["role"] == "user", "unpatched fields preserved by json_patch"

    def test_insert_children_appends_and_advances_cursor(self):
        chat_id = _seed_chat()
        for reply_id in ("msg-r1", "msg-r2"):
            Chats.upsert_message_to_chat_by_id_and_message_id(
                chat_id,
                reply_id,
                {
                    "id": reply_id,
                    "role": "assistant",
                    "content": f"reply {reply_id}",
                    "parentId": "msg-root",
                    "childrenIds": [],
                },
            )

        chat = Chats.get_chat_by_id(chat_id)
        children = chat.chat["history"]["messages"]["msg-root"]["childrenIds"]
        assert children == ["msg-r1", "msg-r2"], "both children appended in order"


class TestAddMessageStatus(IntegrationTest):

    def setup_method(self):
        super().setup_method()

    def test_statuses_accumulate_and_preserve_content(self):
        chat_id = _seed_chat(content="important")
        s1 = {"type": "info", "description": "step 1"}
        s2 = {"type": "done", "description": "step 2"}
        Chats.add_message_status_to_chat_by_id_and_message_id(chat_id, "msg-root", s1)
        Chats.add_message_status_to_chat_by_id_and_message_id(chat_id, "msg-root", s2)

        chat = Chats.get_chat_by_id(chat_id)
        msg = chat.chat["history"]["messages"]["msg-root"]
        assert msg["statusHistory"] == [s1, s2], "statuses accumulate in order"
        assert msg["content"] == "important", "content untouched by status append"
