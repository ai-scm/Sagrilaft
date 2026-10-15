#!/usr/bin/env python3
"""P20 B inert HTTP candidate: always 503; no application, DB or external client."""
import json
import os
import re


def validate(env):
    lab = env.get('P20_RUN_ID', '')
    if not (re.fullmatch(r'p20-[a-f0-9]{12}', lab)
            and env.get('P20_B_FORCE_UNHEALTHY') == 'true'
            and env.get('RUN_MODE') == 'p20-b-unhealthy'
            and env.get('ZOHO_SIGN_ENABLED') == 'false'
            and re.fullmatch(re.escape(lab) + r'-c7-test-[0-9]{8}\.[a-z0-9]+\.us-east-1\.rds\.amazonaws\.com', env.get('DATABASE_HOST', ''))):
        raise RuntimeError('P20 B health fixture refused')


def make_server(host='0.0.0.0', port=8000):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"status":"unhealthy","fixture":"p20-b","databaseTouched":false}'
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass  # Never log arbitrary request paths or headers.
    return HTTPServer((host, port), Handler)


def main():
    try:
        validate(os.environ)
    except RuntimeError:
        print('P20 B health fixture refused', flush=True)
        return 64
    print(json.dumps({'event': 'p20_b_health_failure_started', 'databaseTouched': False, 'externalCalls': False}), flush=True)
    with make_server() as server:
        server.serve_forever()


if __name__ == '__main__':
    raise SystemExit(main())
