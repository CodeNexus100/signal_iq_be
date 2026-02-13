from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class SignalState(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"

class IntersectionMode(str, Enum):
    FIXED = "FIXED"
    MANUAL = "MANUAL"
    AI_OPTIMIZED = "AI_OPTIMIZED"
    EMERGENCY_OVERRIDE = "EMERGENCY_OVERRIDE"

class Intersection(BaseModel):
    id: str
    nsSignal: SignalState
    ewSignal: SignalState
    timer: float
    mode: IntersectionMode
    nsGreenTime: float = 10.0
    ewGreenTime: float = 10.0

class SignalUpdate(BaseModel):
    nsGreenTime: Optional[float] = None
    ewGreenTime: Optional[float] = None
    mode: Optional[IntersectionMode] = None

class AIToggle(BaseModel):
    enabled: bool

class Vehicle(BaseModel):
    id: str
    laneId: str
    laneType: str  # "horizontal" or "vertical"
    direction: str # "north", "south", "east", "west"
    position: float
    speed: float
    type: str = "car"

class GridState(BaseModel):
    intersections: List[Intersection]
    vehicles: List[Vehicle]
