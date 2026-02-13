import random
import time
from typing import Dict, List, Optional
from .models import Intersection, IntersectionMode, SignalState, Vehicle, GridState, SignalUpdate, EmergencyVehicle

class SimulationEngine:
    def __init__(self):
        self.intersections: Dict[str, Intersection] = {}
        self.vehicles: List[Vehicle] = []
        self.emergency_vehicle: Optional[EmergencyVehicle] = None
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
        if self.emergency_vehicle and self.emergency_vehicle.active:
            self._update_emergency_vehicle(dt)

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
        # 1. Group by Lane
        vehicles_by_lane: Dict[str, List[Vehicle]] = {}
        for v in self.vehicles:
            if v.laneId not in vehicles_by_lane:
                vehicles_by_lane[v.laneId] = []
            vehicles_by_lane[v.laneId].append(v)

        # 2. Physics Constants (Scaled for 100-unit grid)
        # Using 15.0 stop offset (user asked for 0.12 on 1.0 scale -> ~12.0)
        STOP_OFFSET = 20.0 
        MIN_GAP = 8.0
        ACCELERATION = 10.0 # units/s^2
        DECELERATION = 20.0 # units/s^2

        # 3. Process each lane
        for lane_id, lane_vehicles in vehicles_by_lane.items():
            # Sort vehicles
            # Horizontal (East): Increasing pos -> Sort descending (leader first)
            # Horizontal (West): Decreasing pos -> Sort ascending (leader first)
            # Vertical (South): Increasing pos -> Sort descending
            # Vertical (North): Decreasing pos -> Sort ascending
            
            is_increasing = "H" in lane_id # Assuming H lanes move East? 
            # Wait, H lanes can be East or West.
            # V lanes can be North or South.
            # I assigned direction randomly in spawn.
            # BUT laneId implies direction usually. 
            # Current spawn logic:
            # lane_idx = random.randint(0,4)
            # if random.choice([True, False]):
            #    laneId = f"H{lane_idx}", direction = random.choice(["east", "west"])
            
            # This allows opposing traffic in SAME lane ID? That's bad.
            # "H0" should probably be one direction or bi-directional with offset?
            # For this prototype, I'll assume:
            # H0, H2, H4 -> East
            # H1, H3 -> West
            # V0, V2, V4 -> South
            # V1, V3 -> North
            # Wait, I need to check spawn logic or enforce it.
            # The current spawn logic calculates direction blindly.
            # I will trust the vehicle's direction for sorting.
            
            # Actually, mixed directions in one list is chaotic.
            # Let's filter by direction too.
            
            direction_groups: Dict[str, List[Vehicle]] = {}
            for v in lane_vehicles:
                if v.direction not in direction_groups:
                    direction_groups[v.direction] = []
                direction_groups[v.direction].append(v)

            for direction, vehicles in direction_groups.items():
                if direction in ["east", "south"]:
                    # Increasing position. Leader has highest position.
                    vehicles.sort(key=lambda v: v.position, reverse=True)
                else:
                    # Decreasing position. Leader has lowest position.
                    vehicles.sort(key=lambda v: v.position)

                # Process vehicles in order (Leader first)
                for i, v in enumerate(vehicles):
                    target_speed = v.target_speed
                    stop_pos = -1 # No stop required
                    
                    # A. Check Signal / Stop Line (Only for Leader or if intersection is between v and leader)
                    upcoming_int, dist_to_int = self._get_upcoming_intersection_info(v)
                    
                    if upcoming_int:
                        # Check Signal
                        should_stop = False
                        if "H" in v.laneId:
                            if upcoming_int.ewSignal in [SignalState.RED, SignalState.YELLOW]:
                                should_stop = True
                        else:
                            if upcoming_int.nsSignal in [SignalState.RED, SignalState.YELLOW]:
                                should_stop = True
                        
                        if should_stop:
                            # Calculate Stop Line Position
                            # Int pos is at row*100 or col*100
                            # Center of intersection.
                            center_pos = self._get_intersection_pos(v, upcoming_int)
                            
                            if direction in ["east", "south"]:
                                stop_pos = center_pos - STOP_OFFSET
                                # If we passed it, don't stop (unless backed up?)
                                if v.position > stop_pos: 
                                    stop_pos = -1
                            else:
                                stop_pos = center_pos + STOP_OFFSET
                                if v.position < stop_pos:
                                    stop_pos = -1

                    # B. Check Lead Vehicle (Queueing)
                    if i > 0:
                        lead_vehicle = vehicles[i-1]
                        gap = abs(lead_vehicle.position - v.position) - 5.0 # minus vehicle length roughly
                        
                        # Ideal stop pos behind leader
                        if direction in ["east", "south"]:
                            lead_stop_pos = lead_vehicle.position - MIN_GAP
                            if stop_pos == -1 or lead_stop_pos < stop_pos:
                                stop_pos = lead_stop_pos
                        else:
                            lead_stop_pos = lead_vehicle.position + MIN_GAP
                            if stop_pos == -1 or lead_stop_pos > stop_pos:
                                stop_pos = lead_stop_pos

                    # C. Apply Physics
                    # If we need to stop
                    if stop_pos != -1:
                        # Distance to stop
                        dist_to_stop = abs(stop_pos - v.position)
                        
                        if dist_to_stop < 1.0:
                            v.speed = 0.0
                            v.position = stop_pos
                        elif dist_to_stop < 100.0: # Start braking earlier
                            # Calculate required decel to stop at distance
                            if v.speed > 0:
                                # v^2 = u^2 + 2as -> 0 = v^2 + 2(-a)s -> a = v^2 / 2s
                                required_decel = (v.speed ** 2) / (2 * dist_to_stop)
                                # Clamp to vehicle limits
                                actual_decel = min(DECELERATION, required_decel)
                                # If we are too fast, we must max out braking (even if it means overshoot, but we try)
                                if required_decel > DECELERATION:
                                     actual_decel = DECELERATION
                                
                                # Apply
                                v.speed -= actual_decel * dt
                                
                                # Prevent stopping too early due to discrete steps?
                                # Ensure min speed if far?
                                if dist_to_stop > 10.0 and v.speed < 2.0:
                                     v.speed = 2.0
                                elif v.speed < 0.5:
                                     v.speed = 0.5 # Creep very slowly to 1.0 mark
                            else:
                                v.speed = 0.0
                    else:
                        # Accelerate
                        if v.speed < target_speed:
                            v.speed += ACCELERATION * dt
                            if v.speed > target_speed: v.speed = target_speed

                    # D. Move
                    move_amount = v.speed * dt
                    if direction in ["east", "south"]:
                        new_pos = v.position + move_amount
                        # Constraint: Don't cross stop_pos if set
                        if stop_pos != -1 and new_pos > stop_pos:
                            new_pos = stop_pos
                            v.speed = 0.0
                        v.position = new_pos
                    else:
                        new_pos = v.position - move_amount
                        if stop_pos != -1 and new_pos < stop_pos:
                            new_pos = stop_pos
                            v.speed = 0.0
                        v.position = new_pos

                    # Respawn bounds
                    if v.position > 600 or v.position < -100:
                        self.vehicles.remove(v)
                        self._spawn_vehicle()

        if len(self.vehicles) < 20 and random.random() < 0.1:
            self._spawn_vehicle()

    def _get_upcoming_intersection_info(self, v: Vehicle):
        # Logic extracted from _check_stop_condition but returns obj + dist
        try:
             idx = int(v.laneId[1:])
        except:
             return None, 9999.0

        if v.laneType == "horizontal":
            row = idx
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
            
            if target_col != -1 and dist < 100.0: # Only care if within 1 block
                 iid = f"I-{100 + (row * 5) + target_col + 1}"
                 return self.intersections.get(iid), dist
                 
        else: # vertical
            col = idx
            target_row = -1
            dist = 9999.0
            for row in range(5):
                intersection_pos = row * 100.0
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
            
            if target_row != -1 and dist < 100.0:
                 iid = f"I-{100 + (target_row * 5) + col + 1}"
                 return self.intersections.get(iid), dist

        return None, 9999.0

    def _get_intersection_pos(self, v: Vehicle, intersection: Intersection) -> float:
        # returns the relevant axis position (x or y) of the intersection
        try:
            idx = int(intersection.id.split("-")[1]) - 101
            row = idx // 5
            col = idx % 5
            if v.laneType == "horizontal":
                return col * 100.0
            else:
                return row * 100.0
        except:
            return 0.0


    def get_state(self) -> GridState:
        return GridState(
            intersections=list(self.intersections.values()),
            vehicles=self.vehicles,
            emergency=self.emergency_vehicle
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

    def start_emergency(self):
        # Route: I-101 -> I-102 -> I-103 -> I-104 -> I-105
        # Lane: H0 (Row 0, Horizontal)
        # Direction: East
        route = ["I-101", "I-102", "I-103", "I-104", "I-105"]
        
        self.emergency_vehicle = EmergencyVehicle(
            id="EM-1",
            position=-50.0, # Start before grid
            laneId="H0",
            speed=35.0, # Faster
            route=route,
            active=True,
            current_target_index=0,
            type="emergency"
        )
        print("Emergency Vehicle Started")

    def stop_emergency(self):
        if not self.emergency_vehicle:
            return

        self.emergency_vehicle.active = False
        # Restore all intersections to previous mode (FIXED for now)
        for iid in self.emergency_vehicle.route:
            if iid in self.intersections:
                    # If still in override, reset
                    if self.intersections[iid].mode == IntersectionMode.EMERGENCY_OVERRIDE:
                        self.intersections[iid].mode = IntersectionMode.FIXED
        
        self.emergency_vehicle = None
        print("Emergency Vehicle Stopped")

    def _update_emergency_vehicle(self, dt: float):
        if not self.emergency_vehicle:
            return
            
        ev = self.emergency_vehicle
        ev.position += ev.speed * dt
        
        # Check target
        if ev.current_target_index < len(ev.route):
            target_id = ev.route[ev.current_target_index]
            intersection = self.intersections.get(target_id)
            
            if intersection:
                # Get Intersection Position (Col * 100)
                # H0 -> Row 0. 
                # I-101 (Col 0) -> 0.0
                # I-102 (Col 1) -> 100.0
                col = int(target_id.split("-")[1]) - 101 # 0, 1, 2...
                col = col % 5
                target_pos = col * 100.0
                
                dist = target_pos - ev.position
                
                # If approaching (e.g. < 150 units), override signal
                if 0 < dist < 150.0:
                    if intersection.mode != IntersectionMode.EMERGENCY_OVERRIDE:
                        intersection.mode = IntersectionMode.EMERGENCY_OVERRIDE
                        intersection.ewSignal = SignalState.GREEN
                        intersection.nsSignal = SignalState.RED
                        print(f"Override {target_id} for Emergency")

                # If passed (dist < -20), restore and next target
                if dist < -20.0:
                    if intersection.mode == IntersectionMode.EMERGENCY_OVERRIDE:
                         intersection.mode = IntersectionMode.FIXED # or revert to prev
                         print(f"Restore {target_id} after Emergency passed")
                    
                    ev.current_target_index += 1
        
        # End emergency only when vehicle leaves the grid (visual range)
        if ev.position > 650.0:
            self.stop_emergency()

# Global instance
simulation_engine = SimulationEngine()
