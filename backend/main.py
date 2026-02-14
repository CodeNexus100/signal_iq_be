import asyncio
import time
from fastapi import FastAPI, HTTPException
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .simulation.engine import simulation_engine
from .simulation.models import GridState, Intersection, SignalUpdate, AIToggle, AIStatus, GridOverview, IntersectionSummary, SignalDetails, TrafficPattern, PatternUpdateResult, OptimizationResult

# Background task for simulation loop
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the simulation loop
    loop_task = asyncio.create_task(run_simulation())
    yield
    # Shutdown: Cancel the loop (if needed, but for now just let it die with the process)
    loop_task.cancel()

app = FastAPI(lifespan=lifespan)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for prototype
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
        
        # Update simulation
        simulation_engine.update(dt)
        
        # Sleep to maintain frame rate
        elapsed = time.time() - start_time
        sleep_time = max(0.0, dt - elapsed)
        await asyncio.sleep(sleep_time)

@app.get("/api/grid/state", response_model=GridState)
async def get_grid_state():
    """Returns the current state of the simulation grid"""
    return simulation_engine.get_state()

@app.get("/api/signals/{intersection_id}", response_model=SignalDetails)
async def get_signal_state(intersection_id: str):
    """Returns the details of a specific intersection"""
    details = simulation_engine.get_intersection_details(intersection_id)
    if not details:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return details

@app.post("/api/signals/{intersection_id}/update", response_model=Intersection)
async def update_signal_timing(intersection_id: str, updates: SignalUpdate):
    """Updates the timing and mode of a specific intersection"""
    intersection = simulation_engine.update_signal_timing(intersection_id, updates)
    if not intersection:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return intersection

@app.post("/api/signals/pattern", response_model=PatternUpdateResult)
async def set_traffic_pattern(pattern: TrafficPattern):
    """Applies a global traffic pattern to all intersections"""
    count = simulation_engine.apply_traffic_pattern(pattern.pattern)
    return {"patternApplied": pattern.pattern, "intersectionsUpdated": count}

@app.post("/api/signals/optimize-all", response_model=OptimizationResult)
async def optimize_all_signals():
    """Triggers immediate AI optimization for all intersections"""
    count = simulation_engine.force_ai_optimization()
    return {"optimized": count, "status": "success"}

@app.post("/api/signals/ai")
async def toggle_ai_mode(toggle: AIToggle):
    """Toggles AI optimization mode for all intersections"""
    simulation_engine.set_ai_mode(toggle.enabled)
    return {"status": "AI Mode Updated", "enabled": toggle.enabled}

@app.post("/api/emergency/start")
async def start_emergency():
    """Starts an emergency vehicle simulation"""
    try:
        simulation_engine.start_emergency()
        return {"status": "Emergency Started", "vehicle": simulation_engine.emergency_vehicle}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/emergency/stop")
async def stop_emergency():
    """Stops the emergency vehicle simulation"""
    simulation_engine.stop_emergency()
    return {"status": "Emergency Stopped"}

@app.get("/api/emergency/state")
async def get_emergency_state():
    """Returns the state of the emergency vehicle"""
    return {"emergency": simulation_engine.emergency_vehicle}

@app.get("/api/ai/status")
async def get_ai_status():
    """Returns the status of the AI Traffic Decision Engine"""
    return simulation_engine.get_ai_status()

@app.get("/api/grid/overview", response_model=GridOverview)
async def get_grid_overview():
    """Returns aggregated grid information for visualization"""
    return simulation_engine.get_grid_overview()

@app.get("/api/intersections", response_model=List[IntersectionSummary])
async def get_intersections():
    """Returns a list of all intersections with their status"""
    return simulation_engine.get_intersections_list()


@app.get("/")
def read_root():
    return {"status": "SmartFlow AI Backend Running"}
