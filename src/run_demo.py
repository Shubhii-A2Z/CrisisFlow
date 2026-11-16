"""Launch the local or hosted CrisisFlow evaluation demo."""
from http.server import ThreadingHTTPServer
import os
import sys
from pathlib import Path

# Ensure src/ is on the path when invoked as `python src/run_demo.py` from project root
sys.path.insert(0, str(Path(__file__).parent))

from server import Handler

if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '8000'))
    display_host = '127.0.0.1' if host in ('0.0.0.0', '::') else host
    print(f'CrisisFlow interactive prototype: http://{display_host}:{port}')
    print('Synthetic rule based simulation. Press Ctrl+C to stop.')
    ThreadingHTTPServer((host, port), Handler).serve_forever()
