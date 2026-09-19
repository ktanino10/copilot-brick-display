"""Own the temporary prefix server for CI browser validation."""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
(root / "validation/web.json").unlink(missing_ok=True)
(root / "validation/tribute-web-ci.json").unlink(missing_ok=True)
port = 8877
base = f"http://127.0.0.1:{port}/copilot-brick-display/"
server = subprocess.Popen([sys.executable, "scripts/serve.py", "--port", str(port)], cwd=root,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    ready = False
    for _ in range(100):
        if server.poll() is not None:
            raise RuntimeError("Temporary preview server exited before readiness")
        try:
            with urllib.request.urlopen(base, timeout=1) as response:
                ready = response.status == 200
        except urllib.error.URLError:
            time.sleep(.1)
        if ready:
            break
    if not ready:
        raise TimeoutError("Temporary preview server did not become ready")
    env = {**os.environ, "BASE_URL": base}
    subprocess.run([sys.executable, "-u", "tests/web.py"], cwd=root, env=env, check=True, timeout=600)
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()
