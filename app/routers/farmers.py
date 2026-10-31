from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.repository import FarmerRepository
from app.schemas import FarmerProfile

router = APIRouter(prefix="/farmers", tags=["farmers"])


@router.get("", response_model=list[FarmerProfile])
def list_farmers(session: Session = Depends(get_session)):
    return FarmerRepository(session).list()


@router.get("/{farmer_id}", response_model=FarmerProfile)
def get_farmer(farmer_id: str, session: Session = Depends(get_session)):
    profile = FarmerRepository(session).get(farmer_id)
    if profile is None:
        raise HTTPException(404, "Farmer not found")
    return profile


@router.post("", status_code=201, response_model=FarmerProfile)
def create_farmer(profile: FarmerProfile, session: Session = Depends(get_session)):
    try:
        return FarmerRepository(session).create(profile)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.put("/{farmer_id}", response_model=FarmerProfile)
def update_farmer(farmer_id: str, profile: FarmerProfile, session: Session = Depends(get_session)):
    try:
        return FarmerRepository(session).update(farmer_id, profile)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
