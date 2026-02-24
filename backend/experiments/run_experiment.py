import json
import time
from backend.kernel.simulation_kernel import SimulationKernel

def run_headless_experiment(config_path: str, output_path: str):
    # Load config (mock for now)
    seed = 42
    duration_ticks = 100

    kernel = SimulationKernel()
    kernel.initialize(seed=seed)

    results = []

    start_time = time.time()
    for i in range(duration_ticks):
        kernel.run_tick()
        state = kernel.get_state()
        results.append({
            "tick": i,
            "vehicle_count": len(state.vehicles),
            "emergency_active": bool(state.emergency and state.emergency.active)
        })

    end_time = time.time()
    print(f"Experiment finished in {end_time - start_time:.4f}s")

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        run_headless_experiment(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python run_experiment.py <config> <output>")
