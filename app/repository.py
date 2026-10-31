"""Small repository; callers never exchange raw database rows."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import FarmerRow
from app.schemas import FarmerProfile


class FarmerRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, farmer_id: str) -> FarmerProfile | None:
        row = self.session.get(FarmerRow, farmer_id)
        return row.as_profile() if row else None

    def list(self) -> list[FarmerProfile]:
        rows = self.session.scalars(select(FarmerRow).order_by(FarmerRow.farmer_id))
        return [row.as_profile() for row in rows]

    def create(self, profile: FarmerProfile) -> FarmerProfile:
        self.session.add(FarmerRow(farmer_id=profile.farmer_id, profile=profile.model_dump(mode="json")))
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise ValueError("Farmer ID already exists") from error
        return profile

    def update(self, farmer_id: str, profile: FarmerProfile) -> FarmerProfile:
        if profile.farmer_id != farmer_id:
            raise ValueError("Farmer ID in URL and body must match")
        row = self.session.get(FarmerRow, farmer_id)
        if row is None:
            raise LookupError("Farmer not found")
        row.profile = profile.model_dump(mode="json")
        self.session.commit()
        return profile
