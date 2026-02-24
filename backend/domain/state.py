from typing import List, Dict, Optional
from pydantic import BaseModel, ConfigDict
from backend.domain.models import Intersection, Vehicle, EmergencyVehicle
from backend.domain.graph import RoadNetwork

class SimulationState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tick_id: int = 0
    time: float = 0.0
    intersections: Dict[str, Intersection] = {}
    vehicles: List[Vehicle] = []
    emergency_vehicle: Optional[EmergencyVehicle] = None
    ai_enabled: bool = False

    # Graph based structure
    road_network: Optional[RoadNetwork] = None
