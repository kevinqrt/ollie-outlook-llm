from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.app import app


@pytest.fixture
def client() -> Generator[TestClient]:
    """Provides a TestClient for the FastAPI app"""
    with TestClient(app) as c:
        yield c
