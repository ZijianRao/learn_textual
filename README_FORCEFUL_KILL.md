# Forceful Thread/Process Termination Demo

This enhanced version demonstrates handling truly stuck/unresponsive threads using multiprocessing instead of threading.

## Key Differences from Original

| Feature | Original (Threading) | Enhanced (Multiprocessing) |
|---------|---------------------|---------------------------|
| **Thread/Process Type** | `threading.Thread` | `multiprocessing.Process` |
| **Cooperative Cancel** | `threading.Event` | `SIGTERM` signal |
| **Forceful Termination** | ❌ Not possible | ✅ `SIGKILL` signal |
| **Resource Cleanup** | Manual (cooperative) | Automatic (OS handles) |
| **Use Case** | Well-behaved tasks | Tasks that may get stuck |

## Why Multiprocessing for Stuck Threads?

### The Problem with Threading
Python's `threading` module **does not support** forcefully killing threads:
- No `terminate()` method on `Thread` class
- Forceful termination causes resource leaks
- Can lead to deadlocks and inconsistent state
- No cleanup of locks, files, or memory

### The Multiprocessing Solution
Multiprocessing provides:
- **Forceful termination**: `process.terminate()` or `os.kill(pid, SIGKILL)`
- **Process isolation**: Each task runs in separate process
- **Resource cleanup**: OS reclaims all resources when process dies
- **Signal handling**: Can catch `SIGTERM` for graceful shutdown

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│         Process 1: UI Frontend (curses TUI)            │
│  - Displays tasks with progress bars                   │
│  - Accepts user input (1-9, arrows, k, K, r, q)        │
│  - Sends task requests to backend                       │
│  - Receives status updates from backend                 │
└─────────────────────────────────────────────────────────┘
                            │
                    IPC Queue (bidirectional)
                            │
┌─────────────────────────────────────────────────────────┐
│         Process 2: Backend Worker                      │
│  - Accepts task requests                                │
│  - Spawns PROCESS for each task (not thread)           │
│  - Monitors task health (watchdog)                      │
│  - Handles SIGTERM/SIGKILL signals                      │
│  - Sends status updates back to UI                      │
└─────────────────────────────────────────────────────────┘
                            │
                    IPC Queue (bidirectional)
                            │
┌─────────────────────────────────────────────────────────┐
│         Process 3: Task Worker                         │
│  - Runs actual task logic                               │
│  - Can be forcefully terminated                         │
│  - Handles SIGTERM for graceful shutdown                │
└─────────────────────────────────────────────────────────┘
```

## Controls

- **1-9**: Create a new texture analysis task
- **↑/↓ Arrow keys**: Navigate through active tasks
- **k**: Graceful cancel (sends SIGTERM)
- **K**: Forceful kill (sends SIGKILL)
- **r**: Restart task (kill + new process)
- **q**: Quit the application

## How to Run

### Full TUI Demo
```bash
python main_with_forceful_kill.py
```

### Run Tests
```bash
python test_forceful_kill.py
```

## Test Output

```
=== Testing Graceful Cancel ===

Worker started. Sending test task...
Sent task: Test task for graceful cancel
Sent graceful cancel request for task 1

Waiting for cancel response...

[Task 1] Task started (0%)
[Task 1] Processing step 1/7 (14%)
[Task 1] Cancelling task (graceful)... (0%)
[Task 1] Process terminated by signal (0%)

✅ Task gracefully cancelled successfully!

=== Testing Forceful Kill ===

Worker started. Sending test tasks...
Sent task: Test task that will get stuck
Sent forceful kill request for task 1

Waiting for kill response...

[Task 1] Task started (0%)
[Task 1] Processing step 1/4 (25%)
[Task 1] Processing step 2/4 (50%)
[Task 1] Task forcefully killed (0%)

✅ Task forcefully killed successfully!

=== Testing Restart ===

Worker started. Sending test task...
Sent task: Test task for restart
Sent restart request for task 1

Waiting for restart response...

[Task 1] Task started (0%)
[Task 1] Processing step 1/3 (33%)
[Task 1] Task restarted (0%)

✅ Task restarted successfully!
```

## Implementation Details

### Message Types
- `TASK_REQUEST`: UI → Worker (create new task)
- `TASK_STATUS`: Worker → UI (progress update)
- `TASK_COMPLETE`: Worker → UI (task finished)
- `TASK_CANCEL`: UI → Worker (graceful termination via SIGTERM)
- `TASK_KILL`: UI → Worker (forceful termination via SIGKILL)
- `TASK_RESTART`: UI → Worker (kill + new process)
- `TASK_RESTART`: UI → Worker (kill + new process)
- `SHUTDOWN`: UI → Worker (cleanup)

### Signal Handling
- **SIGTERM**: Graceful termination - process can clean up resources
- **SIGKILL**: Forceful termination - OS kills process immediately
- **SIGINT**: Interrupt signal (Ctrl+C)

### Watchdog Pattern
The backend worker includes a watchdog thread that:
- Monitors task health every second
- Detects tasks with no progress for 10+ seconds
- Sends warning status to UI

### Process Management
- Each task runs in its own `multiprocessing.Process`
- Processes are tracked in `active_tasks` dictionary
- When killed/restarted, old process is terminated and new one spawned
- OS automatically reclaims all resources (files, memory, etc.)

## When to Use Each Approach

### Use Threading (Original) When:
- Tasks are well-behaved and check cancellation events
- You need lightweight concurrency
- Tasks don't block indefinitely
- You want shared memory between tasks

### Use Multiprocessing (Enhanced) When:
- Tasks might get stuck or block indefinitely
- You need forceful termination capability
- Tasks are CPU-intensive and benefit from process isolation
- You want true parallelism (not just concurrency)

## Limitations

1. **Higher overhead**: Processes use more memory than threads
2. **No shared memory**: Processes have separate memory spaces
3. **Slower IPC**: Queue communication between processes is slower than threads
4. **Platform differences**: Signal handling varies on Windows vs Unix

## Best Practices

1. **Prefer cooperative cancellation**: Always check for cancellation events first
2. **Use timeouts**: Add timeouts to blocking operations
3. **Implement health checks**: Use watchdog to detect stuck tasks
4. **Clean up resources**: Use `try/finally` or context managers
5. **Log signals**: Handle SIGTERM gracefully when possible

## References

- [Python multiprocessing documentation](https://docs.python.org/3/library/multiprocessing.html)
- [POSIX signals](https://en.wikipedia.org/wiki/Signal_(IPC))
- [Thread termination in Python](https://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread-in-python)
