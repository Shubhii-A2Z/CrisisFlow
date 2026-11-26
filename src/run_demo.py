"""Launch the local or hosted CrisisFlow evaluation demo.

This script now supports an optional ``--real-data`` flag that enables loading a
real‑world road network from OpenStreetMap via :pyclass:`graph_loader.GraphLoader`.
The flag is translated into environment variables read by ``crisisflow_core``
so the server module (which creates the simulation at import time) uses the
chosen mode.
"""

import os
import sys
import argparse
from pathlib import Path
from http.server import ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Argument handling – must happen BEFORE we import ``server`` because the server
# creates a ``CitySimulation`` instance at module import time.
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Run CrisisFlow demo")
parser.add_argument(
    "--real-data",
    action="store_true",
    help="Load a real OSM road network (requires optional packages osmnx, networkx)",
)
parser.add_argument(
    "--area",
    type=str,
    default="Manhattan, New York, USA",
    help="OSM place query for real‑data mode (ignored in synthetic mode)",
)
args = parser.parse_args()

if args.real_data:
    os.environ["CRISISFLOW_REAL_DATA"] = "1"
    os.environ["CRISISFLOW_AREA"] = args.area
else:
    os.environ["CRISISFLOW_REAL_DATA"] = "0"

# Ensure src/ is on the path when invoked as `python src/run_demo.py` from project root
sys.path.insert(0, str(Path(__file__).parent))

# Import after env vars are set so the server picks up the correct mode
from server import Handler

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    display_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print(f"CrisisFlow interactive prototype: http://{display_host}:{port}")
    mode = "Real‑data" if os.getenv("CRISISFLOW_REAL_DATA") == "1" else "Synthetic"
    print(f"Running in {mode} mode")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
