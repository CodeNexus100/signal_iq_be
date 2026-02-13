from backend.simulation.engine import simulation_engine
import time
import random

print("Debugging Density Calculation...")

# Force spawn vehicles around I-101 (Row 0, Col 0) -> H0, V0
print("Spawning test vehicles for I-101...")
# I-101 is at H0:0.0, V0:0.0 roughly in our logic? 
# Wait, code says: intersection_h_pos = col * 100.0 (0), intersection_v_pos = row * 100.0 (0)

# Add vehicle on H0 at position 10 (approaching 0? moving east means pos increases)
# If moving east (0 -> 100), approaching 0 is not possible unless we wrap.
# Let's place vehicle at 10 moving West (10 -> 0)
from backend.simulation.models import Vehicle

v1 = Vehicle(id="debug-1", laneId="H0", laneType="horizontal", direction="west", position=10.0, speed=10.0)
simulation_engine.vehicles.append(v1)

# Add vehicle on V0 at position 10 moving North (10 -> 0)
v2 = Vehicle(id="debug-2", laneId="V0", laneType="vertical", direction="north", position=10.0, speed=10.0)
simulation_engine.vehicles.append(v2)

# Check density
ns, ew = simulation_engine._calculate_density("I-101")
print(f"I-101 Density: NS={ns}, EW={ew}")

if ns > 0 and ew > 0:
    print("SUCCESS: Density calculation works.")
else:
    print("FAILURE: Density calculation returned 0.")
    print("Vehicles:", simulation_engine.vehicles)
