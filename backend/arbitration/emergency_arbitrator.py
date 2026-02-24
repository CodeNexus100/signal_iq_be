from typing import List, Optional
from backend.domain.models import EmergencyVehicle, Intersection
from backend.domain.graph import RoadNetwork

class EmergencyArbitrator:
    def __init__(self, road_network: RoadNetwork):
        self.road_network = road_network
        self.active_emergencies: List[EmergencyVehicle] = []

    def register_emergency(self, vehicle: EmergencyVehicle):
        if vehicle not in self.active_emergencies:
            self.active_emergencies.append(vehicle)

    def run_tick(self, intersections: List[Intersection], dt: float):
        # Iterate active emergencies
        # Calculate distance to next intersection
        # Issue override commands if needed
        # This logic was previously in `_update_emergency_vehicle`
        pass
