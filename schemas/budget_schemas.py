from pydantic import BaseModel


class RevenueStreamInitial(BaseModel):
    name: str
    estimated_price: float = 0.0
    estimated_volume: int = 0
    category: str = "revenue"
