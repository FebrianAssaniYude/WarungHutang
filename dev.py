import os
import sys
import subprocess
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


class RestartHandler(FileSystemEventHandler):
    def __init__(self, process):
        self.process = process

    def on_modified(self, event):
        if event.is_directory:
            return

        if not event.src_path.endswith(".py"):
            return

        print(f"\n[DEV] Perubahan terdeteksi: {event.src_path}")
        print("[DEV] Restart aplikasi...\n")

        self.process.terminate()
        self.process.wait()

        self.process = subprocess.Popen(
            [sys.executable, os.path.join(PROJECT_DIR, "dev_app.py")]
        )


def run():
    process = subprocess.Popen(
        [sys.executable, os.path.join(PROJECT_DIR, "dev_app.py")]
    )

    event_handler = RestartHandler(process)

    observer = Observer()
    observer.schedule(
        event_handler,
        PROJECT_DIR,
        recursive=True,
    )
    observer.start()

    print("=" * 50)
    print("WARUNG HUTANG - DEVELOPMENT MODE")
    print("=" * 50)
    print("Auto restart : AKTIF")
    print("Tekan Ctrl+C di terminal untuk berhenti.")
    print("=" * 50)

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[DEV] Menghentikan development mode...")

        observer.stop()

        if process.poll() is None:
            process.terminate()

    observer.join()


if __name__ == "__main__":
    run()