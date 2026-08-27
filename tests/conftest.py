import os

os.environ.setdefault("ADMIN_SECRET", "test-admin-secret")
os.environ.setdefault("CORS_ORIGINS", "https://exsize.pages.dev")
# Must be set before importing exsize.app: MCP tools (mcp_server) resolve the DB
# via SessionLocal directly, so the app-level engine has to point at the same
# test database as the fixture engine below. load_dotenv() will not override it.
os.environ["DATABASE_URL"] = "sqlite:///test.db"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from exsize.app import app
from exsize.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///test.db"


@pytest.fixture()
def client():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Fresh in-memory SQLite session for unit tests of service/repository layers."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    yield session
    session.close()
