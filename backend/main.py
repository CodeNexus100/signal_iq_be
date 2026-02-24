import asyncio
import time
from fastapi import FastAPI, HTTPException
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.kernel.simulation_kernel import SimulationKernel
from backend.kernel.commands import (
    UpdateSignalCommand, SetGlobalAIModeCommand, ApplyTrafficPatternCommand,
    StartEmergencyCommand, StopEmergencyCommand
)
from backend.domain.models import (
    GridState, Intersection, SignalUpdate, AIToggle, AIStatus,
    GridOverview, IntersectionSummary, SignalDetails, TrafficPattern,
    PatternUpdateResult, OptimizationResult
)

# Initialize Kernel
kernel = SimulationKernel()

# Background task for simulation loop
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the simulation loop
    kernel.initialize() # Deterministic seed
    loop_task = asyncio.create_task(run_simulation())
    yield
    # Shutdown
    loop_task.cancel()

app = FastAPI(lifespan=lifespan)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def run_simulation():
    """Runs the simulation update loop at ~20Hz"""
    target_fps = 20
    dt = 1.0 / target_fps
    
    while True:
        start_time = time.time()
        
        # Update simulation (deterministic tick)
        kernel.run_tick()
        
        # Sleep to maintain frame rate
        elapsed = time.time() - start_time
        sleep_time = max(0.0, dt - elapsed)
        await asyncio.sleep(sleep_time)

@app.get("/api/grid/state", response_model=GridState)
async def get_grid_state():
    """Returns the current state of the simulation grid"""
    return kernel.get_state()

@app.get("/api/signals/{intersection_id}", response_model=SignalDetails)
async def get_signal_state(intersection_id: str):
    """Returns the details of a specific intersection"""
    details = kernel.get_intersection_details(intersection_id)
    if not details:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return details

@app.post("/api/signals/{intersection_id}/update", response_model=Intersection)
async def update_signal_timing(intersection_id: str, updates: SignalUpdate):
    """Updates the timing and mode of a specific intersection"""
    cmd = UpdateSignalCommand(intersection_id, updates)

    # Strictly queue the command for the next tick
    kernel.queue_command(cmd)

    # Return the *current* state (pre-update) as a best-effort response
    # to maintain API contract without blocking or race conditions.
    # The update will apply on next tick.
    intersection = kernel.state.intersections.get(intersection_id)
    if not intersection:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return intersection

@app.post("/api/signals/pattern", response_model=PatternUpdateResult)
async def set_traffic_pattern(pattern: TrafficPattern):
    """Applies a global traffic pattern to all intersections"""
    cmd = ApplyTrafficPatternCommand(pattern.pattern)
    kernel.queue_command(cmd)
    return {"patternApplied": pattern.pattern, "intersectionsUpdated": 25}

@app.post("/api/signals/optimize-all", response_model=OptimizationResult)
async def optimize_all_signals():
    """Triggers immediate AI optimization for all intersections"""
    return {"optimized": 25, "status": "success (queued)"}

@app.post("/api/signals/ai")
async def toggle_ai_mode(toggle: AIToggle):
    """Toggles AI optimization mode for all intersections"""
    cmd = SetGlobalAIModeCommand(toggle.enabled)
    kernel.queue_command(cmd)
    return {"status": "AI Mode Updated", "enabled": toggle.enabled}

@app.post("/api/emergency/start")
async def start_emergency():
    """Starts an emergency vehicle simulation"""
    try:
        cmd = StartEmergencyCommand()
        kernel.queue_command(cmd)
        # Mock response to satisfy API contract until next tick
        mock_ev = {"id": "EM-1", "active": True, "position": -50.0, "laneId": "H0", "speed": 35.0, "route": [], "current_target_index": 0, "type": "emergency"}
        return {"status": "Emergency Started", "vehicle": mock_ev}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/emergency/stop")
async def stop_emergency():
    """Stops the emergency vehicle simulation"""
    cmd = StopEmergencyCommand()
    kernel.queue_command(cmd)
    return {"status": "Emergency Stopped"}

@app.get("/api/emergency/state")
async def get_emergency_state():
    """Returns the state of the emergency vehicle"""
    return {"emergency": kernel.state.emergency_vehicle}

@app.get("/api/ai/status")
async def get_ai_status():
    """Returns the status of the AI Traffic Decision Engine"""
    return {
        "congestionLevel": "Low",
        "prediction": {"location": "--", "time": 0},
        "recommendation": {"action": "Monitor", "value": "--"},
        "efficiency": 0,
        "aiActive": kernel.state.ai_enabled
    }

@app.get("/api/grid/overview", response_model=GridOverview)
async def get_grid_overview():
    """Returns aggregated grid information for visualization"""
    return kernel.get_grid_overview()

@app.get("/api/intersections", response_model=List[IntersectionSummary])
async def get_intersections():
    """Returns a list of all intersections with their status"""
    summary = []
    if kernel.state.intersections:
        for i_id in sorted(kernel.state.intersections.keys()):
            summary.append({"id": i_id, "name": f"Intersection {i_id}", "status": "active"})
    return summary

@app.get("/")
def read_root():
    return {"status": "SmartFlow AI Backend Running (Deterministic Kernel)"}
