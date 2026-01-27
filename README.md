# Learnable Texture Python TUI Demo

A minimal two-process TUI demo demonstrating IPC (Inter-Process Communication) with thread-based task processing.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Process 1: UI Frontend               │
│  (curses-based TUI)                                     │
│  - Displays tasks and status                            │
│  - Accepts user input (1-9, arrows, q)                  │
│  - Sends task requests to backend                       │
│  - Receives status updates from backend                 │
└─────────────────────────────────────────────────────────┘
                            │
                    IPC Queue (bidirectional)
                            │
┌─────────────────────────────────────────────────────────┐
│                  Process 2: Backend Worker              │
│  - Accepts task requests                                │
│  - Spawns threads for each task                         │
│  - Processes tasks (simulated texture analysis)         │
│  - Sends status updates back to UI                      │
└─────────────────────────────────────────────────────────┘
```

## Features

- **Two-process architecture**: UI and backend run in separate processes
- **Thread-based processing**: Each task spawns its own thread
- **Real-time status updates**: Progress bars and status messages
- **Bidirectional IPC**: Using `multiprocessing.Queue`
- **Curses TUI**: Clean text-based interface

## How to Run

### Full TUI Demo (requires interactive terminal)
```bash
python main.py
```

### Test IPC Communication (no terminal required)
```bash
python test_ipc.py
```

## Controls

- **1-9**: Create a new texture analysis task (Task 1 through 9)
- **↑/↓ Arrow keys**: Navigate through active tasks
- **q**: Quit the application

## What Happens

1. When you press a number key (1-9), a task request is sent to the backend
2. The backend receives the request and spawns a new thread
3. The thread simulates processing (3-8 random steps with delays)
4. Each step sends a status update back to the UI
5. The UI displays:
   - Active tasks with progress bars
   - Status messages with timestamps
   - Real-time progress updates

## Implementation Details

### Message Types
- `TASK_REQUEST`: UI → Worker (create new task)
- `TASK_STATUS`: Worker → UI (progress update)
- `TASK_COMPLETE`: Worker → UI (task finished)
- `SHUTDOWN`: UI → Worker (cleanup)

### IPC Communication
- `ui_to_worker`: Queue for UI → Worker messages
- `worker_to_ui`: Queue for Worker → UI messages

### Thread Management
- Each task runs in a daemon thread
- Threads are automatically cleaned up when complete
- Worker tracks active tasks in a dictionary

## Example Output

```
=== Learnable Texture Demo ===

1-9: Create new task
Arrow keys: Navigate tasks
q: Quit

Active Tasks:
> Task 1: Processing step 3/5 [███████████████░░░░░░░░░░░░░░░░] 60%
  Task 2: Completed successfully [████████████████████████████] 100%

Status Messages:
[14:32:15] New task requested: Texture analysis 1
[14:32:15] Task 1: Task started
[14:32:16] Task 1: Processing step 1/5
[14:32:17] Task 1: Processing step 2/5
[14:32:18] Task 1: Processing step 3/5
[14:32:20] Task 2: Task started
[14:32:21] Task 1: Processing step 4/5
[14:32:22] Task 1: Completed successfully!
```

## Test Output

```
=== Testing Backend Worker ===

Worker started. Sending test tasks...
Sent task 1: Test texture analysis 1
Sent task 2: Test texture analysis 2
Sent task 3: Test texture analysis 3

Waiting for responses...

[Task 1] Processing step 1/6 (16%)
[Task 1] Task started (0%)
[Task 2] Processing step 1/5 (20%)
[Task 2] Task started (0%)
[Task 3] Processing step 1/7 (14%)
[Task 3] Task started (0%)
[Task 2] Processing step 2/5 (40%)
[Task 1] Processing step 2/6 (33%)
[Task 3] Processing step 2/7 (28%)

Sending shutdown signal...

=== Test Complete ===
Total messages received: 9
IPC communication is working correctly!
```

## Requirements

- Python 3.7+
- Standard library only (no external dependencies)
- Linux/macOS (curses may have limited support on Windows)
