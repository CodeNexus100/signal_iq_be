from backend.simulation.engine import simulation_engine
from backend.simulation.models import Vehicle, SignalState
import time

print("--- Testing Signal Compliance ---")

# Setup: Clear vehicles
simulation_engine.vehicles = []

# Scenario: Vehicle on V0 approaching I-101 (at pos V0=0, H0=0)
# V0 Intersection is at pos 0.0 (Row 0 * 100).
# Vehicle moving North (decreasing pos) from 10.0 towards 0.0
# Wait, north decreases? Let's check engine.py
# if direction in ["east", "south"]: position += move_amount
# else: position -= move_amount
# Row 0 (I-101) is at V-pos 0.0.
# If vehicle is at 10.0 moving North, it is approaching 0.0.
# Distance = 10.0 - 0.0 = 10.0 < 25.0 threshold.

print("Spawning test vehicle approaching I-101 from South...")
v = Vehicle(
    id="test-v",
    laneId="V0", 
    laneType="vertical", 
    direction="north", 
    position=10.0, 
    speed=10.0, 
    target_speed=10.0,
    type="car"
)
simulation_engine.vehicles.append(v)

# Get I-101
i101 = simulation_engine.intersections["I-101"]

# Test 1: Signal is RED
print("\nTest 1: Signal is RED")
i101.nsSignal = SignalState.RED
simulation_engine._update_vehicles(0.1) # Step simulation
print(f"Vehicle Speed: {v.speed}")

if v.speed == 0.0:
    print("SUCCESS: Vehicle stopped at RED light.")
else:
    print(f"FAILURE: Vehicle did not stop. Speed={v.speed}")

# Test 2: Signal is GREEN
print("\nTest 2: Signal is GREEN")
i101.nsSignal = SignalState.GREEN
simulation_engine._update_vehicles(0.1) # Step simulation
print(f"Vehicle Speed: {v.speed}")

if v.speed == 10.0:
    print("SUCCESS: Vehicle resumed at GREEN light.")
else:
    print(f"FAILURE: Vehicle did not resume. Speed={v.speed}")
