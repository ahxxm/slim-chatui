from test.util.abstract_integration_test import IntegrationTest


class TestConfigPersistence(IntegrationTest):
    BASE_PATH = "/api/v1/auths"

    @classmethod
    def setup_class(cls):
        super().setup_class()
        from open_webui.config import get_config

        cls.get_config = staticmethod(get_config)

    def test_admin_config_persists_to_db(self):
        _, headers = self.sign_up()

        defaults = self.fast_api_client.get(
            self.create_url("/admin/config"), headers=headers
        ).json()

        updated = {
            **defaults,
            "WEBUI_URL": "https://changed.example.com",
            "DEFAULT_USER_ROLE": "user",
        }
        resp = self.fast_api_client.post(
            self.create_url("/admin/config"), json=updated, headers=headers
        )
        assert resp.status_code == 200, f"update failed: {resp.text}"

        db_config = self.get_config()
        assert (
            db_config["webui"]["url"] == "https://changed.example.com"
        ), "WEBUI_URL not persisted to DB"
        assert (
            db_config["ui"]["default_user_role"] == "user"
        ), "DEFAULT_USER_ROLE not persisted to DB"

    def test_signup_blocks_in_memory_without_persist(self):
        self.sign_up()

        resp = self.fast_api_client.post(
            "/api/v1/auths/signup",
            json={
                "email": "second@test.com",
                "password": "password",
                "name": "Second",
            },
        )
        assert resp.status_code == 403, "has_users() should reject second signup"
