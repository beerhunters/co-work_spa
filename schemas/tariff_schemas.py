from pydantic import BaseModel


class TariffBase(BaseModel):
    id: int
    name: str
    description: str
    price: float
    purpose: str = None
    service_id: int = None
    is_active: bool

    class Config:
        from_attributes = True


class TariffCreate(BaseModel):
    name: str
    description: str
    price: float
    purpose: str = None
    service_id: int = None
    is_active: bool = True


class TariffUpdate(BaseModel):
    name: str = None
    description: str = None
    price: float = None
    purpose: str = None
    service_id: int = None
    is_active: bool = None
