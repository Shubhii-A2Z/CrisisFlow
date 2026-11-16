# CrisisFlow

**Multi-Agent AI for Autonomous Urban Disaster Response and Emergency Mobility Optimization**

A synthetic, interactive simulation of emergency vehicle routing across a city road network.
Five preset scenarios, congestion-aware route coordination, signal recommendations, and a live comparison table.

---

## Project Structure

```
crisis_flow/
├── src/                     # Project root
│   ├── main.py              # FastAPI app entrypoint
│   ├── crisisflow_core.py   # Core simulation: Dijkstra routing, scenarios, coordination
│   ├── server.py            # HTTP server & JSON API
│   ├── run_demo.py          # Demo launcher
│   ├── index.html           # Browser dashboard
│   ├── app.js               # Frontend JS
│   ├── style.css            # Styles
│   ├── render.yaml          # Render.com deployment config
│   └── __init__.py
├── pyproject.toml
└── uv.lock
```

---

## Run the Interactive Demo

> **Requires Python 3.10+ only — no external packages needed.**

**Option 1 — From project root:**
```bash
python src/run_demo.py
```

**Option 2 — From inside `src/`:**
```bash
cd src
python run_demo.py
```

**Option 3 — Via uv from project root:**
```bash
uv run src/run_demo.py
```

Then open `http://127.0.0.1:8000` in your browser.

- Select a scenario (Blocked arterial, Flooded connectors, Rush hour, Multiple emergencies, Roadworks)
- Press **Compare all 5** for a full route/time comparison table
- Use **Advance traffic**, **Close/Open B–C**, fleet selectors, and **Reset scenario**

---

## Run the FastAPI Server

```bash
uv run uvicorn src.main:app --reload
```

---

## Scenarios

| Scenario | Description |
|---|---|
| Blocked arterial | Crash closes B–C; ambulance reroutes |
| Flooded connectors | B–C and E–H closed; fire + ambulance respond |
| Rush hour congestion | No closures but heavy central load |
| Multiple emergencies | Ambulance, fire, police compete for the network |
| Roadworks diversion | D–E closed; two vehicles need separate paths |

---

> **Note:** All routes, times, and differences are synthetic model estimates — not real-world measurements or trained RL/MARL results.
