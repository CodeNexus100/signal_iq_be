# SignalIQ Backend

This directory contains the backend services for the SignalIQ Traffic Intelligence System.

## Structure

*   `main.py`: The entry point for the FastAPI application and the simulation loop.
*   `simulation/`: Contains the core simulation logic.
    *   `engine.py`: The main simulation engine and state management.
    *   `models.py`: Pydantic data models.
    *   `config.py`: Configuration constants.

## Architecture Review

A comprehensive architectural review and refactoring roadmap is available in the root directory: [ARCHITECTURE_REPORT.md](../ARCHITECTURE_REPORT.md).

## Running the Server

```bash
uvicorn backend.main:app --reload
```

## Testing

Run the integration test:

```bash
python3 test_ai_decision.py
```
