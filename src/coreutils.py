#!/usr/bin/python3

import os
import shutil
import subprocess

version = input("version: ")

# Download
subprocess.run(["wget", f"https://ftp.gnu.org/gnu/coreutils/coreutils-{version}.tar.xz"], check=True)

# Extract
subprocess.run(["tar", "-xf", f"coreutils-{version}.tar.xz"], check=True)

# Enter directory
os.chdir(f"coreutils-{version}")

# Configure + Build
subprocess.run(["./configure"], check=True)
subprocess.run(["make"], check=True)

# --- Collect compiled binaries ---
bin_folder = f"../coreutils-{version}-bin"
os.makedirs(bin_folder, exist_ok=True)

src_dir = "src"

# Copy only executable files from src/
for f in os.listdir(src_dir):
    full = os.path.join(src_dir, f)
    if os.path.isfile(full) and os.access(full, os.X_OK):
        shutil.copy(full, bin_folder)

# --- Zip the binary folder ---
zip_name = f"coreutils-{version}-bin.zip"
shutil.make_archive(f"coreutils-{version}-bin", "zip", bin_folder)

print(f"\nDone! Binaries saved to: {bin_folder}")
print(f"Zip archive created: {zip_name}")
