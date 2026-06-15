from pydantic import BaseModel


class TalentProductRead(BaseModel):
    id: int
    pipedrive_product_id: int | None = None

    model_config = {"from_attributes": True}


class TalentProductCreate(BaseModel):
    pipedrive_product_id: int | None = None


class TalentBase(BaseModel):
    name: str
    active: bool = True
    category: str | None = None
    photo_url: str | None = None


class TalentCreate(TalentBase):
    pass


class TalentUpdate(BaseModel):
    name: str | None = None
    active: bool | None = None
    category: str | None = None
    photo_url: str | None = None


class TalentRead(TalentBase):
    id: int
    products: list[TalentProductRead] = []

    model_config = {"from_attributes": True}
