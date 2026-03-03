from test.util.abstract_integration_test import IntegrationTest


class TestAuths(IntegrationTest):
    BASE_PATH = "/api/v1/auths"

    @classmethod
    def setup_class(cls):
        super().setup_class()
        from open_webui.models.auths import Auths
        from open_webui.models.users import Users

        cls.users = Users
        cls.auths = Auths

    def test_update_profile(self):
        data, headers = self.sign_up()

        response = self.fast_api_client.post(
            self.create_url("/update/profile"),
            json={"name": "Updated Name", "profile_image_url": "/user.png"},
            headers=headers,
        )
        assert response.status_code == 200

        db_user = self.users.get_user_by_id(data["id"])
        assert db_user.name == "Updated Name"

    def test_update_password(self):
        _, headers = self.sign_up()

        from open_webui.utils.auth import verify_password

        response = self.fast_api_client.post(
            self.create_url("/update/password"),
            json={
                "password": self.ADMIN_PASSWORD,
                "new_password": "new_password",
            },
            headers=headers,
        )
        assert response.status_code == 200

        old_auth = self.auths.authenticate_user(
            self.ADMIN_EMAIL,
            lambda pw: verify_password(self.ADMIN_PASSWORD, pw),
        )
        assert old_auth is None

        new_auth = self.auths.authenticate_user(
            self.ADMIN_EMAIL,
            lambda pw: verify_password("new_password", pw),
        )
        assert new_auth is not None

    def test_get_admin_details(self):
        _, headers = self.sign_up()

        response = self.fast_api_client.get(
            self.create_url("/admin/details"), headers=headers
        )
        assert response.status_code == 200
        assert response.json() == {
            "name": self.ADMIN_NAME,
            "email": self.ADMIN_EMAIL,
        }
