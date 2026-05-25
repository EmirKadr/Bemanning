from pydantic import BaseModel
from typing import List


class DaySummary(BaseModel):
    day: int
    day_name: str
    customers_assigned: int
    customers_total: int
    locations_used: int
    locations_total: int
    pallet_used: float
    pallet_total: float


class AssignmentResult(BaseModel):
    success: bool
    summaries: List[DaySummary]
    warnings: List[str]
