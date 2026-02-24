import random
from typing import Dict, List, Optional
from backend.domain.models import (
    Intersection, Vehicle, EmergencyVehicle, SignalState, IntersectionMode, GridState, RoadOverview, ZoneOverview, GridOverview
)
from backend.domain.state import SimulationState
from backend.kernel.command_queue import CommandQueue
from backend.domain import config

class SimulationKernel:
    def __init__(self):
        self.state = SimulationState()
        self.dt = 0.05
        self.command_queue = CommandQueue()
        self.initialized = False
        self._vehicle_lane_cache: Dict[str, List[Vehicle]] = {}

    def initialize(self, seed: int = 42):
        self.state.tick_id = 0
        self.state.time = 0.0
        random.seed(seed)
        self._initialize_grid()
        self._initialize_vehicles()
        self.initialized = True
        print(f"Kernel Initialized (Seed: {seed})")

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
        if len(self.state.vehicles) >= config.MAX_VEHICLES: return
        is_horizontal = random.choice([True, False])
        lane_idx = random.randint(0, 4)
        lane_id = f"H{lane_idx}" if is_horizontal else f"V{lane_idx}"
        direction = random.choice(["east", "west"]) if is_horizontal else random.choice(["north", "south"])

        vehicle = Vehicle(
            id=f"v-{self.state.tick_id}-{random.randint(100,999)}",
            laneId=lane_id,
            laneType="horizontal" if is_horizontal else "vertical",
            direction=direction,
            position=random.uniform(0, 500),
            speed=random.uniform(config.MIN_SPEED, config.MAX_SPEED),
            target_speed=random.uniform(config.MIN_SPEED, config.MAX_SPEED),
            type="car"
        )
        self.state.vehicles.append(vehicle)

    def queue_command(self, command):
        self.command_queue.add(command)

    def run_tick(self):
        if not self.initialized: self.initialize()

        # 1. Process Commands
        commands = self.command_queue.pop_all()
        while commands:
            cmd = commands.popleft()
            cmd.execute(self)

        # 2. Logic
        self._update_signals(self.dt)
        self._update_vehicles(self.dt)
        if self.state.emergency_vehicle and self.state.emergency_vehicle.active:
            self._update_emergency_vehicle(self.dt)

        # 3. Time Advance
        self.state.time += self.dt
        self.state.tick_id += 1

        # 4. Spawning
        if len(self.state.vehicles) < config.MIN_SPAWN_VEHICLES and random.random() < (config.SPAWN_CHANCE * self.dt):
             if random.random() < config.SPAWN_CHANCE:
                self._spawn_vehicle()

    def _update_signals(self, dt):
        for intersection in self.state.intersections.values():
            if intersection.mode not in [IntersectionMode.FIXED, IntersectionMode.AI_OPTIMIZED, IntersectionMode.MANUAL]: continue
            intersection.timer -= dt
            if intersection.timer <= 0: self._switch_signal_phase(intersection)

    def _switch_signal_phase(self, intersection):
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

    def _update_vehicles(self, dt):
        self._vehicle_lane_cache = {}
        for v in self.state.vehicles:
            if v.laneId not in self._vehicle_lane_cache: self._vehicle_lane_cache[v.laneId] = []
            self._vehicle_lane_cache[v.laneId].append(v)

        for lane_id, lane_vehicles in self._vehicle_lane_cache.items():
            direction_groups = {}
            for v in lane_vehicles:
                if v.direction not in direction_groups: direction_groups[v.direction] = []
                direction_groups[v.direction].append(v)

            for direction, vehicles in direction_groups.items():
                if direction in ["east", "south"]: vehicles.sort(key=lambda v: v.position, reverse=True)
                else: vehicles.sort(key=lambda v: v.position)

                for i, v in enumerate(vehicles):
                    self._update_single_vehicle(v, i, vehicles, direction, dt)

                    # Respawn Logic
                    if v.position > config.GRID_BOUNDS_MAX or v.position < config.GRID_BOUNDS_MIN:
                         if v in self.state.vehicles:
                            self.state.vehicles.remove(v)

    def _update_single_vehicle(self, v, idx, lane_group, direction, dt):
        target_speed = v.target_speed
        stop_pos = -1.0

        upcoming_int, dist_to_int = self._get_upcoming_intersection_info(v)

        if upcoming_int:
            should_stop = False
            if "H" in v.laneId:
                if upcoming_int.ewSignal in [SignalState.RED, SignalState.YELLOW]: should_stop = True
            else:
                if upcoming_int.nsSignal in [SignalState.RED, SignalState.YELLOW]: should_stop = True

            if should_stop:
                center_pos = self._get_intersection_pos(v, upcoming_int)
                if direction in ["east", "south"]:
                    stop_pos = center_pos - config.STOP_OFFSET
                    if v.position > center_pos: stop_pos = -1.0
                else:
                    stop_pos = center_pos + config.STOP_OFFSET
                    if v.position < center_pos: stop_pos = -1.0

        if idx > 0:
            lead_vehicle = lane_group[idx-1]
            if direction in ["east", "south"]:
                lead_stop_pos = lead_vehicle.position - config.MIN_GAP
                if stop_pos == -1.0 or lead_stop_pos < stop_pos: stop_pos = lead_stop_pos
            else:
                lead_stop_pos = lead_vehicle.position + config.MIN_GAP
                if stop_pos == -1.0 or lead_stop_pos > stop_pos: stop_pos = lead_stop_pos

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

    def _get_upcoming_intersection_info(self, v):
        try: idx = int(v.laneId[1:])
        except: return None, 9999.0

        if v.laneType == "horizontal":
            row = idx
            target_col = -1
            dist = 9999.0
            for col in range(5):
                intersection_pos = col * config.INTERSECTION_SPACING
                if v.direction == "east":
                     if intersection_pos > v.position:
                         d = intersection_pos - v.position
                         if d < dist:
                             dist = d
                             target_col = col
                else:
                     if intersection_pos < v.position:
                         d = v.position - intersection_pos
                         if d < dist:
                             dist = d
                             target_col = col
            if target_col != -1 and dist < config.INTERSECTION_SPACING:
                 iid = f"I-{100 + (row * 5) + target_col + 1}"
                 return self.state.intersections.get(iid), dist
        else:
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
                else:
                     if intersection_pos < v.position:
                         d = v.position - intersection_pos
                         if d < dist:
                             dist = d
                             target_row = row
            if target_row != -1 and dist < config.INTERSECTION_SPACING:
                 iid = f"I-{100 + (target_row * 5) + col + 1}"
                 return self.state.intersections.get(iid), dist
        return None, 9999.0

    def _get_intersection_pos(self, v, intersection):
        try:
            idx = int(intersection.id.split("-")[1]) - 101
            row = idx // 5
            col = idx % 5
            if v.laneType == "horizontal": return float(col * config.INTERSECTION_SPACING)
            else: return float(row * config.INTERSECTION_SPACING)
        except: return 0.0

    def _update_emergency_vehicle(self, dt):
        pass # Stub for Phase 1

    def start_emergency(self): pass
    def stop_emergency(self): pass

    def get_state(self) -> GridState:
        return GridState(
            intersections=list(self.state.intersections.values()),
            vehicles=self.state.vehicles,
            emergency=self.state.emergency_vehicle
        )

    def get_intersection_details(self, intersection_id: str):
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
            "flowRate": 500,
            "pedestrianDemand": "Low",
            "aiEnabled": (intersection.mode == IntersectionMode.AI_OPTIMIZED)
        }

    def get_grid_overview(self):
        roads = []
        all_lanes = [f"H{i}" for i in range(5)] + [f"V{i}" for i in range(5)]
        lane_congestions = {}
        for lane_id in all_lanes:
            vehicles = self._vehicle_lane_cache.get(lane_id, [])
            count = len(vehicles)
            congestion = min(1.0, count / 3.0)
            lane_congestions[lane_id] = congestion
            status = "optimal"
            if congestion >= 0.75: status = "congested"
            elif congestion >= 0.5: status = "moderate"
            roads.append(RoadOverview(laneId=lane_id, congestion=round(congestion, 2), flow=status))

        zones_map = {
            "North Industrial": ["H0", "H1", "V0", "V4"],
            "Central District": ["H2", "H3", "V2", "V3"],
            "West Harbor": ["V0", "V1", "H4"]
        }
        zones = []
        for name, lanes in zones_map.items():
            total_load = sum(lane_congestions.get(l, 0.0) for l in lanes)
            avg_load = total_load / max(1, len(lanes))
            status = "optimal"
            if avg_load >= 0.75: status = "congested"
            elif avg_load >= 0.5: status = "moderate"
            zones.append(ZoneOverview(name=name, load=round(avg_load, 2), status=status))

        return GridOverview(roads=roads, zones=zones)
