import asyncio
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .simulation.engine import simulation_engine
from .simulation.models import GridState, Intersection, SignalUpdate, AIToggle

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

@app.get("/api/signals/{intersection_id}", response_model=Intersection)
async def get_signal_state(intersection_id: str):
    """Returns the state of a specific intersection"""
    intersection = simulation_engine.get_intersection(intersection_id)
    if not intersection:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return intersection

@app.post("/api/signals/{intersection_id}/update", response_model=Intersection)
async def update_signal_timing(intersection_id: str, updates: SignalUpdate):
    """Updates the timing and mode of a specific intersection"""
    intersection = simulation_engine.update_signal_timing(intersection_id, updates)
    if not intersection:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return intersection

@app.post("/api/signals/ai")
async def toggle_ai_mode(toggle: AIToggle):
    """Toggles AI optimization mode for all intersections"""
    simulation_engine.set_ai_mode(toggle.enabled)
    return {"status": "AI Mode Updated", "enabled": toggle.enabled}


@app.get("/")
def read_root():
    return {"status": "SmartFlow AI Backend Running"}
