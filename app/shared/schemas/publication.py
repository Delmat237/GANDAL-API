from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional


PublicationStatus = Literal["draft", "published", "archived"]


class PublicationBase(BaseModel):
    nom: str
    status: PublicationStatus = "draft"
    lien: Optional[str] = None
    description: Optional[str] = None
    photo: Optional[str] = None


class PublicationCreate(PublicationBase):
    user_id: int


class PublicationUpdate(BaseModel):
    nom: Optional[str] = None
    lien: Optional[str] = None
    description: Optional[str] = None
    photo: Optional[str] = None
    status: Optional[PublicationStatus] = None


class PublicationRead(PublicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
