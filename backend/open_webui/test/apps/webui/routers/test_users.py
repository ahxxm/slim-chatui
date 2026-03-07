from test.util.abstract_integration_test import IntegrationTest


class TestUsers(IntegrationTest):
    BASE_PATH = "/api/v1/users"

    @classmethod
    def setup_class(cls):
        super().setup_class()
        from open_webui.models.users import Users

        cls.users = Users

    def test_user_settings(self):
        _, admin_headers = self.sign_up()
        _, user_headers = self.add_user(admin_headers)

        # empty initially
        response = self.fast_api_client.get(
            self.create_url("/user/settings"), headers=user_headers
        )
        assert response.status_code == 200
        assert response.json() is None

        # update
        settings = {
            "ui": {"attr1": "value1", "attr2": "value2"},
            "model_config": {"attr3": "value3", "attr4": "value4"},
        }
        response = self.fast_api_client.post(
            self.create_url("/user/settings/update"),
            json=settings,
            headers=user_headers,
        )
        assert response.status_code == 200

        # read back
        response = self.fast_api_client.get(
            self.create_url("/user/settings"), headers=user_headers
        )
        assert response.status_code == 200
        assert response.json() == settings

