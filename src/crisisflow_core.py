"""CrisisFlow multi-scenario evaluation simulator.
Synthetic network and deterministic, inspectable route-planning rules only.
"""
from __future__ import annotations
from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Any

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

NODES = {
    "A":{"x":70,"y":210,"label":"Hospital"}, "B":{"x":230,"y":210,"label":"Junction B"},
    "C":{"x":390,"y":210,"label":"Junction C"}, "D":{"x":70,"y":370,"label":"Depot"},
    "E":{"x":230,"y":370,"label":"Junction E"}, "F":{"x":390,"y":370,"label":"Incident 1"},
    "G":{"x":230,"y":520,"label":"Junction G"}, "H":{"x":550,"y":370,"label":"Incident 2"},
}
ROAD_SEED = [
    ("A","B",3,14,8),("B","C",3,12,11),("C","F",3,12,9),
    ("A","D",4,15,6),("D","E",4,16,9),("E","F",4,12,7),
    ("B","E",2,10,7),("D","G",2,10,5),("G","E",2,11,6),
    ("E","H",3,13,8),("F","H",2,12,7),("C","H",4,12,10),
]
SCENARIOS = {
 "blocked_arterial": {"title":"Blocked arterial", "description":"A crash closes B–C while an ambulance heads to Incident 1.", "closures":[("B","C")], "volumes":{"A-B":12,"B-E":24,"E-F":30}, "missions":[("Ambulance","A","F",5)], "fleet":("G","C")},
 "flooded_roads": {"title":"Flooded connectors", "description":"Floodwater closes B–C and E–H; fire and medical teams respond at once.", "closures":[("B","C"),("E","H")], "volumes":{"D-E":30,"D-G":8,"G-E":9,"E-F":24}, "missions":[("Fire engine","D","H",5),("Ambulance","A","F",4)], "fleet":("G","C")},
 "rush_hour": {"title":"Rush hour congestion", "description":"No road is closed, but the central arterial and hospital approach are heavily loaded.", "closures":[], "volumes":{"A-B":14,"B-C":22,"C-F":15,"B-E":18,"E-F":30,"E-H":12,"D-E":8}, "missions":[("Ambulance","A","F",5),("Police","B","H",3)], "fleet":("G","C")},
 "multiple_incidents": {"title":"Multiple emergencies", "description":"Ambulance, fire and police missions compete for a shared road network.", "closures":[("B","C")], "volumes":{"B-E":13,"E-F":12,"E-H":12}, "missions":[("Ambulance","A","F",5),("Fire engine","D","H",4),("Police","B","H",3)], "fleet":("G","C")},
 "roadworks": {"title":"Roadworks diversion", "description":"Construction closes D–E; a fire engine and ambulance need separate routes.", "closures":[("D","E")], "volumes":{"A-B":11,"B-E":12,"C-H":9,"F-H":8}, "missions":[("Fire engine","D","H",5),("Ambulance","A","F",4)], "fleet":("G","C")},
}
VEHICLE_COLORS={"Ambulance":"#ec625e","Fire engine":"#d3a43f","Police":"#3671b7"}

def road_key(a:str,b:str)->str:return "-".join(sorted((a,b)))

class CitySimulation:
    def __init__(self): self.load_scenario("blocked_arterial")
    def load_scenario(self,scenario_id:str):
        if scenario_id not in SCENARIOS:scenario_id="blocked_arterial"
        self.scenario_id=scenario_id; spec=SCENARIOS[scenario_id]; self.tick=0
        self.roads=[Road(*row) for row in ROAD_SEED]
        for road in self.roads:
            road.closed=tuple(sorted((road.a,road.b))) in {tuple(sorted(e)) for e in spec['closures']}
            road.volume=spec['volumes'].get(road_key(road.a,road.b),road.volume)
        self.missions=[]
        for i,(vehicle,origin,destination,severity) in enumerate(spec['missions'],1):
            self.missions.append({"id":f"M-{i:02d}","vehicle":vehicle,"origin":origin,"destination":destination,"severity":severity,"color":VEHICLE_COLORS[vehicle],"route":[],"eta":None,"status":"pending"})
        self.fleet={"origin":spec['fleet'][0],"destination":spec['fleet'][1],"route":[]}
        self.coordinate();return self.state()
    def reset(self):return self.load_scenario(self.scenario_id)
    def close_road(self,a:str,b:str,closed:bool=True):
        r=self._road(a,b)
        if r:r.closed=closed
    def _road(self,a,b):return next((r for r in self.roads if {r.a,r.b}=={a,b}),None)
    def estimate_time(self,path:list[str],emergency:bool=False)->float|None:
        if not path:return None
        penalty=.45 if emergency else .72
        return round(sum((self._road(a,b).minutes*(1+penalty*self._road(a,b).congestion)) for a,b in zip(path,path[1:])),1)
    def route(self,start:str,goal:str,emergency:bool=False,avoid:set[tuple[str,str]]|None=None,free_flow:bool=False):
        avoid=avoid or set();graph={n:[] for n in NODES}
        penalty=.45 if emergency else .72
        for r in self.roads:
            key=tuple(sorted((r.a,r.b)))
            if r.closed or key in avoid:continue
            weight=r.minutes if free_flow else r.minutes*(1+penalty*r.congestion)
            graph[r.a].append((r.b,weight));graph[r.b].append((r.a,weight))
        q=[(0.0,start,[start])];best={start:0.0}
        while q:
            cost,node,path=heappop(q)
            if node==goal:return path,round(cost,1)
            if cost!=best.get(node):continue
            for nxt,w in graph[node]:
                nc=cost+w
                if nc<best.get(nxt,float('inf')):
                    best[nxt]=nc;heappush(q,(nc,nxt,path+[nxt]))
        return [],None
    def coordinate(self):
        ranked=[]
        for m in self.missions:
            _,score=self.route(m['origin'],m['destination'],True)
            ranked.append((m['severity'],score if score is not None else 1e9,m))
        ranked.sort(key=lambda x:(-x[0],x[1],x[2]['id']))
        reservations=set()
        for _,_,m in ranked:
            baseline,_=self.route(m['origin'],m['destination'],True,free_flow=True)
            baseline_eta=self.estimate_time(baseline,True)
            base_path,base_score=self.route(m['origin'],m['destination'],True)
            alt_path,alt_score=self.route(m['origin'],m['destination'],True,reservations)
            if alt_path and base_path and alt_path!=base_path and alt_score<=base_score*1.35:path=alt_path
            else:path=base_path
            m['baseline_route']=baseline;m['baseline_eta']=baseline_eta;m['route']=path
            m['eta']=self.estimate_time(path,True);m['delta_min']=round((baseline_eta or 0)-(m['eta'] or 0),1) if baseline_eta is not None and m['eta'] is not None else None
            m['benefit_pct']=round(m['delta_min']/baseline_eta*100,1) if baseline_eta and m['delta_min'] is not None else None
            m['status']='routed' if path else 'no path'
            reservations.update(tuple(sorted(pair)) for pair in zip(path,path[1:]))
        self.fleet['baseline_route'],_=self.route(self.fleet['origin'],self.fleet['destination'],free_flow=True)
        self.fleet['baseline_eta']=self.estimate_time(self.fleet['baseline_route'])
        self.fleet['route'],_=self.route(self.fleet['origin'],self.fleet['destination'])
        self.fleet['eta']=self.estimate_time(self.fleet['route'])
        self.fleet['delta_min']=round((self.fleet['baseline_eta'] or 0)-(self.fleet['eta'] or 0),1) if self.fleet['baseline_eta'] is not None and self.fleet['eta'] is not None else None
        return self.state()
    def step(self):
        self.tick+=1
        for i,r in enumerate(self.roads):
            if not r.closed:r.volume=max(1,min(r.capacity*2,r.volume+(-2,1,2,0)[(self.tick+i)%4]))
        return self.coordinate()
    def state(self)->dict[str,Any]:
        signal_plan={}
        for m in self.missions:
            for a,b in zip(m['route'],m['route'][1:]):signal_plan[b]={"state":"EMERGENCY GREEN","mission":m['id']}
        for n in NODES:signal_plan.setdefault(n,{"state":"ADAPTIVE","mission":None})
        spec=SCENARIOS[self.scenario_id]
        return {"tick":self.tick,"scenario_id":self.scenario_id,"scenario_title":spec['title'],"scenario_description":spec['description'],
          "scenario_options":[{"id":k,"title":v['title']} for k,v in SCENARIOS.items()],"nodes":NODES,
          "roads":[{"a":r.a,"b":r.b,"minutes":r.minutes,"capacity":r.capacity,"volume":r.volume,"congestion":round(r.congestion,2),"closed":r.closed} for r in self.roads],
          "missions":self.missions,"fleet":self.fleet,"signal_plan":signal_plan,
          "comparison":"Estimated minutes from synthetic road weights: congestion-aware coordinated route vs shortest open route under free-flow weights.",
          "disclosure":"All times and route comparisons are synthetic model estimates, not measured travel times or real-world benefits."}


def compare_all_scenarios()->list[dict[str,Any]]:
    """Run every preset from a fresh state and return comparable estimates."""
    rows=[]
    for scenario_id,spec in SCENARIOS.items():
        sim=CitySimulation();state=sim.load_scenario(scenario_id)
        rows.append({
            "scenario_id":scenario_id,"title":state["scenario_title"],
            "closures":[f"{r['a']}–{r['b']}" for r in state['roads'] if r['closed']],
            "missions":[{k:m[k] for k in ("id","vehicle","baseline_route","baseline_eta","route","eta","delta_min","benefit_pct")} for m in state['missions']],
        })
    return rows
