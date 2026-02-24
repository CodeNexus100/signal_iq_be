# Simulation Configuration

# Grid Settings
GRID_SIZE = 5
INTERSECTION_SPACING = 100.0
GRID_BOUNDS_MIN = -100.0
GRID_BOUNDS_MAX = 600.0

# Signal Timings
MIN_GREEN_TIME = 10.0
MAX_GREEN_TIME = 60.0
YELLOW_TIME = 3.0
AI_UPDATE_INTERVAL = 2.0  # Seconds between AI decision updates

# Vehicle Physics
MAX_VEHICLES = 50
SPAWN_CHANCE = 0.1
MIN_SPAWN_VEHICLES = 20

ACCELERATION = 10.0      # units/s^2
DECELERATION = 30.0      # units/s^2
MAX_SPEED = 15.0
MIN_SPEED = 5.0

# Traffic Rules
STOP_OFFSET = 35.0       # Distance from intersection center to stop line
MIN_GAP = 8.0            # Minimum gap between vehicles
DETECTION_RADIUS = 30.0  # Radius for congestion detection
CONGESTION_RADIUS = 50.0 # Radius for AI congestion scoring
EMERGENCY_DETECTION_DIST = 150.0 # Distance to trigger green wave
