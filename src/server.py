from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
import json
import sys

# Ensure src/ is on the path when invoked from project root
sys.path.insert(0, str(Path(__file__).parent))

from crisisflow_core import CitySimulation, compare_all_scenarios

ROOT=Path(__file__).parent
SIM=CitySimulation()
class Handler(BaseHTTPRequestHandler):
    def _send(self,code,data,content_type='application/json'):
        body=data if isinstance(data,bytes) else (json.dumps(data).encode() if content_type=='application/json' else data.encode())
        self.send_response(code);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/state': self._send(200,SIM.coordinate());return
        if path=='/api/compare': self._send(200,compare_all_scenarios());return
        if path=='/': self._send(200,(ROOT/'index.html').read_bytes(),'text/html; charset=utf-8');return
        if path=='/app.js': self._send(200,(ROOT/'app.js').read_bytes(),'text/javascript; charset=utf-8');return
        if path=='/style.css': self._send(200,(ROOT/'style.css').read_bytes(),'text/css; charset=utf-8');return
        if path=='/city-response.png': self._send(200,(ROOT/'city_response_illustration.png').read_bytes(),'image/png');return
        self._send(404,{'error':'not found'})
    def do_POST(self):
        path=urlparse(self.path).path
        try: data=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0)) or b'{}'))
        except Exception: data={}
        if path=='/api/scenario':
            try:self._send(200,SIM.load_scenario(data['scenario_id']))
            except KeyError:self._send(400,{'error':'expected scenario_id'})
            return
        if path=='/api/step': self._send(200,SIM.step());return
        if path=='/api/reset': self._send(200,SIM.reset());return
        if path=='/api/closure':
            try: SIM.close_road(data['a'],data['b'],bool(data['closed']));self._send(200,SIM.coordinate())
            except (KeyError,TypeError): self._send(400,{'error':'expected a, b and closed'} )
            return
        if path=='/api/fleet':
            try: SIM.fleet.update(origin=data['origin'],destination=data['destination']);self._send(200,SIM.coordinate())
            except KeyError: self._send(400,{'error':'expected origin and destination'})
            return
        self._send(404,{'error':'not found'})
    def log_message(self,fmt,*args): print('%s - %s'%(self.address_string(),fmt%args))

if __name__=='__main__':
    import os
    host=os.environ.get('HOST','127.0.0.1')
    port=int(os.environ.get('PORT','8000'))
    print('CrisisFlow prototype server starting')
    print('Synthetic heuristic simulator; not trained MARL or real-time emergency advice.')
    ThreadingHTTPServer((host,port),Handler).serve_forever()
