#!/usr/bin/env python3
"""
Minimal Learnable Texture Python TUI Demo

Architecture:
- Process 1: UI Builder (Frontend) - Uses curses for TUI
- Process 2: Backend Worker - Accepts messages, spawns threads, sends status back
- Communication: multiprocessing.Queue for IPC
"""

import curses
import multiprocessing as mp
import queue
import random
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MessageType(Enum):
    """Message types for IPC communication"""
    TASK_REQUEST = "task_request"
    TASK_STATUS = "task_status"
    TASK_COMPLETE = "task_complete"
    SHUTDOWN = "shutdown"


@dataclass
class IPCMessage:
    """Message structure for IPC communication"""
    msg_type: MessageType
    task_id: Optional[int] = None
    content: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None


class BackendWorker:
    """Backend worker process that handles tasks and spawns threads"""

    def __init__(self, input_queue: mp.Queue, output_queue: mp.Queue):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.active_tasks = {}
        self.task_counter = 0
        self.running = True

    def process_task(self, task_id: int, content: str):
        """Simulate a learnable texture processing task"""
        # Simulate work with random delays
        steps = random.randint(3, 8)

        for i in range(steps):
            if not self.running:
                break

            # Update progress
            progress = int((i + 1) / steps * 100)
            status = f"Processing step {i + 1}/{steps}"

            # Send status update
            self.output_queue.put(IPCMessage(
                msg_type=MessageType.TASK_STATUS,
                task_id=task_id,
                status=status,
                progress=progress
            ))

            # Simulate work
            time.sleep(random.uniform(0.3, 0.8))

        # Mark as complete
        self.output_queue.put(IPCMessage(
            msg_type=MessageType.TASK_COMPLETE,
            task_id=task_id,
            status="Completed successfully",
            progress=100
        ))

        # Clean up
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]

    def handle_message(self, msg: IPCMessage):
        """Handle incoming messages from UI process"""
        if msg.msg_type == MessageType.TASK_REQUEST:
            self.task_counter += 1
            task_id = self.task_counter

            # Store task info
            self.active_tasks[task_id] = {
                "content": msg.content,
                "thread": None
            }

            # Spawn a thread to process the task
            thread = threading.Thread(
                target=self.process_task,
                args=(task_id, msg.content),
                daemon=True
            )
            thread.start()
            self.active_tasks[task_id]["thread"] = thread

            # Send immediate acknowledgment
            self.output_queue.put(IPCMessage(
                msg_type=MessageType.TASK_STATUS,
                task_id=task_id,
                status="Task started",
                progress=0
            ))

        elif msg.msg_type == MessageType.SHUTDOWN:
            self.running = False

    def run(self):
        """Main worker loop"""
        while self.running:
            try:
                # Non-blocking queue check with timeout
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
        self.needs_redraw = True  # Track if screen needs to be redrawn

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

    def draw_ui(self, stdscr):
        """Draw the TUI interface"""
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Title
        title = "=== Learnable Texture Demo ==="
        stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD)

        # Instructions
        instructions = [
            "1-9: Create new task",
            "Arrow keys: Navigate tasks",
            "q: Quit"
        ]
        for i, line in enumerate(instructions):
            stdscr.addstr(2 + i, 2, line)

        # Active Tasks Section
        stdscr.addstr(6, 2, "Active Tasks:", curses.A_BOLD)

        if not self.tasks:
            stdscr.addstr(7, 4, "No active tasks. Press 1-9 to create one.")
        else:
            # Sort tasks by ID
            sorted_tasks = sorted(self.tasks.items())

            for idx, (task_id, info) in enumerate(sorted_tasks):
                if idx >= height - 15:  # Don't overflow screen
                    break

                y = 8 + idx

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

        # Use doupdate() for smoother updates instead of refresh()
        curses.doupdate()

    def run(self, stdscr):
        """Main UI loop"""
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(True)  # Non-blocking input
        stdscr.timeout(50)  # 50ms timeout for input (reduced from 100ms)

        while self.running:
            # Process incoming messages
            self.process_incoming_messages()

            # Only redraw if something changed or if it's the first draw
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

            except curses.error:
                pass


def ui_process(input_queue: mp.Queue, output_queue: mp.Queue):
    """Entry point for UI process"""
    ui = UIFrontend(input_queue, output_queue)
    try:
        curses.wrapper(ui.run)
    except Exception as e:
        # Handle curses initialization errors gracefully
        print(f"UI process error: {e}")
        print("Note: The TUI requires an interactive terminal.")
        print("Try running in a proper terminal or with: python main.py")
        # Send shutdown to worker
        ui.send_shutdown()


def worker_process(input_queue: mp.Queue, output_queue: mp.Queue):
    """Entry point for worker process"""
    worker = BackendWorker(input_queue, output_queue)
    worker.run()


def main():
    """Main entry point - spawns both processes"""
    print("Starting Learnable Texture Demo...")
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
    # UI -> Worker: task requests
    # Worker -> UI: status updates
    ui_to_worker = mp.Queue()
    worker_to_ui = mp.Queue()

    print("Starting worker process...")
    worker = mp.Process(
        target=worker_process,
        args=(ui_to_worker, worker_to_ui),
        daemon=True
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
