import os

from open_webui.test.util.abstract_integration_test import IntegrationTest
from open_webui.models.chats import Chats
from open_webui.models.files import Files
from open_webui.tasks import delete_orphaned_files


class TestOrphanFileCleanup(IntegrationTest):
    def test_orphan_file_cleaned_from_db_and_disk(self):
        """Upload image, link to chat, delete chat, cleanup removes orphan."""
        data, headers = self.sign_up()
        file_id = self.upload_image(headers)["id"]
        file_path = Files.get_file_by_id(file_id).path

        chat = self.create_chat(headers)
        # No API endpoint for file-chat linking; it happens inside chat completion middleware
        Chats.insert_chat_files(chat["id"], "msg1", [file_id], data["id"])

        assert delete_orphaned_files() == 0, "linked file not touched"

        self.fast_api_client.delete(f"/api/v1/chats/{chat['id']}", headers=headers)

        assert os.path.isfile(file_path), "disk file survives chat deletion"
        assert delete_orphaned_files() == 1

        assert Files.get_file_by_id(file_id) is None
        assert not os.path.isfile(file_path)
