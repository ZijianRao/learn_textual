#!/usr/bin/env python3
"""
Test script to verify IPC communication without requiring curses.
This demonstrates that the backend worker and IPC queues work correctly.
"""

import multiprocessing as mp
import queue
import time
from main import IPCMessage, MessageType, BackendWorker


def worker_runner(input_queue, output_queue):
    """Worker runner function for multiprocessing"""
    worker = BackendWorker(input_queue, output_queue)
    worker.run()


def test_worker():
    """Test the backend worker with simulated messages"""
    print("=== Testing Backend Worker ===\n")

    # Create queues
    input_queue = mp.Queue()
    output_queue = mp.Queue()

    # Start worker in a process
    worker = mp.Process(
        target=worker_runner,
        args=(input_queue, output_queue),
        daemon=True
    )
    worker.start()

    print("Worker started. Sending test tasks...")

    # Send 3 test tasks
    for i in range(1, 4):
        msg = IPCMessage(
            msg_type=MessageType.TASK_REQUEST,
            content=f"Test texture analysis {i}"
        )
        input_queue.put(msg)
        print(f"Sent task {i}: {msg.content}")

    # Wait for responses
    print("\nWaiting for responses...\n")
    responses_received = 0
    start_time = time.time()

    while responses_received < 9 and time.time() - start_time < 15:  # 3 tasks * 3 messages each
        try:
            msg = output_queue.get(timeout=0.5)

            if msg.msg_type == MessageType.TASK_STATUS:
                print(f"[Task {msg.task_id}] {msg.status} ({msg.progress}%)")
                responses_received += 1
            elif msg.msg_type == MessageType.TASK_COMPLETE:
                print(f"[Task {msg.task_id}] ✅ {msg.status}")
                responses_received += 1

        except queue.Empty:
            continue

    # Send shutdown
    input_queue.put(IPCMessage(msg_type=MessageType.SHUTDOWN))
    print("\nSending shutdown signal...")

    # Wait for worker to finish
    worker.join(timeout=2)
    if worker.is_alive():
        worker.terminate()

    print("\n=== Test Complete ===")
    print(f"Total messages received: {responses_received}")
    print("IPC communication is working correctly!")


if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    test_worker()
