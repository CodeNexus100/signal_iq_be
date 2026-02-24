import random
from typing import List, Dict, Optional, Deque
from collections import deque

from backend.domain.models import (
    Intersection, Vehicle, EmergencyVehicle, SignalState, IntersectionMode,
    SignalUpdate, AIStatus, AIPrediction, AIRecommendation, GridState,
    RoadOverview, ZoneOverview, GridOverview
)
from backend.domain.state import SimulationState
from backend.application.commands import Command

# Use config from domain
from backend.domain import config

class SimulationKernel:
    def __init__(self):
        self.state = SimulationState()
        self.dt = 0.05 # Fixed timestep
        self.command_queue: Deque[Command] = deque()
        self.initialized = False

        # Internal Cache for Optimization (similar to original engine)
        self._vehicle_lane_cache: Dict[str, List[Vehicle]] = {}

    def initialize(self, seed: int = 42):
        self.state.tick_id = 0
        self.state.time = 0.0
        random.seed(seed)
        self._initialize_grid()
        self._initialize_vehicles()
        self.initialized = True
        print(f"Simulation Kernel Initialized with Seed {seed}")

    def _initialize_grid(self):
        self.state.intersections = {}
        for i in range(1, 26):
            intersection_id = f"I-{100 + i}"
            start_ns = random.choice([SignalState.GREEN, SignalState.RED])
            start_ew = SignalState.RED if start_ns == SignalState.GREEN else SignalState.GREEN

            self.state.intersections[intersection_id] = Intersection(
                id=intersection_id,
                nsSignal=start_ns,
                ewSignal=start_ew,
                timer=float(random.randint(5, 10)),
                mode=IntersectionMode.FIXED,
                nsGreenTime=config.MIN_GREEN_TIME,
                ewGreenTime=config.MIN_GREEN_TIME
            )

    def _initialize_vehicles(self):
        self.state.vehicles = []
        for i in range(10):
            self._spawn_vehicle()

    def _spawn_vehicle(self):
        if len(self.state.vehicles) >= config.MAX_VEHICLES:
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
            id=f"v-{self.state.tick_id}-{random.randint(100,999)}",
            laneId=lane_id,
            laneType=lane_type,
            direction=direction,
            position=random.uniform(0, 500),
            speed=random.uniform(config.MIN_SPEED, config.MAX_SPEED),
            target_speed=random.uniform(config.MIN_SPEED, config.MAX_SPEED),
            type="car"
        )
        self.state.vehicles.append(vehicle)

    def queue_command(self, command: Command):
        self.command_queue.append(command)

    def run_tick(self):
        if not self.initialized:
            self.initialize()

        # 1. Consume Commands
        while self.command_queue:
            cmd = self.command_queue.popleft()
            cmd.execute(self)

        # 2. Update Physics & Signals
        self._update_signals(self.dt)
        self._update_vehicles(self.dt)

        if self.state.emergency_vehicle and self.state.emergency_vehicle.active:
            self._update_emergency_vehicle(self.dt)

        # 3. Advance Time
        self.state.time += self.dt
        self.state.tick_id += 1

        # 4. Spawn Logic
        if len(self.state.vehicles) < config.MIN_SPAWN_VEHICLES and random.random() < (config.SPAWN_CHANCE * self.dt): # Scale chance by dt? Or keeps same?
            # Original code: if random() < config.SPAWN_CHANCE.
            # Original loop was ~20Hz (dt=0.05). So chance is per tick.
            # We keep it per tick.
             if random.random() < config.SPAWN_CHANCE:
                self._spawn_vehicle()

        # 5. Future Hooks
        self._run_ml_decision_phase()
        self._collect_metrics()
        self._publish_snapshot()

    def _run_ml_decision_phase(self):
        pass # Phase 4

    def _collect_metrics(self):
        pass # Phase 6

    def _publish_snapshot(self):
        pass # Phase 7

    def _update_signals(self, dt: float):
        for intersection in self.state.intersections.values():
            if intersection.mode not in [IntersectionMode.FIXED, IntersectionMode.AI_OPTIMIZED, IntersectionMode.MANUAL]:
                continue

            intersection.timer -= dt
            if intersection.timer <= 0:
                self._switch_signal_phase(intersection)

    def _switch_signal_phase(self, intersection: Intersection):
        # Cycle: GREEN -> YELLOW -> RED -> GREEN
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

    def _update_vehicles(self, dt: float):
        # 1. Group by Lane (Rebuild cache)
        self._vehicle_lane_cache = {}
        for v in self.state.vehicles:
            if v.laneId not in self._vehicle_lane_cache:
                self._vehicle_lane_cache[v.laneId] = []
            self._vehicle_lane_cache[v.laneId].append(v)

        # 3. Process each lane
        for lane_id, lane_vehicles in self._vehicle_lane_cache.items():
            direction_groups: Dict[str, List[Vehicle]] = {}
            for v in lane_vehicles:
                if v.direction not in direction_groups:
                    direction_groups[v.direction] = []
                direction_groups[v.direction].append(v)

            for direction, vehicles in direction_groups.items():
                if direction in ["east", "south"]:
                    vehicles.sort(key=lambda v: v.position, reverse=True)
                else:
                    vehicles.sort(key=lambda v: v.position)

                for i, v in enumerate(vehicles):
                    self._update_single_vehicle(v, i, vehicles, direction, dt)

                    # Respawn bounds
                    if v.position > config.GRID_BOUNDS_MAX or v.position < config.GRID_BOUNDS_MIN:
                         if v in self.state.vehicles:
                            self.state.vehicles.remove(v)
                            # self._spawn_vehicle() # Don't spawn immediately, let the global spawn logic handle it

    def _update_single_vehicle(self, v: Vehicle, idx: int, lane_group: List[Vehicle], direction: str, dt: float):
        target_speed = v.target_speed
        stop_pos = -1.0 # No stop required flag

        # A. Check Signal
        upcoming_int, dist_to_int = self._get_upcoming_intersection_info(v)

        if upcoming_int:
            should_stop = False
            if "H" in v.laneId:
                if upcoming_int.ewSignal in [SignalState.RED, SignalState.YELLOW]:
                    should_stop = True
            else:
                if upcoming_int.nsSignal in [SignalState.RED, SignalState.YELLOW]:
                    should_stop = True

            if should_stop:
                center_pos = self._get_intersection_pos(v, upcoming_int)

                if direction in ["east", "south"]:
                    stop_pos = center_pos - config.STOP_OFFSET
                    if v.position > center_pos: stop_pos = -1.0
                else:
                    stop_pos = center_pos + config.STOP_OFFSET
                    if v.position < center_pos: stop_pos = -1.0

        # B. Check Lead Vehicle
        if idx > 0:
            lead_vehicle = lane_group[idx-1]
            if direction in ["east", "south"]:
                lead_stop_pos = lead_vehicle.position - config.MIN_GAP
                if stop_pos == -1.0 or lead_stop_pos < stop_pos:
                    stop_pos = lead_stop_pos
            else:
                lead_stop_pos = lead_vehicle.position + config.MIN_GAP
                if stop_pos == -1.0 or lead_stop_pos > stop_pos:
                    stop_pos = lead_stop_pos

        # C. Apply Physics
        if stop_pos != -1.0:
            dist_to_stop = abs(stop_pos - v.position)
            if dist_to_stop < 1.0:
                v.speed = 0.0
                v.position = stop_pos
            elif dist_to_stop < 150.0:
                safe_speed = (2 * config.DECELERATION * dist_to_stop) ** 0.5 * 0.8
                if v.speed > safe_speed:
                    required_decel = (v.speed ** 2) / (2 * dist_to_stop)
                    actual_decel = min(config.DECELERATION * 1.5, required_decel)
                    v.speed -= actual_decel * dt
                    if v.speed < 0: v.speed = 0.0
                else:
                    if v.speed < target_speed and v.speed < safe_speed * 0.9:
                            v.speed += config.ACCELERATION * dt
        else:
            if v.speed < target_speed:
                v.speed += config.ACCELERATION * dt
                if v.speed > target_speed: v.speed = target_speed

        # D. Move
        move_amount = v.speed * dt
        if direction in ["east", "south"]:
            new_pos = v.position + move_amount
            if stop_pos != -1.0 and new_pos > stop_pos:
                new_pos = stop_pos
                v.speed = 0.0
            v.position = new_pos
        else:
            new_pos = v.position - move_amount
            if stop_pos != -1.0 and new_pos < stop_pos:
                new_pos = stop_pos
                v.speed = 0.0
            v.position = new_pos


    def _get_upcoming_intersection_info(self, v: Vehicle):
        # Simplified lookup logic
        try:
             idx = int(v.laneId[1:])
        except:
             return None, 9999.0

        if v.laneType == "horizontal":
            row = idx
            target_col = -1
            dist = 9999.0

            # Find nearest intersection in direction
            # Intersections are at col * 100
            for col in range(5):
                intersection_pos = col * config.INTERSECTION_SPACING
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

            if target_col != -1 and dist < config.INTERSECTION_SPACING:
                 iid = f"I-{100 + (row * 5) + target_col + 1}"
                 return self.state.intersections.get(iid), dist

        else: # vertical
            col = idx
            target_row = -1
            dist = 9999.0
            for row in range(5):
                intersection_pos = row * config.INTERSECTION_SPACING
                if v.direction == "south":
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

            if target_row != -1 and dist < config.INTERSECTION_SPACING:
                 iid = f"I-{100 + (target_row * 5) + col + 1}"
                 return self.state.intersections.get(iid), dist

        return None, 9999.0

    def _get_intersection_pos(self, v: Vehicle, intersection: Intersection) -> float:
        try:
            idx = int(intersection.id.split("-")[1]) - 101
            row = idx // 5
            col = idx % 5
            if v.laneType == "horizontal":
                return float(col * config.INTERSECTION_SPACING)
            else:
                return float(row * config.INTERSECTION_SPACING)
        except:
            return 0.0

    # Emergency Vehicle Logic
    def start_emergency(self):
        route = ["I-101", "I-102", "I-103", "I-104", "I-105"]
        self.state.emergency_vehicle = EmergencyVehicle(
            id="EM-1",
            position=-50.0,
            laneId="H0",
            speed=35.0,
            route=route,
            active=True,
            current_target_index=0,
            type="emergency"
        )

    def stop_emergency(self):
        if self.state.emergency_vehicle:
            self.state.emergency_vehicle.active = False
            # Reset signals
            for iid in self.state.emergency_vehicle.route:
                 if iid in self.state.intersections:
                      if self.state.intersections[iid].mode == IntersectionMode.EMERGENCY_OVERRIDE:
                           self.state.intersections[iid].mode = IntersectionMode.FIXED
            self.state.emergency_vehicle = None

    def _update_emergency_vehicle(self, dt: float):
        if not self.state.emergency_vehicle: return
        ev = self.state.emergency_vehicle

        ev.position += ev.speed * dt

        if ev.current_target_index < len(ev.route):
            target_id = ev.route[ev.current_target_index]
            intersection = self.state.intersections.get(target_id)
            if intersection:
                col = (int(target_id.split("-")[1]) - 101) % 5
                target_pos = col * config.INTERSECTION_SPACING
                dist = target_pos - ev.position

                if 0 < dist < config.EMERGENCY_DETECTION_DIST:
                    if intersection.mode != IntersectionMode.EMERGENCY_OVERRIDE:
                        intersection.mode = IntersectionMode.EMERGENCY_OVERRIDE
                        intersection.ewSignal = SignalState.GREEN
                        intersection.nsSignal = SignalState.RED

                if dist < -20.0:
                    if intersection.mode == IntersectionMode.EMERGENCY_OVERRIDE:
                        intersection.mode = IntersectionMode.FIXED
                    ev.current_target_index += 1

        if ev.position > config.GRID_BOUNDS_MAX + 50.0:
            self.stop_emergency()

    # Getters for API
    def get_state(self) -> GridState:
        # Convert internal state to GridState API model
        return GridState(
            intersections=list(self.state.intersections.values()),
            vehicles=self.state.vehicles,
            emergency=self.state.emergency_vehicle
        )

    def get_intersection_details(self, intersection_id: str) -> Optional[dict]:
        intersection = self.state.intersections.get(intersection_id)
        if not intersection: return None

        phase = "All-Red"
        if intersection.nsSignal == SignalState.GREEN: phase = "NS"
        elif intersection.ewSignal == SignalState.GREEN: phase = "EW"
        elif intersection.nsSignal == SignalState.YELLOW: phase = "NS-Yellow"
        elif intersection.ewSignal == SignalState.YELLOW: phase = "EW-Yellow"

        return {
            "intersectionId": intersection.id,
            "nsGreenTime": int(intersection.nsGreenTime),
            "ewGreenTime": int(intersection.ewGreenTime),
            "currentPhase": phase,
            "timerRemaining": max(0, int(intersection.timer)),
            "flowRate": 500, # Placeholder
            "pedestrianDemand": "Low",
            "aiEnabled": (intersection.mode == IntersectionMode.AI_OPTIMIZED)
        }

    def get_grid_overview(self) -> GridOverview:
        # 1. Calculate Road Stats
        roads: List[RoadOverview] = []
        all_lanes = [f"H{i}" for i in range(5)] + [f"V{i}" for i in range(5)]
        lane_congestions = {}

        # Use cache if updated recently (here we can just use cache directly)
        for lane_id in all_lanes:
            vehicles = self._vehicle_lane_cache.get(lane_id, [])
            count = len(vehicles)
            congestion = min(1.0, count / 3.0)
            lane_congestions[lane_id] = congestion

            status = "optimal"
            if congestion >= 0.75: status = "congested"
            elif congestion >= 0.5: status = "moderate"

            roads.append(RoadOverview(laneId=lane_id, congestion=round(congestion, 2), flow=status))

        # 2. Calculate Zone Stats
        zones_map = {
            "North Industrial": ["H0", "H1", "V0", "V4"],
            "Central District": ["H2", "H3", "V2", "V3"],
            "West Harbor": ["V0", "V1", "H4"]
        }

        zones: List[ZoneOverview] = []
        for name, lanes in zones_map.items():
            total_load = 0.0
            for l in lanes:
                total_load += lane_congestions.get(l, 0.0)
            avg_load = total_load / max(1, len(lanes))

            status = "optimal"
            if avg_load >= 0.75: status = "congested"
            elif avg_load >= 0.5: status = "moderate"

            zones.append(ZoneOverview(name=name, load=round(avg_load, 2), status=status))

        return GridOverview(roads=roads, zones=zones)
