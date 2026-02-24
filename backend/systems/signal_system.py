from typing import List
from backend.domain.models import Intersection, SignalState, IntersectionMode
from backend.domain import config

class SignalSystem:
    def update(self, intersections: List[Intersection], dt: float):
        for intersection in intersections:
            if intersection.mode not in [IntersectionMode.FIXED, IntersectionMode.AI_OPTIMIZED, IntersectionMode.MANUAL]:
                continue

            intersection.timer -= dt
            if intersection.timer <= 0:
                self._switch_signal_phase(intersection)

    def _switch_signal_phase(self, intersection: Intersection):
        if intersection.nsSignal == SignalState.GREEN:
            intersection.nsSignal = SignalState.YELLOW
            intersection.timer = config.YELLOW_TIME
        elif intersection.nsSignal == SignalState.YELLOW:
            intersection.nsSignal = SignalState.RED
            intersection.ewSignal = SignalState.GREEN
            intersection.timer = intersection.ewGreenTime
        elif intersection.ewSignal == SignalState.GREEN:
            intersection.ewSignal = SignalState.YELLOW
            intersection.timer = config.YELLOW_TIME
        elif intersection.ewSignal == SignalState.YELLOW:
            intersection.ewSignal = SignalState.RED
            intersection.nsSignal = SignalState.GREEN
            intersection.timer = intersection.nsGreenTime
        elif intersection.nsSignal == SignalState.RED and intersection.ewSignal == SignalState.RED:
             intersection.nsSignal = SignalState.GREEN
             intersection.timer = intersection.nsGreenTime
