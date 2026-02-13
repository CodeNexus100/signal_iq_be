import random
import time
from typing import Dict, List, Optional
from .models import Intersection, IntersectionMode, SignalState, Vehicle, GridState, SignalUpdate

class SimulationEngine:
    def __init__(self):
        self.intersections: Dict[str, Intersection] = {}
        self.vehicles: List[Vehicle] = []
        self._initialize_grid()
        self._initialize_vehicles()

    def _initialize_grid(self):
        # 5x5 Grid: I-101 to I-125
        for i in range(1, 26):
            intersection_id = f"I-{100 + i}"
            # Randomly start some signals as GREEN/RED to vary the grid
            start_ns = random.choice([SignalState.GREEN, SignalState.RED])
            start_ew = SignalState.RED if start_ns == SignalState.GREEN else SignalState.GREEN
            
            self.intersections[intersection_id] = Intersection(
                id=intersection_id,
                nsSignal=start_ns,
                ewSignal=start_ew,
                timer=random.randint(5, 10), # Random start timer
                mode=IntersectionMode.FIXED,
                nsGreenTime=10.0,
                ewGreenTime=10.0
            )

    def _initialize_vehicles(self):
        # Spawn some initial vehicles
        for i in range(10):
            self._spawn_vehicle()

    def _spawn_vehicle(self):
        if len(self.vehicles) >= 50: # Limit max vehicles
            return

        is_horizontal = random.choice([True, False])
        lane_idx = random.randint(0, 4)
        
        if is_horizontal:
            lane_id = f"H{lane_idx}"
            direction = random.choice(["east", "west"])
            lane_type = "horizontal"
        else:
            lane_id = f"V{lane_idx}"
            direction = random.choice(["north", "south"])
            lane_type = "vertical"

        vehicle = Vehicle(
            id=f"v-{int(time.time() * 1000)}-{random.randint(100,999)}",
            laneId=lane_id,
            laneType=lane_type,
            direction=direction,
            position=random.uniform(0, 500), # Increased range to cover whole grid
            speed=random.uniform(5, 15),
            target_speed=random.uniform(5, 15),
            type="car"
        )
        self.vehicles.append(vehicle)

    def update(self, dt: float):
        self._update_signals(dt)
        self._update_vehicles(dt)

    def _update_signals(self, dt: float):
        for intersection in self.intersections.values():
            if intersection.mode not in [IntersectionMode.FIXED, IntersectionMode.AI_OPTIMIZED, IntersectionMode.MANUAL]:
                continue
                
            intersection.timer -= dt
            if intersection.timer <= 0:
                self._switch_signal_phase(intersection)

    def _calculate_density(self, intersection_id: str):
        # Map I-101 (index 1) to row 0, col 0
        # I-125 (index 25) to row 4, col 4
        try:
            # simple lookup
            idx = int(intersection_id.split("-")[1]) - 101 # 0 to 24
            row = idx // 5 # 0-4
            col = idx % 5  # 0-4
            
            h_lane_id = f"H{row}"
            v_lane_id = f"V{col}"

            # Approx position of intersection on lane
            # For H lane, intersection is at V-col position (col * 100)
            # For V lane, intersection is at H-row position (row * 100)
            intersection_h_pos = col * 100.0
            intersection_v_pos = row * 100.0
            
            radius = 30.0 # Detection radius
            
            ns_load = 0
            ew_load = 0
            
            for v in self.vehicles:
                if v.laneId == h_lane_id:
                    if abs(v.position - intersection_h_pos) < radius:
                        # Check if approaching? For prototype, simple proximity load
                        ew_load += 1
                elif v.laneId == v_lane_id:
                     if abs(v.position - intersection_v_pos) < radius:
                        ns_load += 1
                        
            return ns_load, ew_load

        except Exception:
            return 0, 0

    def _optimize_signals(self, intersection: Intersection):
        ns_load, ew_load = self._calculate_density(intersection.id)
        
        # Prototype optimization rule
        # Adjust green times based on load difference
        # We modify the *stored* green times so next cycle uses them
        
        step = 5.0
        min_green = 10.0
        max_green = 60.0
        
        if ns_load > ew_load:
            intersection.nsGreenTime = min(max_green, intersection.nsGreenTime + step)
            intersection.ewGreenTime = max(min_green, intersection.ewGreenTime - step)
        elif ew_load > ns_load:
             intersection.ewGreenTime = min(max_green, intersection.ewGreenTime + step)
             intersection.nsGreenTime = max(min_green, intersection.nsGreenTime - step)
        # Else equal load, keep status quo or drift to neutral? Keep status quo for now.

    def _switch_signal_phase(self, intersection: Intersection):
        # If AI mode, run optimization before picking next timer
        if intersection.mode == IntersectionMode.AI_OPTIMIZED:
            self._optimize_signals(intersection)

        # Cycle: GREEN -> YELLOW -> RED -> GREEN
        
        if intersection.nsSignal == SignalState.GREEN:
            intersection.nsSignal = SignalState.YELLOW
            intersection.timer = 3.0
        elif intersection.nsSignal == SignalState.YELLOW:
            intersection.nsSignal = SignalState.RED
            intersection.ewSignal = SignalState.GREEN
            intersection.timer = intersection.ewGreenTime
        elif intersection.ewSignal == SignalState.GREEN:
            intersection.ewSignal = SignalState.YELLOW
            intersection.timer = 3.0
        elif intersection.ewSignal == SignalState.YELLOW:
            intersection.ewSignal = SignalState.RED
            intersection.nsSignal = SignalState.GREEN
            intersection.timer = intersection.nsGreenTime
        elif intersection.nsSignal == SignalState.RED and intersection.ewSignal == SignalState.RED:
             intersection.nsSignal = SignalState.GREEN
             intersection.timer = intersection.nsGreenTime

    def _update_vehicles(self, dt: float):
        for v in self.vehicles:
            # Check for stop conditions
            should_stop = self._check_stop_condition(v)
            
            if should_stop:
                v.speed = 0.0
            else:
                # Accelerate back to target speed
                # Simple instant acceleration for prototype
                v.speed = v.target_speed

            move_amount = v.speed * dt
            
            if v.direction in ["east", "south"]:
                v.position += move_amount
            else:
                v.position -= move_amount

            # Respawn if out of bounds
            if v.position > 600 or v.position < -100: # Extended range for 5x5 grid
                self.vehicles.remove(v)
                self._spawn_vehicle()
        
        if len(self.vehicles) < 20: 
            if random.random() < 0.1: 
                self._spawn_vehicle()

    def _check_stop_condition(self, v: Vehicle) -> bool:
        # Determine upcoming intersection
        # Lane ID format: H{row} or V{col}
        try:
             idx = int(v.laneId[1:])
        except:
             return False

        if v.laneType == "horizontal":
            row = idx
            # Determine intersection col based on position and direction
            # Intersections are at Col * 100
            # If moving East (increasing pos), look for next (Col * 100) > valid pos
            # If moving West (decreasing pos), look for next (Col * 100) < valid pos
            
            target_col = -1
            dist = 9999.0
            
            for col in range(5):
                intersection_pos = col * 100.0
                if v.direction == "east":
                     if intersection_pos > v.position:
                         d = intersection_pos - v.position
                         if d < dist:
                             dist = d
                             target_col = col
                else: # west
                     if intersection_pos < v.position:
                         d = v.position - intersection_pos
                         if d < dist:
                             dist = d
                             target_col = col
            
            if target_col != -1 and dist < 25.0: # Stop threshold
                 # Found intersection
                 intersection_id = f"I-{100 + (row * 5) + target_col + 1}"
                 intersection = self.intersections.get(intersection_id)
                 if intersection:
                     # Check EW Signal for Horizontal Lane
                     if intersection.ewSignal == SignalState.RED or intersection.ewSignal == SignalState.YELLOW:
                         return True
                         
        else: # vertical
            col = idx
            target_row = -1
            dist = 9999.0
            
            for row in range(5):
                intersection_pos = row * 100.0 # Intersection V pos is Row * 100
                if v.direction == "south": # increasing pos
                     if intersection_pos > v.position:
                         d = intersection_pos - v.position
                         if d < dist:
                             dist = d
                             target_row = row
                else: # north
                     if intersection_pos < v.position:
                         d = v.position - intersection_pos
                         if d < dist:
                             dist = d
                             target_row = row
            
            if target_row != -1 and dist < 25.0:
                 intersection_id = f"I-{100 + (target_row * 5) + col + 1}"
                 intersection = self.intersections.get(intersection_id)
                 if intersection:
                     # Check NS Signal for Vertical Lane
                     if intersection.nsSignal == SignalState.RED or intersection.nsSignal == SignalState.YELLOW:
                         return True

        return False

    def get_state(self) -> GridState:
        return GridState(
            intersections=list(self.intersections.values()),
            vehicles=self.vehicles
        )

    def get_intersection(self, intersection_id: str) -> Optional[Intersection]:
        return self.intersections.get(intersection_id)

    def update_signal_timing(self, intersection_id: str, updates: SignalUpdate):
        intersection = self.intersections.get(intersection_id)
        if not intersection:
            return None
        
        if updates.nsGreenTime is not None:
            intersection.nsGreenTime = updates.nsGreenTime
        if updates.ewGreenTime is not None:
            intersection.ewGreenTime = updates.ewGreenTime
        if updates.mode is not None:
            intersection.mode = updates.mode
        
        return intersection

    def set_ai_mode(self, enabled: bool):
        new_mode = IntersectionMode.AI_OPTIMIZED if enabled else IntersectionMode.FIXED
        for intersection in self.intersections.values():
            intersection.mode = new_mode

# Global instance
simulation_engine = SimulationEngine()
