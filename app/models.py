from enum import Enum

from pydantic import BaseModel, Field, field_validator


class PostStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


class ListingStatus(str, Enum):
    """Disponibilidade comercial de um anúncio já processado."""

    ACTIVE = "active"
    PAUSED = "paused"
    SOLD = "sold"


class PublisherType(str, Enum):
    BUSINESS = "business"  # empresa/marca com nome próprio
    INDIVIDUAL = "individual"  # utilizador simples, sem marca


class PostInput(BaseModel):
    theme: str = Field(..., min_length=3, max_length=200)
    business: str = Field(..., min_length=2, max_length=120)
    category: str = Field(default="venda_informal")
    publisher_type: PublisherType = PublisherType.INDIVIDUAL
    brand_name: str | None = Field(default=None, max_length=120)
    target_audience: str = Field(..., min_length=2, max_length=200)
    objective: str = Field(..., min_length=2, max_length=200)
    tone: str = Field(..., min_length=2, max_length=60)
    language: str = Field(default="pt", min_length=2, max_length=10)
    call_to_action: str = Field(..., min_length=2, max_length=120)
    price_mt: float | None = Field(default=None, ge=0)
    currency: str = Field(default="MZN", max_length=10)
    location: str | None = Field(default=None, max_length=160)
    contact: str = Field(..., min_length=4, max_length=60)
    phone_prefix: str | None = Field(default=None, max_length=10)
    color_reference: str | None = Field(default=None, max_length=60)
    # Descrição do produto: escrita à mão, gerada pela IA a partir de uma
    # explicação, ou gerada a partir de uma fotografia real.
    description: str | None = Field(default=None, max_length=600)
    description_source: str | None = Field(default=None, max_length=20)

    @field_validator("brand_name")
    @classmethod
    def brand_required_for_business(cls, v, info):
        if info.data.get("publisher_type") == PublisherType.BUSINESS and not v:
            raise ValueError("brand_name é obrigatório quando publisher_type=business")
        return v


class UserCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    display_name: str = Field(..., min_length=2, max_length=80)

    @field_validator("email")
    @classmethod
    def email_basic_shape(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("email inválido")
        return v


class UserLogin(BaseModel):
    email: str
    password: str


class BusinessInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    category: str
    description: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=160)
    contact: str = Field(..., min_length=4, max_length=60)
    phone_prefix: str | None = Field(default=None, max_length=10)


class PostRecord(BaseModel):
    post_id: str
    status: PostStatus
    listing_status: ListingStatus = ListingStatus.ACTIVE
    theme: str
    business: str
    category: str
    created_at: str
    updated_at: str
    error: str | None = None
    thumbnail_key: str | None = None
