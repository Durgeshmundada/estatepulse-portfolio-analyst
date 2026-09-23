from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Property, User


def test_update_requires_confirmation_and_commits_once():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add(User(id="U001", name="Rahul Mehta", city="Mumbai"))
        db.add(
            Property(
                id="P001", user_id="U001", property_type_raw="Retail",
                property_type="RETAIL", location="Bandra West, Mumbai",
                city_normalized="Mumbai", area_sqft=5200,
                current_value_inr=120_000_000, annual_rent_inr=7_200_000,
                occupancy_status="TENANTED", tenant_status="YES",
            )
        )

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            assert client.post(
                "/api/session", json={"user_id": "U001", "access_code": "demo"}
            ).status_code == 200
            conversation = client.post("/api/conversations", json={}).json()
            proposal = client.post(
                f"/api/conversations/{conversation['id']}/messages",
                json={"request_id": "update-request-0001", "text": "Update my Bandra property value to ₹14 Cr"},
            ).json()
            review = proposal["message"]["cards"][0]
            assert review["type"] == "change_review"
            with factory() as db:
                assert db.get(Property, "P001").current_value_inr == 120_000_000
            receipt = client.post(
                f"/api/changes/{review['change_id']}/confirm",
                json={"request_id": "confirm-request-0001"},
            )
            assert receipt.status_code == 200
            assert "₹31.70 Cr" not in receipt.json()["message"]["text"]
            assert "₹14.00 Cr" in receipt.json()["message"]["text"]
            with factory() as db:
                assert db.scalar(select(Property.current_value_inr).where(Property.id == "P001")) == 140_000_000
    finally:
        app.dependency_overrides.clear()
