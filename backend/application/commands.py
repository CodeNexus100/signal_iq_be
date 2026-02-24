from abc import ABC, abstractmethod
from typing import Any, Optional
from backend.domain.models import IntersectionMode, SignalUpdate, SignalState

class Command(ABC):
    @abstractmethod
    def execute(self, kernel: Any):
        pass

class UpdateSignalCommand(Command):
    def __init__(self, intersection_id: str, updates: SignalUpdate):
        self.intersection_id = intersection_id
        self.updates = updates

    def execute(self, kernel: Any):
        intersection = kernel.state.intersections.get(self.intersection_id)
        if intersection:
            if self.updates.nsGreenTime is not None:
                intersection.nsGreenTime = self.updates.nsGreenTime
            if self.updates.ewGreenTime is not None:
                intersection.ewGreenTime = self.updates.ewGreenTime
            if self.updates.mode is not None:
                intersection.mode = self.updates.mode
        return intersection

class SetGlobalAIModeCommand(Command):
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def execute(self, kernel: Any):
        kernel.state.ai_enabled = self.enabled
        new_mode = IntersectionMode.AI_OPTIMIZED if self.enabled else IntersectionMode.FIXED
        for intersection in kernel.state.intersections.values():
            intersection.mode = new_mode

class SpawnVehicleCommand(Command):
    def execute(self, kernel: Any):
        # Force a spawn attempt
        kernel._spawn_vehicle()

class ApplyTrafficPatternCommand(Command):
    def __init__(self, pattern: str):
        self.pattern = pattern

    def execute(self, kernel: Any):
        ns_green = 10.0
        ew_green = 10.0

        if self.pattern == "rush_hour":
            ns_green, ew_green = 40.0, 20.0
        elif self.pattern == "night_mode":
            ns_green, ew_green = 10.0, 10.0
        elif self.pattern == "event":
            ns_green, ew_green = 35.0, 35.0
        elif self.pattern == "holiday":
            ns_green, ew_green = 20.0, 20.0

        for intersection in kernel.state.intersections.values():
            intersection.nsGreenTime = float(ns_green)
            intersection.ewGreenTime = float(ew_green)
            # Reset timer based on current active phase
            if intersection.nsSignal in [SignalState.GREEN, SignalState.YELLOW]:
                 intersection.timer = float(ns_green)
            else:
                 intersection.timer = float(ew_green)

class StartEmergencyCommand(Command):
    def execute(self, kernel: Any):
        kernel.start_emergency()

class StopEmergencyCommand(Command):
    def execute(self, kernel: Any):
        kernel.stop_emergency()
