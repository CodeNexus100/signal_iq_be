from typing import Any
from backend.controllers.base import Controller
from backend.domain.models import IntersectionMode

class FixedController(Controller):
    def run_tick(self, state: Any, dt: float):
        # In a real fixed controller, we might enforce offsets or specific plans.
        # For now, the SignalSystem handles the timer decrement based on `nsGreenTime`.
        # This controller might adjust those green times periodically if scheduled.
        pass

class HeuristicController(Controller):
    def run_tick(self, state: Any, dt: float):
        # Check density and adjust timings if mode is AI_OPTIMIZED
        # This logic was previously in `_optimize_signals` inside engine.
        pass
