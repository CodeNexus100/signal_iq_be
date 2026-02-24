from abc import ABC, abstractmethod
from typing import Any

class Controller(ABC):
    @abstractmethod
    def run_tick(self, state: Any, dt: float):
        pass
