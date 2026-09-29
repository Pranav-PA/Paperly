import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment
os.environ["DATABASE_URL"] = "sqlite:///./test_paperly.db"
os.environ["DEBUG"] = "false"
os.environ["GEMINI_API_KEY"] = ""  # always use the offline mock, never call the real API from tests

from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test_paperly.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Seed a test teacher user
    if not db.query(User).filter(User.username == "testteacher").first():
        user = User(
            username="testteacher",
            hashed_password=get_password_hash("testpassword123"),
            full_name="Test Teacher",
            role="teacher",
            is_active=True
        )
        db.add(user)
        db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_paperly.db"):
        os.remove("./test_paperly.db")


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "testteacher", "password": "testpassword123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
