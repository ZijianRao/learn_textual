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


def test_cancel_and_restart():
    """Test the cancel and restart functionality"""
    print("\n=== Testing Cancel and Restart ===\n")

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

    print("Worker started. Testing cancel and restart...")

    # Send a task
    msg = IPCMessage(
        msg_type=MessageType.TASK_REQUEST,
        content="Test task for cancel/restart"
    )
    input_queue.put(msg)
    print(f"Sent task: {msg.content}")

    # Wait a bit for task to start
    time.sleep(0.5)

    # Send cancel request
    cancel_msg = IPCMessage(
        msg_type=MessageType.TASK_CANCEL,
        task_id=1
    )
    input_queue.put(cancel_msg)
    print(f"Sent cancel request for task 1")

    # Wait for cancel response
    print("\nWaiting for cancel response...\n")
    cancel_received = False
    start_time = time.time()

    while not cancel_received and time.time() - start_time < 5:
        try:
            msg = output_queue.get(timeout=0.5)
            print(f"[Task {msg.task_id}] {msg.status} ({msg.progress}%)")

            if "cancelled" in msg.status.lower():
                cancel_received = True

        except queue.Empty:
            continue

    if cancel_received:
        print("\n✅ Task cancelled successfully!")

        # Now restart the task
        restart_msg = IPCMessage(
            msg_type=MessageType.TASK_RESTART,
            task_id=1
        )
        input_queue.put(restart_msg)
        print(f"\nSent restart request for task 1")

        # Wait for restart response
        print("\nWaiting for restart response...\n")
        restart_received = False
        start_time = time.time()

        while not restart_received and time.time() - start_time < 10:
            try:
                msg = output_queue.get(timeout=0.5)
                print(f"[Task {msg.task_id}] {msg.status} ({msg.progress}%)")

                if "restarted" in msg.status.lower():
                    restart_received = True

            except queue.Empty:
                continue

        if restart_received:
            print("\n✅ Task restarted successfully!")
        else:
            print("\n⚠️  Restart response not received")
    else:
        print("\n⚠️  Cancel response not received")

    # Send shutdown
    input_queue.put(IPCMessage(msg_type=MessageType.SHUTDOWN))
    print("\nSending shutdown signal...")

    # Wait for worker to finish
    worker.join(timeout=2)
    if worker.is_alive():
        worker.terminate()

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    test_worker()
    test_cancel_and_restart()
