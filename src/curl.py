#!/usr/bin/python3

import os
import shutil
import subprocess
import sys
import threading
import time

version = input("curl version: ")

TOTAL = 708
progress_done = False

def progress_thread():
    for i in range(1, TOTAL + 1):
        if progress_done:
            return
        filled = int((i / TOTAL) * 40)   # 40-char bar
        bar = "█" * filled + "░" * (40 - filled)

        # Clear line + return cursor to start
        sys.stdout.write("\r\033[2K")  # erase full line
        sys.stdout.write(f"[{bar}] {i}/{TOTAL}")
        sys.stdout.flush()

        time.sleep(0.05)
    sys.stdout.write("\n")  # final newline when done

try:
    t = threading.Thread(target=progress_thread)
    t.start()

    subprocess.run(
        ["wget", f"https://curl.se/download/curl-{version}.tar.xz"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    subprocess.run(
        ["tar", "-xf", f"curl-{version}.tar.xz"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    os.chdir(f"curl-{version}")

    subprocess.run(
        ["./configure", "--with-openssl"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    subprocess.run(
        ["make"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    bin_folder = f"../curl-{version}-bin"
    os.makedirs(bin_folder, exist_ok=True)

    src_dir = "src"
    for f in os.listdir(src_dir):
        full = os.path.join(src_dir, f)
        if os.path.isfile(full) and os.access(full, os.X_OK):
            shutil.copy(full, bin_folder)

    shutil.make_archive(f"curl-{version}-bin", "zip", bin_folder)

    progress_done = True
    t.join()

except Exception:
    progress_done = True
    print("error")
    input()

print("\nDone.")
input()

