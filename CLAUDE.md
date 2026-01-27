# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a minimal Python TUI demo demonstrating two-process architecture with IPC (Inter-Process Communication) and thread-based task processing. The project uses Python's standard library only (no external dependencies despite `textual` being listed in `pyproject.toml`).

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│         Process 1: UI Frontend (curses TUI)            │
│  - Displays tasks with progress bars                   │
│  - Accepts user input (1-9, arrows, q)                 │
│  - Sends task requests to backend                       │
│  - Receives status updates from backend                 │
└─────────────────────────────────────────────────────────┘
                            │
                    IPC Queue (bidirectional)
                            │
┌─────────────────────────────────────────────────────────┐
│         Process 2: Backend Worker                      │
│  - Accepts task requests                                │
│  - Spawns threads for each task                         │
│  - Simulates texture processing                         │
│  - Sends status updates back to UI                      │
└─────────────────────────────────────────────────────────┘
```

### Key Components

**`main.py`** - Single file containing:
- `MessageType` enum - IPC message types (TASK_REQUEST, TASK_STATUS, TASK_COMPLETE, SHUTDOWN)
- `IPCMessage` dataclass - Structured message format for IPC
- `BackendWorker` class - Worker process that spawns threads for tasks
- `UIFrontend` class - Curses-based TUI with optimized rendering (uses `needs_redraw` flag to prevent screen flushing)
- `ui_process()` / `worker_process()` - Process entry points
- `main()` - Spawns both processes with `multiprocessing.Queue` for communication

**`test_ipc.py`** - Test script that verifies IPC communication without requiring curses

### IPC Communication Flow

1. **UI → Worker**: Task requests sent via `ui_to_worker` queue
2. **Worker → UI**: Status updates sent via `worker_to_ui` queue
3. Each task spawns a daemon thread in the worker process
4. Threads send progress updates (TASK_STATUS) and completion (TASK_COMPLETE) back to UI

### UI Rendering Optimization

The UI uses a `needs_redraw` flag to prevent unnecessary screen refreshes:
- Set to `True` when: receiving messages, sending requests, navigating tasks
- Screen only redraws when `needs_redraw = True`
- Uses `curses.doupdate()` instead of `refresh()` for smoother updates
- Timeout set to 50ms for responsive input handling

## Common Commands

### Run the Full TUI Demo
Requires an interactive terminal (curses-based):
```bash
python main.py
```

### Run IPC Tests
No terminal required - verifies backend worker and IPC communication:
```bash
python test_ipc.py
```

### Using uv (if configured)
```bash
source .venv/bin/activate
python main.py
```

## Development Notes

- **No external dependencies**: The code uses only Python standard library (`curses`, `multiprocessing`, `threading`, `queue`, etc.)
- **Platform considerations**: `curses` has limited support on Windows; the demo is designed for Linux/macOS
- **Multiprocessing**: Uses `spawn` start method for cross-platform compatibility
- **Error handling**: UI process gracefully handles curses initialization errors in non-interactive terminals

## File Structure

- `main.py` - Main demo application (385 lines)
- `test_ipc.py` - IPC test script (82 lines)
- `README.md` - User documentation with examples
- `pyproject.toml` - Project configuration (note: `textual` dependency is listed but not used)
- `CLAUDE.md` - This file - development guidance for Claude Code