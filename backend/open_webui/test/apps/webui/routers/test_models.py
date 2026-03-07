from test.util.abstract_integration_test import IntegrationTest


class TestModels(IntegrationTest):
    BASE_PATH = "/api/v1/models"

    @classmethod
    def setup_class(cls):
        super().setup_class()
        from open_webui.models.models import Models

        cls.models = Models

    def test_create_and_list_models(self):
        _, headers = self.sign_up()

        # empty at start
        response = self.fast_api_client.get(self.create_url("/list"), headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 0

        # create
        response = self.fast_api_client.post(
            self.create_url("/create"),
            json={
                "id": "my-model",
                "base_model_id": "base-model-id",
                "name": "Hello World",
                "meta": {

                    "description": "description",
                    "capabilities": None,
                    "model_config": {},
                },
                "params": {},
            },
            headers=headers,
        )
        assert response.status_code == 200

        # list shows one
        response = self.fast_api_client.get(self.create_url("/list"), headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 1

        # get by id
        response = self.fast_api_client.get(
            self.create_url("/model", query_params={"id": "my-model"}),
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["id"] == "my-model"
        assert response.json()["name"] == "Hello World"

    def test_delete_model(self):
        _, headers = self.sign_up()

        self.fast_api_client.post(
            self.create_url("/create"),
            json={
                "id": "my-model",
                "base_model_id": "base-model-id",
                "name": "Hello World",
                "meta": {

                    "description": "description",
                    "capabilities": None,
                    "model_config": {},
                },
                "params": {},
            },
            headers=headers,
        )

        response = self.fast_api_client.post(
            self.create_url("/model/delete"),
            json={"id": "my-model"},
            headers=headers,
        )
        assert response.status_code == 200

        response = self.fast_api_client.get(self.create_url("/list"), headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 0
