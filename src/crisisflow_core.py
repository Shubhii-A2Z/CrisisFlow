"""CrisisFlow multi-scenario evaluation simulator.
Supports both synthetic baseline and real-world OpenStreetMap datasets.
"""
from __future__ import annotations
from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Any
import os
import random

@dataclass
class Road:
    a: str
    b: str
    minutes: float
    capacity: int
    volume: int
    closed: bool = False
    @property
    def congestion(self) -> float:
        return min(2.5, self.volume / max(1, self.capacity))

# ---------------------------------------------------------------------------
# Graph loading - synthetic vs. real OSM data
# ---------------------------------------------------------------------------
from graph_loader import GraphLoader

_real = str(os.getenv("CRISISFLOW_REAL_DATA", "0")).lower() in ("1", "true", "yes")
_loader = GraphLoader(
    real_data=_real,
    area=os.getenv("CRISISFLOW_AREA", "Manhattan, New York, USA"),
)
NODES, ROAD_SEED = _loader.load()
IS_REAL_DATA = _loader.real_data

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

SYNTHETIC_SCENARIOS = {
 "blocked_arterial": {"title":"Blocked arterial", "description":"A crash closes B–C while an ambulance heads to Incident 1.", "closures":[("B","C")], "volumes":{"A-B":12,"B-E":24,"E-F":30}, "missions":[("Ambulance","A","F",5)], "fleet":("G","C")},
 "flooded_roads": {"title":"Flooded connectors", "description":"Floodwater closes B–C and E–H; fire and medical teams respond at once.", "closures":[("B","C"),("E","H")], "volumes":{"D-E":30,"D-G":8,"G-E":9,"E-F":24}, "missions":[("Fire engine","D","H",5),("Ambulance","A","F",4)], "fleet":("G","C")},
 "rush_hour": {"title":"Rush hour congestion", "description":"No road is closed, but the central arterial and hospital approach are heavily loaded.", "closures":[], "volumes":{"A-B":14,"B-C":22,"C-F":15,"B-E":18,"E-F":30,"E-H":12,"D-E":8}, "missions":[("Ambulance","A","F",5),("Police","B","H",3)], "fleet":("G","C")},
 "multiple_incidents": {"title":"Multiple emergencies", "description":"Ambulance, fire and police missions compete for a shared road network.", "closures":[("B","C")], "volumes":{"B-E":13,"E-F":12,"E-H":12}, "missions":[("Ambulance","A","F",5),("Fire engine","D","H",4),("Police","B","H",3)], "fleet":("G","C")},
 "roadworks": {"title":"Roadworks diversion", "description":"Construction closes D–E; a fire engine and ambulance need separate routes.", "closures":[("D","E")], "volumes":{"A-B":11,"B-E":12,"C-H":9,"F-H":8}, "missions":[("Fire engine","D","H",5),("Ambulance","A","F",4)], "fleet":("G","C")},
}

REAL_DATA_SCENARIOS = {
 "blocked_arterial": {
     "title": "Blocked Midtown Corridor (Real OSM)",
     "description": "Traffic collision at Times Square Core (112–113) blocks Broadway; an ambulance is dispatched from 8th Ave / 54th St (101) to Grand Central (115).",
     "closures": [("112", "113")],
     "volumes": {"107-112": 45, "112-118": 40, "111-112": 40},
     "missions": [("Ambulance", "101", "115", 5)],
     "fleet": ("116", "105")
 },
 "flooded_roads": {
     "title": "Severe Flash Flooding & Multiple Closures",
     "description": "Water main break closes 6th Ave corridors (107–108 and 113–114). Fire engines and ambulances must navigate parallel avenues.",
     "closures": [("107", "108"), ("113", "114")],
     "volumes": {"101-106": 35, "106-111": 38, "114-115": 42},
     "missions": [("Fire engine", "111", "104", 5), ("Ambulance", "117", "105", 4)],
     "fleet": ("120", "101")
 },
 "rush_hour": {
     "title": "Evening Peak Congestion (42nd & 34th Crosstown)",
     "description": "Severe rush hour gridlock around Port Authority and Penn Station. Coordinated emergency routing bypasses choked cross streets.",
     "closures": [],
     "volumes": {"111-112": 42, "112-113": 38, "117-118": 38, "113-118": 36},
     "missions": [("Ambulance", "101", "118", 5), ("Police", "116", "110", 3)],
     "fleet": ("116", "105")
 },
 "multiple_incidents": {
     "title": "Multi-Agency Emergency Coordination",
     "description": "Simultaneous structural fire, medical emergency, and police escort near Bryant Park and Rockefeller Center competing for corridor space.",
     "closures": [("112", "113")],
     "volumes": {"107-112": 40, "108-113": 35, "113-114": 30},
     "missions": [
         ("Ambulance", "101", "115", 5),
         ("Fire engine", "117", "104", 4),
         ("Police", "111", "110", 3)
     ],
     "fleet": ("116", "105")
 },
 "roadworks": {
     "title": "Utility Construction Diversion",
     "description": "Scheduled roadworks close 7th Ave & Broadway connector (102–107). Response units reroute onto 8th Ave and 6th Ave corridors.",
     "closures": [("102", "107")],
     "volumes": {"101-106": 32, "103-107": 28, "104-108": 30},
     "missions": [("Fire engine", "101", "119", 5), ("Ambulance", "111", "105", 4)],
     "fleet": ("116", "120")
 }
}

SCENARIOS = REAL_DATA_SCENARIOS if IS_REAL_DATA else SYNTHETIC_SCENARIOS
VEHICLE_COLORS = {"Ambulance": "#ec625e", "Fire engine": "#d3a43f", "Police": "#3671b7"}

def road_key(a: str, b: str) -> str:
    return "-".join(sorted((a, b)))

class CitySimulation:
    def __init__(self):
        self.load_scenario("blocked_arterial")

    def load_scenario(self, scenario_id: str):
        if scenario_id not in SCENARIOS:
            scenario_id = "blocked_arterial"
        self.scenario_id = scenario_id
        spec = SCENARIOS[scenario_id]
        self.tick = 0
        self.roads = [Road(*row) for row in ROAD_SEED]
        for road in self.roads:
            road.closed = tuple(sorted((road.a, road.b))) in {tuple(sorted(e)) for e in spec['closures']}
            road.volume = spec['volumes'].get(road_key(road.a, road.b), road.volume)
        self.missions = []
        for i, (vehicle, origin, destination, severity) in enumerate(spec['missions'], 1):
            self.missions.append({
                "id": f"M-{i:02d}",
                "vehicle": vehicle,
                "origin": origin,
                "destination": destination,
                "severity": severity,
                "color": VEHICLE_COLORS[vehicle],
                "route": [],
                "eta": None,
                "status": "pending"
            })
        self.fleet = {"origin": spec['fleet'][0], "destination": spec['fleet'][1], "route": []}
        self.coordinate()
        return self.state()

    def reset(self):
        return self.load_scenario(self.scenario_id)

    def close_road(self, a: str, b: str, closed: bool = True):
        r = self._road(a, b)
        if r:
            r.closed = closed

    def _road(self, a, b):
        return next((r for r in self.roads if {r.a, r.b} == {a, b}), None)

    def estimate_time(self, path: list[str], emergency: bool = False) -> float | None:
        if not path or len(path) < 2:
            return None
        penalty = 0.45 if emergency else 0.72
        cost = 0.0
        for a, b in zip(path, path[1:]):
            r = self._road(a, b)
            if not r:
                return None
            cost += r.minutes * (1 + penalty * r.congestion)
        return round(cost, 1)

    def route(self, start: str, goal: str, emergency: bool = False, avoid: set[tuple[str, str]] | None = None, free_flow: bool = False):
        avoid = avoid or set()
        graph = {n: [] for n in NODES}
        penalty = 0.45 if emergency else 0.72
        for r in self.roads:
            key = tuple(sorted((r.a, r.b)))
            if r.closed or key in avoid:
                continue
            weight = r.minutes if free_flow else r.minutes * (1 + penalty * r.congestion)
            if r.a in graph and r.b in graph:
                graph[r.a].append((r.b, weight))
                graph[r.b].append((r.a, weight))
        q = [(0.0, start, [start])]
        best = {start: 0.0}
        while q:
            cost, node, path = heappop(q)
            if node == goal:
                return path, round(cost, 1)
            if cost != best.get(node):
                continue
            for nxt, w in graph.get(node, []):
                nc = cost + w
                if nc < best.get(nxt, float('inf')):
                    best[nxt] = nc
                    heappush(q, (nc, nxt, path + [nxt]))
        return [], None

    def coordinate(self):
        ranked = []
        for m in self.missions:
            _, score = self.route(m['origin'], m['destination'], True)
            ranked.append((m['severity'], score if score is not None else 1e9, m))
        ranked.sort(key=lambda x: (-x[0], x[1], x[2]['id']))
        reservations = set()
        for _, _, m in ranked:
            baseline, _ = self.route(m['origin'], m['destination'], True, free_flow=True)
            baseline_eta = self.estimate_time(baseline, True)
            base_path, base_score = self.route(m['origin'], m['destination'], True)
            alt_path, alt_score = self.route(m['origin'], m['destination'], True, reservations)
            if alt_path and base_path and alt_path != base_path and alt_score <= base_score * 1.35:
                path = alt_path
            else:
                path = base_path
            m['baseline_route'] = baseline
            m['baseline_eta'] = baseline_eta
            m['route'] = path
            m['eta'] = self.estimate_time(path, True)
            m['delta_min'] = round((baseline_eta or 0) - (m['eta'] or 0), 1) if baseline_eta is not None and m['eta'] is not None else None
            m['benefit_pct'] = round(m['delta_min'] / baseline_eta * 100, 1) if baseline_eta and m['delta_min'] is not None else None
            m['status'] = 'routed' if path else 'no path'
            reservations.update(tuple(sorted(pair)) for pair in zip(path, path[1:]))

        self.fleet['baseline_route'], _ = self.route(self.fleet['origin'], self.fleet['destination'], free_flow=True)
        self.fleet['baseline_eta'] = self.estimate_time(self.fleet['baseline_route'])
        self.fleet['route'], _ = self.route(self.fleet['origin'], self.fleet['destination'])
        self.fleet['eta'] = self.estimate_time(self.fleet['route'])
        self.fleet['delta_min'] = round((self.fleet['baseline_eta'] or 0) - (self.fleet['eta'] or 0), 1) if self.fleet['baseline_eta'] is not None and self.fleet['eta'] is not None else None
        return self.state()

    def step(self):
        self.tick += 1
        for i, r in enumerate(self.roads):
            if not r.closed:
                r.volume = max(1, min(r.capacity * 2, r.volume + (-2, 1, 2, 0)[(self.tick + i) % 4]))
        return self.coordinate()

    def state(self) -> dict[str, Any]:
        signal_plan = {}
        for m in self.missions:
            for a, b in zip(m['route'], m['route'][1:]):
                signal_plan[b] = {"state": "EMERGENCY GREEN", "mission": m['id']}
        for n in NODES:
            signal_plan.setdefault(n, {"state": "ADAPTIVE", "mission": None})
        spec = SCENARIOS[self.scenario_id]
        return {
            "tick": self.tick,
            "scenario_id": self.scenario_id,
            "scenario_title": spec['title'],
            "scenario_description": spec['description'],
            "scenario_options": [{"id": k, "title": v['title']} for k, v in SCENARIOS.items()],
            "nodes": NODES,
            "roads": [{"a": r.a, "b": r.b, "minutes": r.minutes, "capacity": r.capacity, "volume": r.volume, "congestion": round(r.congestion, 2), "closed": r.closed} for r in self.roads],
            "missions": self.missions,
            "fleet": self.fleet,
            "signal_plan": signal_plan,
            "is_real_data": IS_REAL_DATA,
            "comparison": "Estimated travel minutes: congestion-aware coordinated route vs shortest open path under baseline weights.",
            "disclosure": "Real-world OpenStreetMap road network & landmarks. All comparative times are model-estimated travel times."
        }


def compare_all_scenarios() -> list[dict[str, Any]]:
    """Run every preset from a fresh state and return comparable estimates."""
    rows = []
    for scenario_id, spec in SCENARIOS.items():
        sim = CitySimulation()
        state = sim.load_scenario(scenario_id)
        rows.append({
            "scenario_id": scenario_id,
            "title": state["scenario_title"],
            "closures": [f"{r['a']}–{r['b']}" for r in state['roads'] if r['closed']],
            "missions": [{k: m[k] for k in ("id", "vehicle", "baseline_route", "baseline_eta", "route", "eta", "delta_min", "benefit_pct")} for m in state['missions']],
        })
    return rows
