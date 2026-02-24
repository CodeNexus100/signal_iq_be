from typing import List, Dict, Optional
from pydantic import BaseModel
from .models import Intersection, Vehicle, EmergencyVehicle

class SimulationState(BaseModel):
    tick_id: int = 0
    time: float = 0.0
    intersections: Dict[str, Intersection] = {}
    vehicles: List[Vehicle] = []
    emergency_vehicle: Optional[EmergencyVehicle] = None
    ai_enabled: bool = False

    # Random state placeholder if we were to serialize it
    # random_state: str = ""
