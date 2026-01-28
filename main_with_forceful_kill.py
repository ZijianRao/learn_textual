#!/usr/bin/env python3
"""
Enhanced Learnable Texture Python TUI Demo with Forceful Thread Termination

This version demonstrates handling truly stuck/unresponsive threads using:
1. Cooperative cancellation (threading.Event) - for well-behaved threads
2. Forceful termination using multiprocessing - for stuck/deadlocked threads
3. Watchdog pattern - to detect and handle unresponsive tasks

Architecture:
- Uses multiprocessing.Process instead of threading.Thread for tasks
- Each task runs in its own process (can be terminated forcefully)
- Watchdog monitors task health and can trigger termination
- UI can send KILL signal for truly stuck processes
"""

import curses
import multiprocessing as mp
import queue
import random
import threading
import time
import signal
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict


class MessageType(Enum):
    """Message types for IPC communication"""
    TASK_REQUEST = "task_request"
    TASK_STATUS = "task_status"
    TASK_COMPLETE = "task_complete"
    TASK_CANCEL = "task_cancel"      # Cooperative cancellation
    TASK_KILL = "task_kill"          # Forceful termination
    TASK_RESTART = "task_restart"
    SHUTDOWN = "shutdown"


@dataclass
class IPCMessage:
    """Message structure for IPC communication"""
    msg_type: MessageType
    task_id: Optional[int] = None
    content: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None


def task_worker_process(task_id: int, content: str, output_queue: mp.Queue):
    """
    Worker function that runs in a separate process.
    This can be forcefully terminated if it gets stuck.
    """
    # Set up signal handler for graceful termination
    def signal_handler(signum, frame):
        output_queue.put(IPCMessage(
            msg_type=MessageType.TASK_STATUS,
            task_id=task_id,
            status="Process terminated by signal",
            progress=0
        ))
        exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Simulate work with random delays
        steps = random.randint(3, 8)

        for i in range(steps):
            # Update progress
            progress = int((i + 1) / steps * 100)
            status = f"Processing step {i + 1}/{steps}"

            # Send status update
            output_queue.put(IPCMessage(
                msg_type=MessageType.TASK_STATUS,
                task_id=task_id,
                status=status,
                progress=progress
            ))

            # Simulate work
            time.sleep(random.uniform(0.3, 0.8))

        # Mark as complete
        output_queue.put(IPCMessage(
            msg_type=MessageType.TASK_COMPLETE,
            task_id=task_id,
            status="Completed successfully",
            progress=100
        ))

    except Exception as e:
        output_queue.put(IPCMessage(
            msg_type=MessageType.TASK_STATUS,
            task_id=task_id,
            status=f"Error: {str(e)}",
            progress=0
        ))


class BackendWorker:
    """Backend worker process that handles tasks using multiprocessing"""

    def __init__(self, input_queue: mp.Queue, output_queue: mp.Queue):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.active_tasks: Dict[int, Dict] = {}
        self.task_counter = 0
        self.running = True
        self.watchdog_thread = None
        self.watchdog_stop_event = threading.Event()

    def start_watchdog(self):
        """Start watchdog thread to monitor task health"""
        def watchdog():
            while not self.watchdog_stop_event.is_set():
                time.sleep(1.0)  # Check every second
                for task_id, task_info in list(self.active_tasks.items()):
                    process = task_info.get("process")
                    if process and process.is_alive():
                        # Check if task is stuck (no progress for too long)
                        last_update = task_info.get("last_update", 0)
                        if time.time() - last_update > 10:  # 10 second timeout
                            # Task appears stuck, send warning
                            self.output_queue.put(IPCMessage(
                                msg_type=MessageType.TASK_STATUS,
                                task_id=task_id,
                                status="⚠️  Task appears stuck (no progress)",
                                progress=task_info.get("progress", 0)
                            ))

        self.watchdog_thread = threading.Thread(target=watchdog, daemon=True)
        self.watchdog_thread.start()

    def stop_watchdog(self):
        """Stop the watchdog thread"""
        self.watchdog_stop_event.set()
        if self.watchdog_thread:
            self.watchdog_thread.join(timeout=1)

    def handle_message(self, msg: IPCMessage):
        """Handle incoming messages from UI process"""
        if msg.msg_type == MessageType.TASK_REQUEST:
            self.task_counter += 1
            task_id = self.task_counter

            # Create output queue for this task
            task_output_queue = mp.Queue()

            # Store task info
            self.active_tasks[task_id] = {
                "content": msg.content,
                "process": None,
                "output_queue": task_output_queue,
                "last_update": time.time(),
                "progress": 0
            }

            # Spawn a process to process the task
            # Note: Not daemon to allow child processes
            process = mp.Process(
                target=task_worker_process,
                args=(task_id, msg.content, task_output_queue)
            )
            process.start()
            self.active_tasks[task_id]["process"] = process

            # Send immediate acknowledgment
            self.output_queue.put(IPCMessage(
                msg_type=MessageType.TASK_STATUS,
                task_id=task_id,
                status="Task started",
                progress=0
            ))

        elif msg.msg_type == MessageType.TASK_CANCEL:
            # Cooperative cancellation - ask process to stop gracefully
            task_id = msg.task_id
            if task_id in self.active_tasks:
                task_info = self.active_tasks[task_id]
                process = task_info.get("process")
                if process and process.is_alive():
                    # Send SIGTERM for graceful termination
                    process.terminate()
                    self.output_queue.put(IPCMessage(
                        msg_type=MessageType.TASK_STATUS,
                        task_id=task_id,
                        status="Cancelling task (graceful)...",
                        progress=0
                    ))

        elif msg.msg_type == MessageType.TASK_KILL:
            # Forceful termination - kill the process immediately
            task_id = msg.task_id
            if task_id in self.active_tasks:
                task_info = self.active_tasks[task_id]
                process = task_info.get("process")
                if process and process.is_alive():
                    # Force kill with SIGKILL
                    try:
                        os.kill(process.pid, signal.SIGKILL)
                        self.output_queue.put(IPCMessage(
                            msg_type=MessageType.TASK_STATUS,
                            task_id=task_id,
                            status="Task forcefully killed",
                            progress=0
                        ))
                    except ProcessLookupError:
                        # Process already dead
                        pass

        elif msg.msg_type == MessageType.TASK_RESTART:
            # Restart a task (kill if running, then start new)
            task_id = msg.task_id
            if task_id in self.active_tasks:
                task_info = self.active_tasks[task_id]
                process = task_info.get("process")
                if process and process.is_alive():
                    # Kill existing process
                    try:
                        os.kill(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

                # Start a new process with the same content
                content = task_info["content"]
                task_output_queue = mp.Queue()

                self.active_tasks[task_id] = {
                    "content": content,
                    "process": None,
                    "output_queue": task_output_queue,
                    "last_update": time.time(),
                    "progress": 0
                }

                process = mp.Process(
                    target=task_worker_process,
                    args=(task_id, content, task_output_queue),
                    daemon=True
                )
                process.start()
                self.active_tasks[task_id]["process"] = process

                # Send status update
                self.output_queue.put(IPCMessage(
                    msg_type=MessageType.TASK_STATUS,
                    task_id=task_id,
                    status="Task restarted",
                    progress=0
                ))

        elif msg.msg_type == MessageType.SHUTDOWN:
            self.running = False

    def run(self):
        """Main worker loop"""
        self.start_watchdog()

        while self.running:
            try:
                # Check for task output
                for task_id, task_info in list(self.active_tasks.items()):
                    try:
                        msg = task_info["output_queue"].get_nowait()
                        self.output_queue.put(msg)
                        task_info["last_update"] = time.time()
                        if msg.progress:
                            task_info["progress"] = msg.progress

                        # Clean up completed tasks
                        if msg.msg_type == MessageType.TASK_COMPLETE:
                            if task_id in self.active_tasks:
                                del self.active_tasks[task_id]
                    except queue.Empty:
                        pass

                # Check for UI messages
                try:
                    msg = self.input_queue.get(timeout=0.1)
                    self.handle_message(msg)
                except queue.Empty:
                    continue

            except Exception as e:
                # Log error but keep running
                self.output_queue.put(IPCMessage(
                    msg_type=MessageType.TASK_STATUS,
                    task_id=-1,
                    status=f"Error: {str(e)}",
                    progress=0
                ))

        # Cleanup
        self.stop_watchdog()
        for task_id, task_info in self.active_tasks.items():
            process = task_info.get("process")
            if process and process.is_alive():
                try:
                    os.kill(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


class UIFrontend:
    """UI Frontend process using curses"""

    def __init__(self, input_queue: mp.Queue, output_queue: mp.Queue):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.tasks = {}
        self.task_counter = 0
        self.running = True
        self.status_messages = []
        self.selected_task = 0
        self.needs_redraw = True

    def add_status_message(self, msg: str):
        """Add a status message to display"""
        self.status_messages.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        if len(self.status_messages) > 10:
            self.status_messages.pop(0)

    def process_incoming_messages(self):
        """Process messages from backend worker"""
        try:
            while True:
                msg = self.input_queue.get_nowait()

                if msg.msg_type == MessageType.TASK_STATUS:
                    if msg.task_id not in self.tasks:
                        self.tasks[msg.task_id] = {
                            "status": "Unknown",
                            "progress": 0,
                            "content": ""
                        }

                    self.tasks[msg.task_id]["status"] = msg.status
                    self.tasks[msg.task_id]["progress"] = msg.progress

                    if msg.task_id > 0:
                        self.add_status_message(f"Task {msg.task_id}: {msg.status}")
                    self.needs_redraw = True

                elif msg.msg_type == MessageType.TASK_COMPLETE:
                    if msg.task_id in self.tasks:
                        self.tasks[msg.task_id]["status"] = msg.status
                        self.tasks[msg.task_id]["progress"] = 100
                    self.add_status_message(f"Task {msg.task_id} completed!")
                    self.needs_redraw = True

        except queue.Empty:
            pass

    def send_task_request(self, content: str):
        """Send a task request to backend"""
        self.output_queue.put(IPCMessage(
            msg_type=MessageType.TASK_REQUEST,
            content=content
        ))
        self.add_status_message(f"New task requested: {content}")
        self.needs_redraw = True

    def send_shutdown(self):
        """Send shutdown signal to backend"""
        self.output_queue.put(IPCMessage(msg_type=MessageType.SHUTDOWN))

    def send_cancel(self, task_id: int):
        """Send cancel request (graceful termination)"""
        if task_id in self.tasks:
            self.output_queue.put(IPCMessage(
                msg_type=MessageType.TASK_CANCEL,
                task_id=task_id
            ))
            self.add_status_message(f"Cancelling task {task_id} (graceful)...")
            self.needs_redraw = True

    def send_kill(self, task_id: int):
        """Send kill request (forceful termination)"""
        if task_id in self.tasks:
            self.output_queue.put(IPCMessage(
                msg_type=MessageType.TASK_KILL,
                task_id=task_id
            ))
            self.add_status_message(f"Killing task {task_id} (forceful)...")
            self.needs_redraw = True

    def send_restart(self, task_id: int):
        """Send restart request"""
        if task_id in self.tasks:
            self.output_queue.put(IPCMessage(
                msg_type=MessageType.TASK_RESTART,
                task_id=task_id
            ))
            self.add_status_message(f"Restarting task {task_id}...")
            self.needs_redraw = True

    def draw_ui(self, stdscr):
        """Draw the TUI interface"""
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Title
        title = "=== Learnable Texture Demo (Forceful Kill Support) ==="
        stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD)

        # Instructions
        instructions = [
            "1-9: Create new task",
            "Arrow keys: Navigate tasks",
            "k: Graceful cancel (SIGTERM)",
            "K: Forceful kill (SIGKILL)",
            "r: Restart task",
            "q: Quit"
        ]
        for i, line in enumerate(instructions):
            stdscr.addstr(2 + i, 2, line)

        # Active Tasks Section
        stdscr.addstr(9, 2, "Active Tasks:", curses.A_BOLD)

        if not self.tasks:
            stdscr.addstr(10, 4, "No active tasks. Press 1-9 to create one.")
        else:
            # Sort tasks by ID
            sorted_tasks = sorted(self.tasks.items())

            for idx, (task_id, info) in enumerate(sorted_tasks):
                if idx >= height - 18:  # Don't overflow screen
                    break

                y = 11 + idx

                # Selection indicator
                prefix = "> " if idx == self.selected_task else "  "

                # Task info
                task_line = f"{prefix}Task {task_id}: {info['status']}"
                stdscr.addstr(y, 4, task_line)

                # Progress bar
                progress = info['progress']
                bar_width = 30
                filled = int(bar_width * progress / 100)
                bar = "[" + "█" * filled + "░" * (bar_width - filled) + "]"
                stdscr.addstr(y, 4 + len(task_line) + 2, f"{bar} {progress}%")

        # Status Messages Section
        status_y = height - 12
        stdscr.addstr(status_y, 2, "Status Messages:", curses.A_BOLD)

        for i, msg in enumerate(self.status_messages):
            if status_y + 1 + i >= height - 1:
                break
            stdscr.addstr(status_y + 1 + i, 4, msg)

        # Footer
        footer = "Press 'q' to quit"
        stdscr.addstr(height - 1, (width - len(footer)) // 2, footer)

        # Use doupdate() for smoother updates
        curses.doupdate()

    def run(self, stdscr):
        """Main UI loop"""
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(True)  # Non-blocking input
        stdscr.timeout(50)  # 50ms timeout for input

        while self.running:
            # Process incoming messages
            self.process_incoming_messages()

            # Only redraw if something changed
            if self.needs_redraw:
                self.draw_ui(stdscr)
                self.needs_redraw = False

            # Handle input
            try:
                key = stdscr.getch()

                if key == ord('q'):
                    self.running = False
                    self.send_shutdown()

                # Create tasks with number keys
                elif ord('1') <= key <= ord('9'):
                    task_num = key - ord('0')
                    content = f"Texture analysis {task_num}"
                    self.send_task_request(content)

                # Navigate tasks
                elif key == curses.KEY_UP:
                    if self.tasks:
                        self.selected_task = max(0, self.selected_task - 1)
                        self.needs_redraw = True

                elif key == curses.KEY_DOWN:
                    if self.tasks:
                        self.selected_task = min(len(self.tasks) - 1, self.selected_task + 1)
                        self.needs_redraw = True

                # Graceful cancel (SIGTERM)
                elif key == ord('k'):
                    if self.tasks:
                        sorted_tasks = sorted(self.tasks.items())
                        if 0 <= self.selected_task < len(sorted_tasks):
                            task_id = sorted_tasks[self.selected_task][0]
                            self.send_cancel(task_id)

                # Forceful kill (SIGKILL)
                elif key == ord('K'):
                    if self.tasks:
                        sorted_tasks = sorted(self.tasks.items())
                        if 0 <= self.selected_task < len(sorted_tasks):
                            task_id = sorted_tasks[self.selected_task][0]
                            self.send_kill(task_id)

                # Restart selected task
                elif key == ord('r'):
                    if self.tasks:
                        sorted_tasks = sorted(self.tasks.items())
                        if 0 <= self.selected_task < len(sorted_tasks):
                            task_id = sorted_tasks[self.selected_task][0]
                            self.send_restart(task_id)

            except curses.error:
                pass


def ui_process(input_queue: mp.Queue, output_queue: mp.Queue):
    """Entry point for UI process"""
    ui = UIFrontend(input_queue, output_queue)
    try:
        curses.wrapper(ui.run)
    except Exception as e:
        print(f"UI process error: {e}")
        print("Note: The TUI requires an interactive terminal.")
        print("Try running in a proper terminal or with: python main.py")
        ui.send_shutdown()


def worker_process(input_queue: mp.Queue, output_queue: mp.Queue):
    """Entry point for worker process"""
    worker = BackendWorker(input_queue, output_queue)
    worker.run()


def main():
    """Main entry point - spawns both processes"""
    print("Starting Learnable Texture Demo (with Forceful Kill Support)...")
    print("Setting up IPC queues...")

    # Check if we're in an interactive terminal
    import sys
    if not sys.stdin.isatty():
        print("\nWarning: Not running in an interactive terminal.")
        print("The TUI requires a proper terminal to function.")
        print("Try running directly in a terminal: python main.py")
        print("\nHowever, the backend worker will still run.")
        print("You can test the IPC communication by running in a proper terminal.\n")

    # Create queues for bidirectional communication
    ui_to_worker = mp.Queue()
    worker_to_ui = mp.Queue()

    print("Starting worker process...")
    worker = mp.Process(
        target=worker_process,
        args=(ui_to_worker, worker_to_ui)
    )
    worker.start()

    print("Starting UI process...")
    ui = mp.Process(
        target=ui_process,
        args=(worker_to_ui, ui_to_worker),
        daemon=True
    )
    ui.start()

    print("\nDemo is running!")
    print("Use the TUI to create tasks (press 1-9)")
    print("Press 'k' for graceful cancel, 'K' for forceful kill")
    print("Press Ctrl+C to exit\n")

    try:
        # Wait for UI to finish
        ui.join()
    except KeyboardInterrupt:
        print("\nShutting down...")

    # Cleanup
    if worker.is_alive():
        worker.terminate()
    if ui.is_alive():
        ui.terminate()

    print("Demo stopped.")


if __name__ == "__main__":
    # Required for multiprocessing on some platforms
    mp.set_start_method('spawn', force=True)
    main()
