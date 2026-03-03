from urllib.parse import urlencode


class IntegrationTest:
    BASE_PATH = ""
    ADMIN_EMAIL = "admin@test.com"
    ADMIN_PASSWORD = "password"
    ADMIN_NAME = "Admin"
    TEST_EMAIL = "user@test.com"
    TEST_PASSWORD = "password"
    TEST_NAME = "User"

    @classmethod
    def setup_class(cls):
        from open_webui.main import app
        from starlette.testclient import TestClient

        cls.app = app
        cls.fast_api_client = TestClient(app)

    def setup_method(self):
        from open_webui.internal.db import engine, Base

        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())

    def create_url(self, path="", query_params=None):
        url = f"{self.BASE_PATH}{path}"
        if query_params:
            url = f"{url}?{urlencode(query_params)}"
        return url

    def sign_up(self):
        """First user becomes admin. Returns (data, headers)."""
        resp = self.fast_api_client.post(
            "/api/v1/auths/signup",
            json={
                "email": self.ADMIN_EMAIL,
                "password": self.ADMIN_PASSWORD,
                "name": self.ADMIN_NAME,
            },
        )
        assert resp.status_code == 200, f"signup failed: {resp.text}"
        data = resp.json()
        headers = {"Authorization": f"Bearer {data['token']}"}
        return data, headers

    def add_user(self, headers):
        """Admin adds a user via API. Returns (data, headers)."""
        resp = self.fast_api_client.post(
            "/api/v1/auths/add",
            json={
                "email": self.TEST_EMAIL,
                "password": self.TEST_PASSWORD,
                "name": self.TEST_NAME,
                "role": "user",
                "profile_image_url": "/user.png",
            },
            headers=headers,
        )
        assert resp.status_code == 200, f"add_user failed: {resp.text}"
        data = resp.json()
        user_headers = {"Authorization": f"Bearer {data['token']}"}
        return data, user_headers
