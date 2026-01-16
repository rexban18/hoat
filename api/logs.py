import os
import sqlite3
import json
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            import urllib.parse
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            
            script_id = params.get('script_id', [None])[0]
            
            if not script_id:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Script ID is required'
                }).encode())
                return
            
            db_path = '/tmp/database/scripts.db'
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get log path
            cursor.execute('SELECT log_path FROM scripts WHERE id = ?', (script_id,))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Script not found'
                }).encode())
                return
            
            log_path = result[0]
            
            # Read logs
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    logs = f.read()
            else:
                logs = "No logs available yet..."
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'logs': logs,
                'script_id': script_id
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode())