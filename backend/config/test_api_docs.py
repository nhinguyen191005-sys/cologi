from django.test import SimpleTestCase


class APIDocumentationTests(SimpleTestCase):
    def test_openapi_schema_is_available_without_authentication(self):
        response = self.client.get(
            "/api/schema/",
            HTTP_ACCEPT="application/vnd.oai.openapi",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/api/demands/", response.content)
        self.assertIn(b"/api/auth/login/", response.content)

    def test_swagger_ui_is_available_without_authentication(self):
        response = self.client.get("/api/docs/swagger/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn(b"swagger", response.content.lower())

    def test_redoc_is_available_without_authentication(self):
        response = self.client.get("/api/docs/redoc/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn(b"redoc", response.content.lower())
