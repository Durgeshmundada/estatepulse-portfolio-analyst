import argparse
import csv
from pathlib import Path

from sqlalchemy import select

from .analytics import normalize_city, normalize_type
from .db import Base, SessionLocal, engine
from .models import Property, User


def seed(data_dir: Path) -> tuple[int, int]:
    Base.metadata.create_all(engine)
    users_path = data_dir / "users.csv"
    properties_path = data_dir / "properties.csv"
    with users_path.open(encoding="utf-8-sig", newline="") as stream:
        users = list(csv.DictReader(stream))
    with properties_path.open(encoding="utf-8-sig", newline="") as stream:
        properties = list(csv.DictReader(stream))
    user_ids = {row["user_id"] for row in users}
    if len(user_ids) != len(users):
        raise ValueError("Duplicate user IDs in seed")
    if any(row["user_id"] not in user_ids for row in properties):
        raise ValueError("Property references unknown user")
    inserted_users = inserted_properties = 0
    with SessionLocal.begin() as session:
        existing_users = set(session.scalars(select(User.id)))
        existing_properties = set(session.scalars(select(Property.id)))
        for row in users:
            if row["user_id"] in existing_users:
                continue
            session.add(User(
                id=row["user_id"], name=row["name"], city=row["city"],
                preferences=row["preferences"], preferred_locations=row["preferred_locations"],
                portfolio_value_preference=row["portfolio_value_preference_inr"],
            ))
            inserted_users += 1
        for row in properties:
            if row["property_id"] in existing_properties:
                continue
            session.add(Property(
                id=row["property_id"], user_id=row["user_id"],
                property_type_raw=row["property_type"],
                property_type=normalize_type(row["property_type"]) or "OTHER",
                sub_type=row["sub_type"] or None, location=row["location"],
                city_normalized=normalize_city(row["location"]),
                area_sqft=int(row["area_sqft"]) if row["area_sqft"] else None,
                current_value_inr=int(row["current_estimated_value_inr"]),
                purchase_price_inr=int(row["purchase_price_inr"]) if row["purchase_price_inr"] else None,
                annual_rent_inr=int(row["annual_rent_inr"]) if row["annual_rent_inr"] else None,
                occupancy_status=row["occupancy_status"].upper().replace("-", "_"),
                tenant_status=row["tenant_status"].upper(),
                ownership_percent=int(row["ownership_percent"]), status=row["status"].upper(),
            ))
            inserted_properties += 1
    return inserted_users, inserted_properties


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("../data"))
    args = parser.parse_args()
    users, properties = seed(args.data_dir)
    print(f"Seed complete: {users} users, {properties} properties inserted")


if __name__ == "__main__":
    main()

