from test.util.abstract_integration_test import IntegrationTest


class TestAuthUserLifecycle(IntegrationTest):
    BASE_PATH = "/api/v1"

    @classmethod
    def setup_class(cls):
        super().setup_class()
        from open_webui.models.auths import Auths
        from open_webui.models.users import Users

        cls.auths = Auths
        cls.users = Users

    def test_signup_creates_auth_and_user(self):
        data, _ = self.sign_up()
        uid = data["id"]

        from open_webui.internal.db import get_db
        from open_webui.models.auths import Auth
        from open_webui.models.users import User

        with get_db() as db:
            auth = db.get(Auth, uid)
            user = db.get(User, uid)

        assert auth is not None
        assert auth.email == self.ADMIN_EMAIL
        assert user is not None
        assert user.name == self.ADMIN_NAME
        assert user.email == self.ADMIN_EMAIL

    def test_add_user_creates_auth_and_user(self):
        _, admin_headers = self.sign_up()
        data, _ = self.add_user(admin_headers)
        uid = data["id"]

        from open_webui.internal.db import get_db
        from open_webui.models.auths import Auth
        from open_webui.models.users import User

        with get_db() as db:
            auth = db.get(Auth, uid)
            user = db.get(User, uid)

        assert auth is not None
        assert auth.email == self.TEST_EMAIL
        assert user is not None
        assert user.name == self.TEST_NAME

    def test_delete_user_removes_auth_user_and_chats(self):
        _, admin_headers = self.sign_up()
        user_data, user_headers = self.add_user(admin_headers)
        uid = user_data["id"]

        chat_resp = self.fast_api_client.post(
            "/api/v1/chats/new",
            json={"chat": {"messages": []}},
            headers=user_headers,
        )
        assert chat_resp.status_code == 200
        chat_id = chat_resp.json()["id"]

        resp = self.fast_api_client.delete(
            f"/api/v1/users/{uid}", headers=admin_headers
        )
        assert resp.status_code == 200

        from open_webui.internal.db import get_db
        from open_webui.models.auths import Auth
        from open_webui.models.users import User
        from open_webui.models.chats import Chat

        with get_db() as db:
            assert db.get(Auth, uid) is None
            assert db.get(User, uid) is None
            assert db.get(Chat, chat_id) is None

    def test_update_user_changes_auth_and_user(self):
        _, admin_headers = self.sign_up()
        user_data, _ = self.add_user(admin_headers)
        uid = user_data["id"]

        resp = self.fast_api_client.post(
            f"/api/v1/users/{uid}/update",
            json={
                "name": "New Name",
                "email": "new@test.com",
                "profile_image_url": "/user.png",
                "role": "user",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200

        from open_webui.internal.db import get_db
        from open_webui.models.auths import Auth
        from open_webui.models.users import User

        with get_db() as db:
            auth = db.get(Auth, uid)
            user = db.get(User, uid)

        assert auth.email == "new@test.com"
        assert user.name == "New Name"
        assert user.email == "new@test.com"


class TestDBAtomicity(IntegrationTest):

    def test_rollback_undoes_model_write(self):
        _, admin_headers = self.sign_up()
        user_data, _ = self.add_user(admin_headers)
        uid = user_data["id"]

        from open_webui.internal.db import get_db
        from open_webui.models.auths import Auths, Auth

        with get_db() as session:
            Auths.update_email_by_id(uid, "gone@test.com", db=session)
            session.rollback()

        with get_db() as db:
            assert db.get(Auth, uid).email == user_data["email"], "rollback should undo model write"


class TestChatTagOperations(IntegrationTest):
    BASE_PATH = "/api/v1/chats"

    @classmethod
    def setup_class(cls):
        super().setup_class()
        from open_webui.models.chats import Chats
        from open_webui.models.tags import Tags

        cls.chats = Chats
        cls.tags = Tags

    def _create_chat(self, headers):
        resp = self.fast_api_client.post(
            "/api/v1/chats/new",
            json={"chat": {"messages": []}},
            headers=headers,
        )
        assert resp.status_code == 200
        return resp.json()["id"]

    def _add_tag(self, chat_id, tag_name, headers):
        resp = self.fast_api_client.post(
            f"/api/v1/chats/{chat_id}/tags",
            json={"name": tag_name},
            headers=headers,
        )
        assert resp.status_code == 200
        return resp.json()

    def test_add_tag_creates_row_and_updates_meta(self):
        _, headers = self.sign_up()
        chat_id = self._create_chat(headers)

        self._add_tag(chat_id, "my tag", headers)

        from open_webui.internal.db import get_db
        from open_webui.models.chats import Chat
        from open_webui.models.tags import Tag

        with get_db() as db:
            chat = db.get(Chat, chat_id)
            assert "my_tag" in chat.meta.get("tags", [])

            tag = db.query(Tag).filter_by(id="my_tag").first()
            assert tag is not None
            assert tag.name == "my tag"

    def test_delete_chat_removes_orphan_tags(self):
        _, headers = self.sign_up()
        chat_id = self._create_chat(headers)
        self._add_tag(chat_id, "unique tag", headers)

        resp = self.fast_api_client.delete(
            f"/api/v1/chats/{chat_id}", headers=headers
        )
        assert resp.status_code == 200

        from open_webui.internal.db import get_db
        from open_webui.models.chats import Chat
        from open_webui.models.tags import Tag

        with get_db() as db:
            assert db.get(Chat, chat_id) is None
            assert db.query(Tag).filter_by(id="unique_tag").first() is None

    def test_delete_last_tag_removes_orphan(self):
        _, headers = self.sign_up()
        chat_id = self._create_chat(headers)
        self._add_tag(chat_id, "lonely tag", headers)

        resp = self.fast_api_client.request(
            "DELETE",
            f"/api/v1/chats/{chat_id}/tags",
            json={"name": "lonely tag"},
            headers=headers,
        )
        assert resp.status_code == 200

        from open_webui.internal.db import get_db
        from open_webui.models.chats import Chat
        from open_webui.models.tags import Tag

        with get_db() as db:
            chat = db.get(Chat, chat_id)
            assert "lonely_tag" not in chat.meta.get("tags", [])
            assert db.query(Tag).filter_by(id="lonely_tag").first() is None

    def test_delete_all_tags_clears_everything(self):
        _, headers = self.sign_up()
        chat_id = self._create_chat(headers)
        self._add_tag(chat_id, "tag one", headers)
        self._add_tag(chat_id, "tag two", headers)

        resp = self.fast_api_client.delete(
            f"/api/v1/chats/{chat_id}/tags/all", headers=headers
        )
        assert resp.status_code == 200

        from open_webui.internal.db import get_db
        from open_webui.models.chats import Chat
        from open_webui.models.tags import Tag

        with get_db() as db:
            chat = db.get(Chat, chat_id)
            assert chat.meta.get("tags", []) == []
            assert db.query(Tag).filter_by(id="tag_one").first() is None
            assert db.query(Tag).filter_by(id="tag_two").first() is None
