from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class UploadPreviewResponse(BaseModel):
    headers: List[str]
    rowCount: int
    missingRequiredColumns: List[str]
    sample: List[Dict[str, Any]]


class WeightConfig(BaseModel):
    texas_max_lbs: int = Field(52000, ge=40000, le=100000)
    texas_min_lbs: int = Field(47000, ge=40000, le=100000)
    other_max_lbs: int = Field(48000, ge=40000, le=100000)
    other_min_lbs: int = Field(44000, ge=40000, le=100000)

    @classmethod
    def default(cls) -> "WeightConfig":
        return cls(
            texas_max_lbs=52000,
            texas_min_lbs=47000,
            other_max_lbs=48000,
            other_min_lbs=44000,
        )


def _default_weight_config() -> dict:
    return {
        "texas_max_lbs": 52000,
        "texas_min_lbs": 47000,
        "other_max_lbs": 48000,
        "other_min_lbs": 44000,
    }


class OptimizeRequest(BaseModel):
    weightConfig: WeightConfig = Field(default_factory=WeightConfig.default)


class TruckSummary(BaseModel):
    truckNumber: int
    customerName: str
    customerAddress: Optional[str] = None
    customerCity: str
    customerState: str
    # Optional grouping metadata coming from input data
    zone: Optional[str] = None
    route: Optional[str] = None
    totalWeight: float
    minWeight: int
    maxWeight: int
    totalOrders: int
    totalLines: int
    totalPieces: int
    maxWidth: float
    percentOverwidth: float
    containsLate: bool
    priorityBucket: str  # Late, NearDue, WithinWindow, NotDue


class LineAssignment(BaseModel):
    truckNumber: int
    so: str
    line: str
    customerName: str
    customerAddress: Optional[str] = None
    customerCity: str
    customerState: str
    piecesOnTransport: int
    totalReadyPieces: int
    weightPerPiece: float
    totalWeight: float
    width: float
    isOverwidth: bool
    isLate: bool
    earliestDue: Optional[str] = None
    latestDue: Optional[str] = None


class OptimizeResponse(BaseModel):
    trucks: List[TruckSummary]
    assignments: List[LineAssignment]
    sections: Dict[str, List[int]]  # bucket -> list of truckNumbers


class CombineTrucksRequest(BaseModel):
    truckIds: List[int] = Field(...,
                                description="List of truck numbers to combine")
    lineIds: List[str] = Field(
        ..., description="List of line identifiers to combine (format: truckNumber-SO-Line)")
    weightConfig: WeightConfig = Field(default_factory=WeightConfig.default)


class CombineTrucksResponse(BaseModel):
    success: bool
    message: str
    newTruck: Optional[TruckSummary] = None
    updatedAssignments: List[LineAssignment]
    removedTruckIds: List[int]
