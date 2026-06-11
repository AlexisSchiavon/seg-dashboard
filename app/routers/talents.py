from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Talent, TalentProduct
from app.schemas.talent import (
    TalentCreate,
    TalentProductCreate,
    TalentProductRead,
    TalentRead,
    TalentUpdate,
)

router = APIRouter(
    prefix="/talents",
    tags=["talents"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[TalentRead])
def list_talents(db: Session = Depends(get_db)):
    return db.query(Talent).all()


@router.post("", response_model=TalentRead, status_code=status.HTTP_201_CREATED)
def create_talent(payload: TalentCreate, db: Session = Depends(get_db)):
    talent = Talent(**payload.model_dump())
    db.add(talent)
    db.commit()
    db.refresh(talent)
    return talent


@router.patch("/{talent_id}", response_model=TalentRead)
def update_talent(talent_id: int, payload: TalentUpdate, db: Session = Depends(get_db)):
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talent not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(talent, field, value)

    db.commit()
    db.refresh(talent)
    return talent


@router.get("/{talent_id}/products", response_model=list[TalentProductRead])
def list_talent_products(talent_id: int, db: Session = Depends(get_db)):
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talent not found")

    return talent.products


@router.post(
    "/{talent_id}/products",
    response_model=TalentProductRead,
    status_code=status.HTTP_201_CREATED,
)
def add_talent_product(
    talent_id: int, payload: TalentProductCreate, db: Session = Depends(get_db)
):
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talent not found")

    product = TalentProduct(talent_id=talent_id, **payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.delete(
    "/{talent_id}/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_talent_product(talent_id: int, product_id: int, db: Session = Depends(get_db)):
    product = db.get(TalentProduct, product_id)
    if product is None or product.talent_id != talent_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    db.delete(product)
    db.commit()
