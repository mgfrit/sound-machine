# tests/test_web_app_wifi.py
import pytest
from unittest.mock import patch, MagicMock
import web_app


@pytest.fixture
def client():
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c
