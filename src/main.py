#!/usr/bin/env python3
import threading
import subprocess
import re
import sys
import time
import json

try:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext
except Exception as e:
    print("Tkinter is required to run this program. Install tkinter for your Python distribution.", e)
    raise

# Prefer 'requests' for HTTP; if not available, try urllib
try:
    import requests
except Exception:
    requests = None
    import urllib.request as _urllib

# Version comparison: try packaging.version, fallback to distutils or a simple comparator
try:
    from packaging import version as _packaging_version
    def parse_version(v):
        return _packaging_version.Version(v)
    def version_gt(a, b):
        return parse_version(a) > parse_version(b)
except Exception:
    # fallback: distutils (works in many environments)
    try:
        from distutils.version import LooseVersion as _LooseVersion
        def parse_version(v):
            return _LooseVersion(v)
        def version_gt(a, b):
            return parse_version(a) > parse_version(b)
    except Exception:
        # final fallback: simple semantic splitter (handles numeric dotted versions)
        def parse_version(v):
            parts = []
            for p in re.split(r'[.\-+]', str(v)):
                if p.isdigit():
                    parts.append(int(p))
                else:
                    # non-numeric fallback
                    parts.append(p)
            return parts
        def version_gt(a, b):
            pa = parse_version(a)
            pb = parse_version(b)
            return pa > pb

# -----------------------------
# Local (current) versions
# -----------------------------
curl_version = "8.17.0"
bash_version = "5.3"
coreutils_version = "9.9"

# Build commands (as you specified)
BUILD_COMMANDS = {
    "coreutils": "gnome-terminal -- /usr/bin/coreutils",   # user-provided command
    "bash": "gnome-terminal -- /usr/bin/build-bash",
    "curl": "gnome-terminal -- /usr/bin/build-curl",
}

# -----------------------------
# Utilities: HTTP GET wrapper
# -----------------------------
def http_get_text(url, timeout=12):
    """Fetch text content from URL. Use requests if available, otherwise urllib."""
    if requests:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text
    else:
        with _urllib.urlopen(url, timeout=timeout) as resp:
            raw = resp.read()
            # try to decode
            return raw.decode('utf-8', errors='replace')

# -----------------------------
# Logging helper (GUI will set this)
# -----------------------------
_log_widget = None
_log_lock = threading.Lock()

def attach_logger(widget):
    global _log_widget
    _log_widget = widget

def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    # Print to stdout as well (useful when running headless)
    print(line)
    if _log_widget:
        with _log_lock:
            _log_widget.configure(state='normal')
            _log_widget.insert(tk.END, line + "\n")
            _log_widget.see(tk.END)
            _log_widget.configure(state='disabled')

# -----------------------------
# Fetchers
# -----------------------------
def fetch_latest_coreutils_from_github(log=log):
    """
    Use GitHub tags API to get latest tag name from coreutils/coreutils.
    Strips leading 'v' if present.
    """
    url = "https://api.github.com/repos/coreutils/coreutils/tags"
    log(f"[INFO] Fetching coreutils tags from GitHub API: {url}")
    try:
        text = http_get_text(url)
        data = json.loads(text)
        if not isinstance(data, list) or not data:
            log("[WARN] GitHub API returned empty or unexpected data for tags.")
            return None
        tags = []
        for obj in data:
            if isinstance(obj, dict) and "name" in obj:
                tags.append(obj["name"].lstrip("v"))
        if not tags:
            log("[WARN] No tags parsed from GitHub response.")
            return None
        # Sort using version parser and pick latest
        try:
            latest = sorted(tags, key=lambda v: parse_version(v))[-1]
        except Exception:
            latest = tags[0]
        log(f"[INFO] Parsed coreutils tags (sample): {', '.join(tags[:8])}")
        log(f"[INFO] Latest coreutils (from GitHub tags): {latest}")
        return latest
    except Exception as e:
        log(f"[ERROR] Failed to fetch/parse coreutils tags: {e}")
        return None

def fetch_latest_bash_from_arch_pkgbuild():
    url = "https://gitlab.archlinux.org/archlinux/packaging/packages/bash/-/raw/main/PKGBUILD"
    log(f"[INFO] Fetching bash PKGBUILD from Arch: {url}")

    try:
        text = http_get_text(url)

        # Remove comments
        lines = []
        for line in text.splitlines():
            if "#" in line:
                line = line.split("#", 1)[0]
            if line.strip():
                lines.append(line.strip())

        clean = "\n".join(lines)

        # Extract _basever=...
        m = re.search(
            r'_basever\s*=\s*["\']?([0-9]+\.[0-9]+)',
            clean
        )

        if not m:
            log("[WARN] Could not find _basever in PKGBUILD")
            return None

        basever = m.group(1)
        log(f"[INFO] Bash base version: {basever}")
        return basever

    except Exception as e:
        log(f"[ERROR] Failed to fetch/parse PKGBUILD: {e}")
        return None


def fetch_latest_curl_from_curlsite(log=log):
    """
    Parse curl.se download page for curl-X.Y.Z.tar.gz filenames.
    """
    url = "https://curl.se/download/"
    log(f"[INFO] Fetching curl download page: {url}")
    try:
        text = http_get_text(url)
        matches = re.findall(r'curl-([0-9]+\.[0-9]+\.[0-9]+)\.tar\.gz', text)
        if not matches:
            log("[WARN] No curl versions detected on page")
            return None
        # sort and pick last
        try:
            latest = sorted(matches, key=lambda v: parse_version(v))[-1]
        except Exception:
            latest = matches[-1]
        log(f"[INFO] Found {len(matches)} curl versions; latest: {latest}")
        return latest
    except Exception as e:
        log(f"[ERROR] Failed to fetch/parse curl site: {e}")
        return None

# -----------------------------
# Coordinator: check all versions (threaded)
# -----------------------------
class VersionChecker(threading.Thread):
    def __init__(self, update_callback):
        super().__init__(daemon=True)
        self.update_callback = update_callback  # function(name, latest, up_status, fetch_ok)
        self._stop = False

    def run(self):
        log("[INFO] Starting version check...")
        results = {}

        # coreutils
        latest_core = fetch_latest_coreutils_from_github()
        ok_core = latest_core is not None
        if ok_core:
            up_core = version_gt(latest_core, coreutils_version)
        else:
            up_core = None
        self.update_callback("coreutils", latest_core, up_core, ok_core)

        # bash
        latest_bash = fetch_latest_bash_from_arch_pkgbuild()
        ok_bash = latest_bash is not None
        if ok_bash:
            up_bash = version_gt(latest_bash, bash_version)
        else:
            up_bash = None
        self.update_callback("bash", latest_bash, up_bash, ok_bash)

        # curl
        latest_curl = fetch_latest_curl_from_curlsite()
        ok_curl = latest_curl is not None
        if ok_curl:
            up_curl = version_gt(latest_curl, curl_version)
        else:
            up_curl = None
        self.update_callback("curl", latest_curl, up_curl, ok_curl)

        log("[INFO] Version check completed.")

# -----------------------------
# GUI
# -----------------------------
class BuildManagerGUI:
    def __init__(self, master):
        self.master = master
        master.title("Build Manager")
        master.geometry("900x700")

        # Frame: status + buttons
        top_frame = tk.Frame(master)
        top_frame.pack(fill=tk.X, padx=12)

        # Left: status labels
        status_frame = tk.LabelFrame(top_frame, text="Status", padx=8, pady=8)
        status_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=6, pady=6)

        self.status_labels = {}
        self.latest_labels = {}
        self.local_labels = {}

        for name in ("coreutils", "bash", "curl"):
            row = tk.Frame(status_frame)
            row.pack(fill=tk.X, pady=4)
            lbl_name = tk.Label(row, text=name.capitalize(), width=12, anchor="w", font=("Segoe UI", 10, "bold"))
            lbl_name.pack(side=tk.LEFT)
            lbl_local = tk.Label(row, text=f"local: --", width=18, anchor="w", relief="sunken")
            lbl_local.pack(side=tk.LEFT, padx=4)
            lbl_latest = tk.Label(row, text=f"latest: --", width=18, anchor="w", relief="sunken")
            lbl_latest.pack(side=tk.LEFT, padx=4)
            lbl_status = tk.Label(row, text="status: ???", width=22, anchor="w", relief="ridge")
            lbl_status.pack(side=tk.LEFT, padx=4)
            self.local_labels[name] = lbl_local
            self.latest_labels[name] = lbl_latest
            self.status_labels[name] = lbl_status

        # Initialize local versions display
        self.local_labels["coreutils"].config(text=f"local: {coreutils_version}")
        self.local_labels["bash"].config(text=f"local: {bash_version}")
        self.local_labels["curl"].config(text=f"local: {curl_version}")

        # Right: buttons (build)
        button_frame = tk.LabelFrame(top_frame, text="Build Commands", padx=8, pady=8)
        button_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=6, pady=6)

        self.buttons = {}
        for name in ("coreutils", "bash", "curl"):
            btn = tk.Button(button_frame,
                            text=f"{BUILD_COMMANDS[name].replace('gnome-terminal -- ', '')}",
                            width=40,
                            command=lambda n=name: self._on_build_click(n))
            btn.pack(pady=6)
            self.buttons[name] = btn

        # Re-check button and hint
        ctrl_frame = tk.Frame(master)
        ctrl_frame.pack(fill=tk.X, padx=12, pady=(2,8))
        self.recheck_btn = tk.Button(ctrl_frame, text="Re-check Versions (Verbose)", bg="lightblue",
                                     font=("Segoe UI", 11, "bold"), command=self.start_version_check)
        self.recheck_btn.pack(side=tk.LEFT, padx=8)

        self.refresh_hint = tk.Label(ctrl_frame, text="Logs and details appear below.", anchor="w")
        self.refresh_hint.pack(side=tk.LEFT, padx=8)

        # Log scrolledtext
        log_frame = tk.LabelFrame(master, text="Verbose Log", padx=8, pady=8)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        self.log_widget = scrolledtext.ScrolledText(log_frame, width=100, height=20, font=("Courier", 10))
        self.log_widget.pack(fill=tk.BOTH, expand=True)
        self.log_widget.configure(state='disabled')

        # attach logger
        attach_logger(self.log_widget)

        # Bottom: status bar
        self.status_bar = tk.Label(master, text="Ready", bd=1, relief="sunken", anchor="w")
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Start first check
        self.start_version_check()

    def update_status(self, name, latest, up_status, fetch_ok):
        """
        Called from version checker thread (we must schedule UI updates on main thread)
        latest: string or None
        up_status: True (update available) / False (up-to-date) / None (could not determine)
        fetch_ok: True/False
        """
        def _apply():
            # latest label
            if latest:
                self.latest_labels[name].config(text=f"latest: {latest}")
            else:
                self.latest_labels[name].config(text=f"latest: N/A")

            # status label and colors
            lbl = self.status_labels[name]
            btn = self.buttons[name]

            if up_status is True:
                lbl.config(text="UPDATE AVAILABLE", bg="yellow", fg="black")
                btn.config(bg="yellow")
                self.status_bar.config(text=f"{name}: update available ({latest})")
            elif up_status is False:
                lbl.config(text="up-to-date", bg="lightgreen", fg="black")
                btn.config(bg="lightgreen")
                self.status_bar.config(text=f"{name}: up-to-date")
            else:
                # None -> fetch failed or unknown
                lbl.config(text="fetch failed / unknown", bg="tomato", fg="white")
                btn.config(bg="SystemButtonFace")
                self.status_bar.config(text=f"{name}: could not determine latest version")

            # always update local display (use current variable)
            if name == "coreutils":
                self.local_labels[name].config(text=f"local: {coreutils_version}")
            elif name == "bash":
                self.local_labels[name].config(text=f"local: {bash_version}")
            elif name == "curl":
                self.local_labels[name].config(text=f"local: {curl_version}")

        # schedule on main thread
        self.master.after(0, _apply)

    def start_version_check(self):
        self.recheck_btn.config(state='disabled')
        log("[UI] Triggering version check (in background)...")
        def callback(name, latest, up_status, fetch_ok):
            # forward to GUI updater
            self.update_status(name, latest, up_status, fetch_ok)
        checker = VersionChecker(update_callback=callback)
        # Re-enable button after thread finishes (we poll thread)
        def poll_thread():
            if checker.is_alive():
                self.master.after(300, poll_thread)
            else:
                self.recheck_btn.config(state='normal')
                log("[UI] Version check finished (background).")
        checker.start()
        self.master.after(300, poll_thread)

    def _on_build_click(self, name):
        cmd = BUILD_COMMANDS.get(name)
        if not cmd:
            messagebox.showerror("Error", f"No command configured for {name}")
            return
        # Ask for confirmation
        if not messagebox.askyesno("Run build command", f"Run command:\n\n{cmd}\n\nThis will be executed as a shell command. Continue?"):
            return
        # run in background
        self._run_command_async(cmd, name)

    def _run_command_async(self, cmd, name):
        log(f"[RUN] Starting build for {name}: {cmd}")
        def _worker():
            try:
                # Use shell=True so user-provided command strings run as-is (this mirrors your earlier behavior)
                proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                out = proc.stdout.strip()
                err = proc.stderr.strip()
                rc = proc.returncode
                if out:
                    log(f"[RUN:{name}] STDOUT:\n{out}")
                if err:
                    log(f"[RUN:{name}] STDERR:\n{err}")
                if rc == 0:
                    log(f"[OK] Build command finished successfully: {cmd}")
                    self.master.after(0, lambda: messagebox.showinfo("Build finished", f"Command finished successfully:\n\n{cmd}"))
                else:
                    log(f"[FAIL] Build command exited with code {rc}: {cmd}")
                    self.master.after(0, lambda: messagebox.showerror("Build failed", f"Command exited with code {rc}:\n\n{cmd}\n\nSee log for details."))
            except Exception as e:
                log(f"[ERROR] Exception while running build command: {e}")
                self.master.after(0, lambda: messagebox.showerror("Build error", f"Exception while running command:\n\n{e}"))
        threading.Thread(target=_worker, daemon=True).start()

# -----------------------------
# Helper: make version checker update GUI properly
# -----------------------------
def make_update_callback(gui):
    def callback(name, latest, up_status, fetch_ok):
        # gui.update_status(name, latest, up_status, fetch_ok)
        # We want to forward with fetch_ok semantics:
        gui.update_status(name, latest, up_status, fetch_ok)
    return callback

# -----------------------------
# Bootstrap
# -----------------------------
def main():
    root = tk.Tk()
    gui = BuildManagerGUI(root)
    # Set callback wrapper for VersionChecker (so tests could call it directly if needed)
    root.mainloop()

if __name__ == "__main__":
    main()

