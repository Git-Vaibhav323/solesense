"""
SoleSense — Live FSR Viewer
Polls the running receiver over HTTP. Works in any terminal.

Usage:
    Terminal 1:  python -m hardware.esp32_receiver
    Terminal 2:  python watch_fsr.py
"""

import time
import urllib.request
import urllib.error
import json

LATEST_URL = "http://127.0.0.1:5005/api/latest"
HEALTH_URL = "http://127.0.0.1:5005/api/health"


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:
        return 0, {}


print()
print("=" * 60)
print("  SoleSense — Live FSR Viewer")
print("  Press Ctrl+C to stop")
print("=" * 60)
print()

# Wait for receiver
for i in range(15):
    code, body = get(HEALTH_URL)
    if code == 200:
        print(f"  Receiver ready. Total received so far: {body.get('total_received', 0)}")
        break
    print(f"  Waiting for receiver on port 5005... ({i+1}/15)")
    time.sleep(1)
else:
    print()
    print("  ERROR: cannot reach receiver at localhost:5005")
    print("  Run this first:  python -m hardware.esp32_receiver")
    raise SystemExit(1)

print()
print(f"  {'FSR1':>6}  {'FSR2':>6}  {'FSR3':>6}  {'FSR4':>6}  {'TEMP':>8}  {'RATE':>7}  {'TOTAL':>7}")
print(f"  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*8}  {'-'*7}  {'-'*7}")

seen = 0
while True:
    code, pkt = get(LATEST_URL)

    if code == 200 and pkt.get("timestamp", 0) != seen:
        seen = pkt.get("timestamp", 0)
        temp = f"{pkt['temperature']:.1f}C" if pkt.get("temperature") else "N/A"
        conn = "LIVE" if pkt.get("connected") else "WAIT"
        print(
            f"  {pkt['fsr1']:>6}  {pkt['fsr2']:>6}  "
            f"{pkt['fsr3']:>6}  {pkt['fsr4']:>6}  "
            f"{temp:>8}  "
            f"{pkt['rate_hz']:>5.1f}Hz  "
            f"{pkt['total']:>7}  {conn}"
        )
    elif code == 204:
        print("  [waiting for ESP32 packets...]")

    time.sleep(0.1)
