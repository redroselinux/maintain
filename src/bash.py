#!/usr/bin/python3

import os
import shutil
import subprocess

version = input("version: ")

# Download
subprocess.run(["wget", f"https://ftp.gnu.org/gnu/bash/bash-{version}.tar.gz"], check=True)

# Extract
subprocess.run(["tar", "-xf", f"bash-{version}.tar.gz"], check=True)

# Enter directory
os.chdir(f"bash-{version}")

# Configure + Build
subprocess.run(["./configure"], check=True)
subprocess.run(["make"], check=True)

# --- Collect compiled binaries ---
bin_folder = f"../bash-{version}-bin"
os.makedirs(bin_folder, exist_ok=True)

# Main bash binary
bash_binary = "bash"
if os.path.isfile(bash_binary) and os.access(bash_binary, os.X_OK):
    shutil.copy(bash_binary, bin_folder)

# Other possible executables
extras = ["bashbug", "bashbug.sh"]
for f in extras:
    if os.path.isfile(f) and os.access(f, os.X_OK):
        shutil.copy(f, bin_folder)

# --- Zip the binary folder ---
zip_name = f"bash-{version}-bin.zip"
shutil.make_archive(f"bash-{version}-bin", "zip", bin_folder)

print(f"\nDone! Binaries saved to: {bin_folder}")
print(f"Zip archive created: {zip_name}")
