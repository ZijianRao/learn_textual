#!/usr/bin/env python3
"""
Test script to verify forceful kill functionality.
This demonstrates handling truly stuck/unresponsive processes.
"""

import multiprocessing as mp
import queue
import time
import signal
import os
from main_with_forceful_kill import IPCMessage, MessageType, BackendWorker


def worker_runner(input_queue, output_queue):
    """Worker runner function for multiprocessing"""
    worker = BackendWorker(input_queue, output_queue)
    worker.run()


def test_forceful_kill():
    """Test forceful termination of a stuck process"""
    print("=== Testing Forceful Kill ===\n")

    # Create queues
    input_queue = mp.Queue()
    output_queue = mp.Queue()

    # Start worker in a process
    worker = mp.Process(
        target=worker_runner,
        args=(input_queue, output_queue)
    )
    worker.start()

    print("Worker started. Sending test tasks...")

    # Send a task that will get stuck (simulate infinite loop)
    msg = IPCMessage(
        msg_type=MessageType.TASK_REQUEST,
        content="Test task that will get stuck"
    )
    input_queue.put(msg)
    print(f"Sent task: {msg.content}")

    # Wait a bit for task to start
    time.sleep(1)

    # Send forceful kill request
    kill_msg = IPCMessage(
        msg_type=MessageType.TASK_KILL,
        task_id=1
    )
    input_queue.put(kill_msg)
    print(f"Sent forceful kill request for task 1")

    # Wait for kill response
    print("\nWaiting for kill response...\n")
    kill_received = False
    start_time = time.time()

    while not kill_received and time.time() - start_time < 5:
        try:
            msg = output_queue.get(timeout=0.5)
            print(f"[Task {msg.task_id}] {msg.status} ({msg.progress}%)")

            if "killed" in msg.status.lower() or "terminated" in msg.status.lower():
                kill_received = True

        except queue.Empty:
            continue

    if kill_received:
        print("\n✅ Task forcefully killed successfully!")
    else:
        print("\n⚠️  Kill response not received")

    # Send shutdown
    input_queue.put(IPCMessage(msg_type=MessageType.SHUTDOWN))
    print("\nSending shutdown signal...")

    # Wait for worker to finish
    worker.join(timeout=2)
    if worker.is_alive():
        worker.terminate()

    print("\n=== Test Complete ===")


def test_graceful_cancel():
    """Test graceful cancellation"""
    print("\n=== Testing Graceful Cancel ===\n")

    # Create queues
    input_queue = mp.Queue()
    output_queue = mp.Queue()

    # Start worker in a process
    worker = mp.Process(
        target=worker_runner,
        args=(input_queue, output_queue)
    )
    worker.start()

    print("Worker started. Sending test task...")

    # Send a task
    msg = IPCMessage(
        msg_type=MessageType.TASK_REQUEST,
        content="Test task for graceful cancel"
    )
    input_queue.put(msg)
    print(f"Sent task: {msg.content}")

    # Wait a bit for task to start
    time.sleep(0.5)

    # Send graceful cancel request
    cancel_msg = IPCMessage(
        msg_type=MessageType.TASK_CANCEL,
        task_id=1
    )
    input_queue.put(cancel_msg)
    print(f"Sent graceful cancel request for task 1")

    # Wait for cancel response
    print("\nWaiting for cancel response...\n")
    cancel_received = False
    start_time = time.time()

    while not cancel_received and time.time() - start_time < 5:
        try:
            msg = output_queue.get(timeout=0.5)
            print(f"[Task {msg.task_id}] {msg.status} ({msg.progress}%)")

            if "cancelled" in msg.status.lower() or "terminated" in msg.status.lower():
                cancel_received = True

        except queue.Empty:
            continue

    if cancel_received:
        print("\n✅ Task gracefully cancelled successfully!")
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


def test_restart():
    """Test restart functionality"""
    print("\n=== Testing Restart ===\n")

    # Create queues
    input_queue = mp.Queue()
    output_queue = mp.Queue()

    # Start worker in a process
    worker = mp.Process(
        target=worker_runner,
        args=(input_queue, output_queue)
    )
    worker.start()

    print("Worker started. Sending test task...")

    # Send a task
    msg = IPCMessage(
        msg_type=MessageType.TASK_REQUEST,
        content="Test task for restart"
    )
    input_queue.put(msg)
    print(f"Sent task: {msg.content}")

    # Wait a bit for task to start
    time.sleep(0.5)

    # Send restart request
    restart_msg = IPCMessage(
        msg_type=MessageType.TASK_RESTART,
        task_id=1
    )
    input_queue.put(restart_msg)
    print(f"Sent restart request for task 1")

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
    test_graceful_cancel()
    test_forceful_kill()
    test_restart()
