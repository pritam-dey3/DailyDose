import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.api import app
from src.db import get_session
from src.db.models import Dose, FrequencyPeriod, FrequencyType, Tag

# Create an in-memory SQLite database for testing
sqlite_url = "sqlite:///:memory:"
engine = create_engine(
    sqlite_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def drop_db_and_tables():
    SQLModel.metadata.drop_all(engine)


def get_test_session():
    with Session(engine) as session:
        yield session


app.dependency_overrides[get_session] = get_test_session
client = TestClient(app)


@pytest.fixture(name="session")
def session_fixture():
    create_db_and_tables()
    with Session(engine) as session:
        yield session
    drop_db_and_tables()


def test_create_dose(session: Session):
    # Create tag first
    tag = Tag(name="health", demand=1.0)
    session.add(tag)
    session.commit()

    response = client.post(
        "/doses",
        json={
            "id": "dose1",
            "tag_name": "health",
            "message": "Drink water",
            "frequency_type": "at-least",
            "frequency_count": 1,
            "frequency_period": "day",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "dose1"
    assert data["tag_name"] == "health"
    assert data["message"] == "Drink water"
    assert data["frequency_type"] == "at-least"
    assert data["frequency_period"] == "day"


def test_get_doses(session: Session):
    # Setup
    tag = Tag(name="health", demand=1.0)
    session.add(tag)
    dose = Dose(
        id="dose1",
        tag_name="health",
        message="Drink water",
        frequency_type=FrequencyType.AT_LEAST,
        frequency_count=1,
        frequency_period=FrequencyPeriod.DAY,
    )
    session.add(dose)
    session.commit()

    response = client.get("/doses")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "dose1"


def test_get_dose(session: Session):
    # Setup
    tag = Tag(name="health", demand=1.0)
    session.add(tag)
    dose = Dose(
        id="dose1",
        tag_name="health",
        message="Drink water",
        frequency_type=FrequencyType.AT_LEAST,
        frequency_count=1,
        frequency_period=FrequencyPeriod.DAY,
    )
    session.add(dose)
    session.commit()

    response = client.get("/doses/dose1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "dose1"


def test_get_dose_not_found(session: Session):
    response = client.get("/doses/nonexistent")
    assert response.status_code == 404


def test_create_dose_duplicate(session: Session):
    tag = Tag(name="health", demand=1.0)
    session.add(tag)
    dose = Dose(
        id="dose1",
        tag_name="health",
        message="Drink water",
        frequency_type=FrequencyType.AT_LEAST,
        frequency_count=1,
        frequency_period=FrequencyPeriod.DAY,
    )
    session.add(dose)
    session.commit()

    response = client.post(
        "/doses",
        json={
            "id": "dose1",
            "tag_name": "health",
            "message": "Drink water",
            "frequency_type": "at-least",
            "frequency_count": 1,
            "frequency_period": "day",
        },
    )
    assert response.status_code == 400


def test_create_dose_missing_tag(session: Session):
    response = client.post(
        "/doses",
        json={
            "id": "dose1",
            "tag_name": "missing_tag",
            "message": "Drink water",
            "frequency_type": "at-least",
            "frequency_count": 1,
            "frequency_period": "day",
        },
    )
    assert response.status_code == 400


def test_create_tag(session: Session):
    response = client.post(
        "/tags",
        json={"name": "finance", "demand": 0.5},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "finance"
    assert data["demand"] == 0.5


def test_get_tags(session: Session):
    tag = Tag(name="finance", demand=0.5)
    session.add(tag)
    session.commit()

    response = client.get("/tags")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "finance"


def test_get_tag(session: Session):
    tag = Tag(name="finance", demand=0.5)
    session.add(tag)
    session.commit()

    response = client.get("/tags/finance")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "finance"


def test_get_tag_not_found(session: Session):
    response = client.get("/tags/nonexistent")
    assert response.status_code == 404


def test_create_tag_duplicate(session: Session):
    tag = Tag(name="finance", demand=0.5)
    session.add(tag)
    session.commit()

    response = client.post(
        "/tags",
        json={"name": "finance", "demand": 0.8},
    )
    assert response.status_code == 400
