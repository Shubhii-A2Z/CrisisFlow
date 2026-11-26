"""Utility to load a road graph either from:
1) Built-in synthetic toy graph (nodes A-H)
2) Real-world OpenStreetMap dataset (e.g. Manhattan Midtown with real streets & coordinates)
3) Live OpenStreetMap download via osmnx if available

Both structures use the same schema as the original hard-coded constants, so the
simulation core does not need any changes beyond receiving these values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple


def _scale_coords(
    nodes: Dict[str, dict],
    width: int = 750,
    height: int = 580,
    margin: int = 60,
) -> Dict[str, dict]:
    """Scale raw coordinates to fit SVG viewBox nicely."""
    if not nodes:
        return nodes
    xs = [float(n["x"]) for n in nodes.values()]
    ys = [float(n["y"]) for n in nodes.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    range_x = max_x - min_x or 1.0
    range_y = max_y - min_y or 1.0
    for n in nodes.values():
        n["x"] = int(margin + (float(n["x"]) - min_x) / range_x * (width - 2 * margin))
        n["y"] = int(margin + (float(n["y"]) - min_y) / range_y * (height - 2 * margin))
    return nodes


class GraphLoader:
    """Load either the synthetic demo graph or real OpenStreetMap data."""

    def __init__(
        self,
        real_data: bool = False,
        area: str = "",
        dataset_path: str | Path | None = None,
    ) -> None:
        self.real_data = real_data
        self.area = area or "Manhattan, New York, USA"
        self.dataset_path = dataset_path or (
            Path(__file__).parent / "data" / "manhattan_osm.json"
        )

    def load(self) -> Tuple[Dict[str, dict], List[Tuple[str, str, float, int, int]]]:
        """Return (nodes, roads)."""
        if not self.real_data:
            return self._synthetic()

        # Strategy 1: Load bundled real-world OpenStreetMap dataset (guaranteed offline/online)
        bundled_data = self._load_bundled_real_dataset()
        if bundled_data:
            nodes, roads = bundled_data
            print(
                f"[INFO] Successfully loaded real-world OSM dataset ({self.area}): "
                f"{len(nodes)} real intersections, {len(roads)} road corridors."
            )
            return nodes, roads

        # Strategy 2: If custom area specified and osmnx installed, attempt live download
        live_data = self._try_live_osm_download()
        if live_data:
            return live_data

        print("[WARN] Falling back to synthetic graph.")
        self.real_data = False
        return self._synthetic()

    def _load_bundled_real_dataset(
        self,
    ) -> Tuple[Dict[str, dict], List[Tuple[str, str, float, int, int]]] | None:
        """Loads a real OpenStreetMap road dataset (Midtown Manhattan landmarks)."""
        try:
            path = Path(self.dataset_path)
            if not path.is_file():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            nodes = data.get("nodes", {})
            raw_roads = data.get("roads", [])
            roads = [
                (str(r[0]), str(r[1]), float(r[2]), int(r[3]), int(r[4]))
                for r in raw_roads
            ]
            return _scale_coords(nodes), roads
        except Exception as e:
            print(f"[WARN] Error reading bundled real dataset: {e}")
            return None

    def _try_live_osm_download(
        self,
    ) -> Tuple[Dict[str, dict], List[Tuple[str, str, float, int, int]]] | None:
        """Attempt to download network via osmnx if connection is active."""
        try:
            import osmnx as ox  # type: ignore

            print(f"[INFO] Querying OpenStreetMap API for area: {self.area}...")
            G = ox.graph_from_place(self.area, network_type="drive")
            nodes: Dict[str, dict] = {}
            for node_id, data in G.nodes(data=True):
                nodes[str(node_id)] = {
                    "x": data.get("x", 0),
                    "y": -data.get("y", 0),
                    "label": str(data.get("name", "")),
                }
            nodes = _scale_coords(nodes)

            roads: List[Tuple[str, str, float, int, int]] = []
            seen = set()
            for u, v, data in G.edges(data=True):
                k = tuple(sorted((str(u), str(v))))
                if k in seen:
                    continue
                seen.add(k)
                length_m = data.get("length", 150)
                maxspeed = data.get("maxspeed", 30)
                if isinstance(maxspeed, (list, tuple)):
                    maxspeed = maxspeed[0]
                try:
                    speed = float(str(maxspeed).replace(" mph", "").replace(" km/h", ""))
                except Exception:
                    speed = 30.0
                minutes = round(length_m / (speed * 1000 / 60), 2)
                capacity = max(10, int(data.get("lanes", 1)) * 20)
                volume = int(capacity * 0.45)
                roads.append((str(u), str(v), minutes, capacity, volume))
            return nodes, roads
        except Exception:
            return None

    @staticmethod
    def _synthetic() -> Tuple[Dict[str, dict], List[Tuple[str, str, float, int, int]]]:
        """Return the original hard-coded demo graph."""
        nodes = {
            "A": {"x": 70, "y": 210, "label": "Hospital"},
            "B": {"x": 230, "y": 210, "label": "Junction B"},
            "C": {"x": 390, "y": 210, "label": "Junction C"},
            "D": {"x": 70, "y": 370, "label": "Depot"},
            "E": {"x": 230, "y": 370, "label": "Junction E"},
            "F": {"x": 390, "y": 370, "label": "Incident 1"},
            "G": {"x": 230, "y": 520, "label": "Junction G"},
            "H": {"x": 550, "y": 370, "label": "Incident 2"},
        }
        roads = [
            ("A", "B", 3, 14, 8),
            ("B", "C", 3, 12, 11),
            ("C", "F", 3, 12, 9),
            ("A", "D", 4, 15, 6),
            ("D", "E", 4, 16, 9),
            ("E", "F", 4, 12, 7),
            ("B", "E", 2, 10, 7),
            ("D", "G", 2, 10, 5),
            ("G", "E", 2, 11, 6),
            ("E", "H", 3, 13, 8),
            ("F", "H", 2, 12, 7),
            ("C", "H", 4, 12, 10),
        ]
        return nodes, roads
