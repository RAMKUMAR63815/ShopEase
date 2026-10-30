from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserProfile
from app.schemas import (
    ProfileCreate,
    ProfileResponse,
    ProfileUpdate
)
from app.security import CurrentUserId


router = APIRouter(prefix="/users", tags=["Users"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/me", response_model=ProfileResponse,
             status_code=status.HTTP_201_CREATED)
def create_profile(
    profile_data: ProfileCreate,
    user_id: CurrentUserId,
    db: DbSession
):
    existing_profile = db.scalar(
        select(UserProfile).where(
            UserProfile.auth_user_id == user_id
        )
    )

    if existing_profile:
        raise HTTPException(
            status_code=409,
            detail="Profile already exists"
        )

    profile = UserProfile(
        auth_user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        phone=profile_data.phone
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile


@router.get("/me", response_model=ProfileResponse)
def get_profile(
    user_id: CurrentUserId,
    db: DbSession
):
    profile = db.scalar(
        select(UserProfile).where(
            UserProfile.auth_user_id == user_id
        )
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    return profile


@router.patch("/me", response_model=ProfileResponse)
def update_profile(
    profile_data: ProfileUpdate,
    user_id: CurrentUserId,
    db: DbSession
):
    profile = db.scalar(
        select(UserProfile).where(
            UserProfile.auth_user_id == user_id
        )
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    update_data = profile_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return profile