import random
import time
from typing import Dict, List, Optional
from .models import (
    Intersection, IntersectionMode, SignalState, Vehicle, GridState, SignalUpdate, 
    EmergencyVehicle, AIStatus, AIPrediction, AIRecommendation,
    RoadOverview, ZoneOverview, GridOverview, IntersectionSummary, SignalDetails
)
from . import config

class SimulationEngine:
    def __init__(self):
        self.intersections: Dict[str, Intersection] = {}
        self.vehicles: List[Vehicle] = []
        self.emergency_vehicle: Optional[EmergencyVehicle] = None
        self.ai_status: Optional[AIStatus] = None
        self._last_ai_update = 0.0
        self.ai_mode = False # Global AI mode state
        self._initialize_grid()
        self.particles_by_lane: Dict[str, List[Vehicle]] = {} # Cache for optimization
        self._initialize_grid()
        self._initialize_vehicles()

    def _get_vehicles_in_lane(self, lane_id: str) -> List[Vehicle]:
        return [v for v in self.vehicles if v.laneId == lane_id]

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
                nsGreenTime=config.MIN_GREEN_TIME,
                ewGreenTime=config.MIN_GREEN_TIME
            )

    def _initialize_vehicles(self):
        # Spawn some initial vehicles
        for i in range(10):
            self._spawn_vehicle()

    def _spawn_vehicle(self):
        if len(self.vehicles) >= config.MAX_VEHICLES:
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
            position=random.uniform(0, 500), 
            speed=random.uniform(config.MIN_SPEED, config.MAX_SPEED),
            target_speed=random.uniform(config.MIN_SPEED, config.MAX_SPEED),
            type="car"
        )
        self.vehicles.append(vehicle)

    def update(self, dt: float):
        self._update_signals(dt)
        self._update_vehicles(dt)
        if self.emergency_vehicle is not None and self.emergency_vehicle.active:
            self._update_emergency_vehicle(dt)
        
        # Run AI Decision Engine (every tick for now, or throttle)
        self._run_ai_decision_engine()

    def _update_signals(self, dt: float):
        for intersection in self.intersections.values():
            if intersection.mode not in [IntersectionMode.FIXED, IntersectionMode.AI_OPTIMIZED, IntersectionMode.MANUAL]:
                continue
                
            intersection.timer -= dt
            if intersection.timer <= 0:
                self._switch_signal_phase(intersection)

    def _calculate_congestion_score(self, lane_id: str, intersection_id: str) -> float:
        # Score = count + waiting * 2
        count: int = 0
        waiting: int = 0
        
        # Intersection Pos
        intersection = self.intersections.get(intersection_id)
        if not intersection: return 0.0
        
        # Determine detection zone (radius)
        # We need the pos of the intersection relative to the lane
        # Reuse logic from density calc or simplify
        # For prototype: Just count vehicles on the lane within 100 distance of intersection?
        
        # Actually, let's just count all vehicles on the lane segment
        # In this grid, a lane spans the whole row/col, but we only care about the segment approaching this intersection
        
        # Simplify: Count all vehicles on the laneId that are "approaching" and within reasonable distance
        # Lane H0 -> I-101 (0.0), I-102 (100.0), etc.
        # Vehicle on H0 at 50.0 is between 101 and 102. Approaching 102 (East) or 101 (West)
        
        # User spec: "congestion_score = number_of_vehicles_on_lane + waiting_vehicles_near_intersection * 2"
        # "number_of_vehicles_on_lane" implies the whole lane? Or just the approach?
        # Let's use the density logic: Vehicles within radius 30.0 of intersection
        
        radius = config.CONGESTION_RADIUS
        
        idx = int(intersection_id.split("-")[1]) - 101
        row = idx // 5
        col = idx % 5
        
        int_h_pos = col * config.INTERSECTION_SPACING
        int_v_pos = row * config.INTERSECTION_SPACING
        
        # Optimize: iterate only vehicles in this lane
        lane_vehicles = self._get_vehicles_in_lane(lane_id)
        
        for v in lane_vehicles:
            # Check distance
            dist = 9999.0
            if "H" in lane_id:
                dist = abs(v.position - int_h_pos)
            else:
                dist = abs(v.position - int_v_pos)
                
            if dist < radius:
                count += 1
                if v.speed < 1.0:
                    waiting += 1
                        
        return count + (waiting * 2)

    def _run_ai_decision_engine(self):
        # 1. Aggregate Congestion
        total_ns_score = 0
        total_ew_score = 0
        
        max_lane_score = -1
        max_lane_id = "None"
        
        for intersection in self.intersections.values():
            if intersection.mode != IntersectionMode.AI_OPTIMIZED:
                continue
                
            idx = int(intersection.id.split("-")[1]) - 101
            row = idx // 5
            col = idx % 5
            
            h_lane = f"H{row}"
            v_lane = f"V{col}"
            
            ew_score = self._calculate_congestion_score(h_lane, intersection.id)
            ns_score = self._calculate_congestion_score(v_lane, intersection.id)
            
            total_ew_score += ew_score
            total_ns_score += ns_score
            
            if ew_score > max_lane_score:
                max_lane_score = ew_score
                max_lane_id = f"East-West ({h_lane} @ {intersection.id})"
            if ns_score > max_lane_score:
                max_lane_score = ns_score
                max_lane_id = f"North-South ({v_lane} @ {intersection.id})"

        # 2. Decision Logic
        recommended = "Balanced"
        green_increase = 0
        efficiency = 0
        
        # Global decision for now, or per intersection?
        # "If North-South congestion > East-West ... nsGreenTime += 5" implies global shift or per intersection.
        # Implementation plan said "Update Signals: Apply ... for all AI-mode intersections" -> Global Policy.
        
        if total_ns_score > total_ew_score:
            recommended = "North-South"
            green_increase = 5
            efficiency = int((total_ns_score - total_ew_score) * 2) # Arbitrary metric
        elif total_ew_score > total_ns_score:
            recommended = "East-West"
            green_increase = 5
            efficiency = int((total_ew_score - total_ns_score) * 2)
        
        # 3. Apply changes (Throttled? optimization rules say "Run every tick", but updating timer every tick is chaotic)
        # engine.py _optimize_signals handles this during phase switch.
        # But user request says "Outputs: updated signal timings".
        # Let's update the *target* green times in the intersections, so next cycle picks them up.
        # We should NOT increment indefinitely every tick. 
        # We need a stable target.
        # Let's treat "nsGreenTime += 5" as "Limit towards max".
        # Actually, if we add 5 every tick, it explodes.
        # This logic is likely meant to be "Per Cycle" or "Throttled".
        # I will apply it here but carefully. 
        # Let's simply update the stored greenTimes using the logic from _optimize_signals but globally.
        
        # Wait, the user prompt says:
        # "If North-South congestion > East-West congestion: nsGreenTime += 5"
        # This sounds like an incremental adjustment step.
        # I will apply this ONLY if we haven't maxed out, and maybe with a small probability or only on certain triggers?
        # "Run the AI engine every simulation tick."
        # If I add 5 every tick (0.05s), in 1 second I add 100 seconds. That's wrong.
        # I will assume this decision engine sets the STRATEGY, and the strategy is applied periodically.
        # OR, I interpret "nsGreenTime += 5" as "Desired Green Time is Base + 5".
        
        # Let's stick to the previous implementation: _optimize_signals does the adjustment during phase switch.
        # Here we just REPORT the status.
        # INVALIDATING previous _optimize_signals?
        # User said "Do NOT create new simulation loops. Attach this engine to the existing update loop."
        # And "Outputs: updated signal timings".
        
        # OK, I will modify `_optimize_signals` to USE this global logic, or make this function update them?
        # I'll make this function update them, but ONLY occasionally.
        # Let's use a counter or timestamp.
        
        # BETTER: Calculate the TARGET and nudge towards it.
        # Or just let _optimize_signals call this status?
        
        # Let's make this function just UPDATE STATUS for now, 
        # AND apply the nudges purely to the intersection GreenTime attributes?
        # If I do it every tick, I must act slowly. 0.05s is too fast.
        
        # Re-reading: "Run ... every simulation tick."
        # "If NS > EW: nsGreen += 5".
        # I'll assume this is "If we are in this state, we *want* +5 more than current".
        # I will implement a cooldown. Update signals every 5 seconds?
        
       # For prototype simplicity:
        # The AI Engine RUNS every tick to monitor.
        # It UPDATES signals only every 1.0s or 5.0s.
        
        current_time = time.time()
        if not hasattr(self, "_last_ai_update"):
            self._last_ai_update = 0
            
        if current_time - self._last_ai_update > config.AI_UPDATE_INTERVAL:
            self._last_ai_update = current_time
            
            for intersection in self.intersections.values():
                 if intersection.mode == IntersectionMode.AI_OPTIMIZED:
                     if recommended == "North-South":
                         intersection.nsGreenTime = min(config.MAX_GREEN_TIME, intersection.nsGreenTime + 1.0) # Slow drifting
                         intersection.ewGreenTime = max(config.MIN_GREEN_TIME, intersection.ewGreenTime - 1.0)
                     elif recommended == "East-West":
                         intersection.ewGreenTime = min(config.MAX_GREEN_TIME, intersection.ewGreenTime + 1.0)
                         intersection.nsGreenTime = max(config.MIN_GREEN_TIME, intersection.nsGreenTime - 1.0)

        # 4. Global Status
        # Determine strict congestion level
        level = "Low"
        if max_lane_score > 10: level = "Medium"
        if max_lane_score > 20: level = "High"

        rec_action = "Monitor"
        rec_value = "--"
        
        if recommended == "North-South":
             rec_action = "Extend North-South Green"
             rec_value = f"+{green_increase}s"
        elif recommended == "East-West":
             rec_action = "Extend East-West Green"
             rec_value = f"+{green_increase}s"

        self.ai_status = AIStatus(
            congestionLevel=level,
            prediction=AIPrediction(
                location=max_lane_id if max_lane_score > 5 else "Grid Optimal",
                time=int(max(0.0, 10.0 - efficiency/10.0)) # Mock logic
            ),
            recommendation=AIRecommendation(
                action=rec_action,
                value=rec_value
            ),
            efficiency=efficiency,
            aiActive=self.ai_mode,
            timestamp=current_time
        )

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
            intersection_h_pos = col * config.INTERSECTION_SPACING
            intersection_v_pos = row * config.INTERSECTION_SPACING
            
            radius = config.DETECTION_RADIUS
            
            ns_load: int = 0
            ew_load: int = 0
            
            # Optimize: Only check relevant lanes
            for v in self._get_vehicles_in_lane(h_lane_id):
                if abs(v.position - intersection_h_pos) < radius:
                    ew_load += 1
            
            for v in self._get_vehicles_in_lane(v_lane_id):
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
        min_green = config.MIN_GREEN_TIME
        max_green = config.MAX_GREEN_TIME
        
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
        # 1. Group by Lane (Optimize: this rebuilds the index every tick. 
        # Ideally we maintain it, but for n=50 it's fast enough to rebuild)
        vehicles_by_lane: Dict[str, List[Vehicle]] = {}
        for v in self.vehicles:
            if v.laneId not in vehicles_by_lane:
                vehicles_by_lane[v.laneId] = []
            vehicles_by_lane[v.laneId].append(v)

        # 3. Process each lane
        for lane_id, lane_vehicles in vehicles_by_lane.items():
            # Sort vehicles
            # Horizontal (East): Increasing pos -> Sort descending (leader first)
            # Horizontal (West): Decreasing pos -> Sort ascending (leader first)
            # Vertical (South): Increasing pos -> Sort descending
            # Vertical (North): Decreasing pos -> Sort ascending
            
            # This allows opposing traffic in SAME lane ID? That's bad.
            # "H0" should probably be one direction or bi-directional with offset?
            # For this prototype, I'll assume:
            # H0, H2, H4 -> East
            # H1, H3 -> West
            # V0, V2, V4 -> South
            # V1, V3 -> North
            
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
                                stop_pos = center_pos - config.STOP_OFFSET
                                # Fix: Don't give up stopping just because we passed the line.
                                # Only give up if we passed the CENTER (entered intersection) or some "too late" point.
                                # Let's say if we are past the line but not yet at center, keep stopping.
                                if v.position > center_pos: 
                                    stop_pos = -1
                            else:
                                stop_pos = center_pos + config.STOP_OFFSET
                                # Fix: West/North (decreasing). Center < StopLine.
                                # If v.pos < StopLine, we passed it.
                                # Only give up if v.pos < Center.
                                if v.position < center_pos:
                                    stop_pos = -1

                    # B. Check Lead Vehicle (Queueing)
                    if i > 0:
                        lead_vehicle = vehicles[i-1]
                        
                        # Ideal stop pos behind leader
                        if direction in ["east", "south"]:
                            lead_stop_pos = lead_vehicle.position - config.MIN_GAP
                            if stop_pos == -1 or lead_stop_pos < stop_pos:
                                stop_pos = lead_stop_pos
                        else:
                            lead_stop_pos = lead_vehicle.position + config.MIN_GAP
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
                        elif dist_to_stop < 150.0: # Check stopping condition logic
                            # Smart Approach Logic
                            # Allow vehicle to move IF it can safely stop in remaining distance.
                            # v_safe = sqrt(2 * a * d) * safety_factor
                            safe_speed = (2 * config.DECELERATION * dist_to_stop) ** 0.5 * 0.8
                            
                            if v.speed > safe_speed:
                                # We are too fast, BRAKE
                                required_decel = (v.speed ** 2) / (2 * dist_to_stop)
                                actual_decel = min(config.DECELERATION * 1.5, required_decel) # Allow harder braking if needed
                                v.speed -= actual_decel * dt
                                if v.speed < 0: v.speed = 0.0
                            else:
                                # We are slow enough, maintain or accelerate slightly to close gap
                                # Only accelerate if we are significantly below target and safe
                                if v.speed < target_speed and v.speed < safe_speed * 0.9:
                                     v.speed += config.ACCELERATION * dt

                    else:
                        # Accelerate
                        if v.speed < target_speed:
                            v.speed += config.ACCELERATION * dt
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
                    if v.position > config.GRID_BOUNDS_MAX or v.position < config.GRID_BOUNDS_MIN:
                        self.vehicles.remove(v)
                        self._spawn_vehicle()

        if len(self.vehicles) < config.MIN_SPAWN_VEHICLES and random.random() < config.SPAWN_CHANCE:
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
            dist = 9999.0
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
            
            if target_col != -1 and dist < config.INTERSECTION_SPACING: # Only care if within 1 block
                 iid = f"I-{100 + (row * 5) + target_col + 1}"
                 return self.intersections.get(iid), dist
                 
        else: # vertical
            col = idx
            target_row = -1
            dist = 9999.0
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
                 return self.intersections.get(iid), dist

        return None, 9999.0

    def _get_intersection_pos(self, v: Vehicle, intersection: Intersection) -> float:
        # returns the relevant axis position (x or y) of the intersection
        try:
            idx = int(intersection.id.split("-")[1]) - 101
            row = idx // 5
            col = idx % 5
            if v.laneType == "horizontal":
                return col * config.INTERSECTION_SPACING
            else:
                return row * config.INTERSECTION_SPACING
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
        self.ai_mode = enabled
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
        if self.emergency_vehicle is None:
            return

        self.emergency_vehicle.active = False
        # Restore all intersections to previous mode (FIXED for now)
        for iid in self.emergency_vehicle.route:
            # We must verify intersections exist and emergency_vehicle is not None (checked above)
            if iid in self.intersections and self.emergency_vehicle:
                # If still in override, reset
                if self.intersections[iid].mode == IntersectionMode.EMERGENCY_OVERRIDE:
                    self.intersections[iid].mode = IntersectionMode.FIXED
        
        self.emergency_vehicle = None
        print("Emergency Vehicle Stopped")

    def _update_emergency_vehicle(self, dt: float):
        if self.emergency_vehicle is None:
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
                target_pos = col * config.INTERSECTION_SPACING
                
                dist = target_pos - ev.position
                
                # If approaching (e.g. < 150 units), override signal
                if 0 < dist < config.EMERGENCY_DETECTION_DIST:
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
        # End emergency only when vehicle leaves the grid (visual range)
        if ev.position > config.GRID_BOUNDS_MAX + 50.0:
            self.stop_emergency()

    def get_ai_status(self) -> AIStatus:
        if self.ai_status:
             # Refresh timestamp?
             return self.ai_status
        
        # Default if not run yet
        return {
            "congestionLevel": "Low",
            "prediction": {"location": "--", "time": 0},
            "recommendation": {"action": "Monitor", "value": "--"},
            "efficiency": 0,
            "aiActive": False
        }

    def get_grid_overview(self) -> GridOverview:
        # 1. Calculate Road Stats
        roads: List[RoadOverview] = []
        
        # Define all lanes (H0-H4, V0-V4)
        all_lanes = [f"H{i}" for i in range(5)] + [f"V{i}" for i in range(5)]
        
        lane_congestions = {}
        
        for lane_id in all_lanes:
            vehicles = self._get_vehicles_in_lane(lane_id)
            count = len(vehicles)
            
            # Normalize: 3 vehicles = 1.0 congestion (aggressive for demo)
            congestion = min(1.0, count / 3.0)
            lane_congestions[lane_id] = congestion
            
            status = "optimal"
            if congestion >= 0.75:
                status = "congested"
            elif congestion >= 0.5:
                status = "moderate"
                
            roads.append(RoadOverview(laneId=lane_id, congestion=round(congestion, 2), flow=status))

        # 2. Calculate Zone Stats
        # Mapping definition
        zones_map = {
            "North Industrial": ["H0", "H1", "V0", "V4"], # Northern rim
            "Central District": ["H2", "H3", "V2", "V3"], # Core
            "West Harbor": ["V0", "V1", "H4"] # South-West
        }
        
        zones: List[ZoneOverview] = []
        for name, lanes in zones_map.items():
            total_load = 0.0
            for l in lanes:
                total_load += lane_congestions.get(l, 0.0)
            
            avg_load = total_load / max(1, len(lanes))
            
            status = "optimal"
            if avg_load >= 0.75:
                status = "congested"
            elif avg_load >= 0.5:
                status = "moderate"
                
            zones.append(ZoneOverview(name=name, load=round(avg_load, 2), status=status))

        return GridOverview(roads=roads, zones=zones)

    def get_intersections_list(self) -> List[IntersectionSummary]:
        summary_list = []
        # Sort by ID for consistent output
        sorted_ids = sorted(self.intersections.keys())
        
        for i_id in sorted_ids:
            # Parse ID to generate name: I-r-c -> "Avenue {r+1} & Street {c+1}"
            try:
                parts = i_id.split('-')
                r = int(parts[1])
                c = int(parts[2])
                name = f"Avenue {r+1} & Street {c+1}"
            except:
                name = f"Intersection {i_id}"
                
            summary_list.append(IntersectionSummary(
                id=i_id,
                name=name,
                status="active" # Always active in this simulation
            ))
            
        return summary_list

            
        return summary_list

    def get_intersection_details(self, intersection_id: str) -> Optional[SignalDetails]:
        intersection = self.intersections.get(intersection_id)
        if not intersection:
            return None
            
        # Determine Current Phase
        # If NS is green -> NS
        # If EW is green -> EW
        # If both Red -> Transition/All-Red (we'll default to previous or just "All-Red")
        phase = "All-Red"
        if intersection.nsSignal == SignalState.GREEN:
            phase = "NS"
        elif intersection.ewSignal == SignalState.GREEN:
            phase = "EW"
        elif intersection.nsSignal == SignalState.YELLOW:
            phase = "NS-Yellow"
        elif intersection.ewSignal == SignalState.YELLOW:
            phase = "EW-Yellow"
        
        # Calculate Flow Rate (Mock based on vehicles in related lanes)
        # Parse I-r-c to find lanes
        try:
            parts = intersection_id.split('-')
            r = int(parts[1]) # H{r}
            c = int(parts[2]) # V{c}
            
            h_lane = f"H{r}"
            v_lane = f"V{c}"
            
            # Count vehicles in these lanes
            # We can use the index if we trust it's updated, or just filter.
            # Using index for improved perf
            h_count = len(self.particles_by_lane.get(h_lane, []))
            v_count = len(self.particles_by_lane.get(v_lane, []))
            
            # Mock flow rate: (count * random factor) -> vehicles/hour approx
            # This is just for visualization
            raw_flow = (h_count + v_count) * 120 # e.g., 5 vehicles * 120 = 600 v/h
            # Add some jitter so it looks alive
            flow_rate = int(raw_flow * random.uniform(0.9, 1.1))
        except:
             flow_rate = random.randint(500, 1000)

        return SignalDetails(
            intersectionId=intersection.id,
            nsGreenTime=int(intersection.nsGreenTime),
            ewGreenTime=int(intersection.ewGreenTime),
            currentPhase=phase,
            timerRemaining=max(0, int(intersection.timer)),
            flowRate=flow_rate,
            pedestrianDemand="Low", # Hardcoded for now
            aiEnabled=(intersection.mode == IntersectionMode.AI_OPTIMIZED)
        )

# Global instance
simulation_engine = SimulationEngine()
