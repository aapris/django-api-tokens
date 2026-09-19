"""OpenAPI integration via drf-spectacular."""

from drf_spectacular.generators import SchemaGenerator


def test_schema_declares_bearer_scheme() -> None:
    """The generated schema documents token auth as HTTP bearer."""
    schema = SchemaGenerator().get_schema(request=None, public=True)
    scheme = schema["components"]["securitySchemes"]["apiToken"]
    assert (scheme["type"], scheme["scheme"]) == ("http", "bearer")
    assert "test_<key_id>_<secret>" in scheme["description"]
