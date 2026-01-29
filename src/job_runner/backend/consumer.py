import multiprocessing as mp
import subprocess
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class OutputLine:
    pid: int
    line: str


class BackEndConsumer:
    def __init__(self, input_queue: mp.Queue, output_queue: mp.Queue) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.thread_pool = []

    def run(self) -> None:
        while True:
            item = self.input_queue.get()
            print(f"Got item from input queue: {item}")
            if item is None:  # Shutdown signal
                break
            thread = threading.Thread(target=self.process_item, args=(item,))
            thread.start()
            self.thread_pool.append(thread)

        while True:
            out = self.output_queue.get()
            print(f"Received output from PID {out.pid}: {out.line}")
            if out is None:  # Shutdown signal
                break

    def process_item(self, item: int):
        demo_command = "./simulated_worker.sh {}".format(item)
        process = subprocess.Popen(
            demo_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        process_stdout = process.stdout
        assert process_stdout is not None
        for line in iter(process_stdout.readline, ""):
            line = line.strip()
            if line:
                out = OutputLine(pid=process.pid, line=line)
                self.output_queue.put(out)


if __name__ == "__main__":
    input_queue = mp.Queue()
    output_queue = mp.Queue()
    for i in range(5):
        input_queue.put(i + 1)
    input_queue.put(None)  # Shutdown signal
    consumer = BackEndConsumer(input_queue, output_queue)
    consumer.run()
