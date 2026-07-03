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
    # Dérivé du token (utilisateur authentifié) côté service ; le front n'a pas
    # à l'envoyer. Optionnel pour éviter un 422 quand le formulaire ne le fournit pas.
    user_id: Optional[int] = None


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
