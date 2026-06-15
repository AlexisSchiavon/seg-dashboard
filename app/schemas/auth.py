from pydantic import BaseModel, EmailStr


class TokenResponse(BaseModel):
    status: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    email: EmailStr

    model_config = {"from_attributes": True}
