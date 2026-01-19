import os
import signal
import subprocess

def kill_port(port):
    print(f"Searching for process on port {port}...")
    try:
        # This finds the PID using the port
        result = subprocess.check_output(["lsof", "-t", f"-i:{port}"])
        pids = result.decode().strip().split("\n")
        for pid in pids:
            if pid:
                print(f"Found PID {pid}. Killing it...")
                os.kill(int(pid), signal.SIGKILL)
        print(f"✅ Port {port} is now clear.")
    except Exception:
        print(f"ℹ️ No active process found on port {port} or lsof not available.")

if __name__ == "__main__":
    kill_port(8081)
    kill_port(8080)