from typing import Any, Dict
from backend.domain.state import SimulationState

class SnapshotBuilder:
    def build(self, state: SimulationState) -> Dict[str, Any]:
        return {
            "tick": state.tick_id,
            "time": state.time,
            "vehicles": [
                {
                    "id": v.id,
                    "pos": v.position, # To be derived from edge progress
                    "edge": v.edge_id
                }
                for v in state.vehicles
            ],
            "intersections": [
                {
                    "id": i.id,
                    "state": i.nsSignal
                }
                for i in state.intersections.values()
            ]
        }
