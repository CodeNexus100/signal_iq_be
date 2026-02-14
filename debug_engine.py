import sys
import os

# Add parent directory to path so we can import backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from backend.simulation.engine import simulation_engine
    from backend.simulation.models import TrafficPattern
    
    print("Engine imported successfully.")
    print(f"Intersections: {len(simulation_engine.intersections)}")
    
    print("Applying 'rush_hour'...")
    count = simulation_engine.apply_traffic_pattern("rush_hour")
    print(f"Count: {count}")
    
    # Check one intersection
    if len(simulation_engine.intersections) > 0:
        first = list(simulation_engine.intersections.values())[0]
        print(f"First ID: {first.id}")
        print(f"NS Green: {first.nsGreenTime}")
        print(f"EW Green: {first.ewGreenTime}")
        
    print("Done.")

except Exception as e:
    print(f"CRASH: {e}")
    import traceback
    traceback.print_exc()
