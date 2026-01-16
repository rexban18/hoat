import os
import sqlite3
import json
import signal
import time
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            script_id = data.get('script_id')
            
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
            
            # Get script info
            cursor.execute('SELECT pid, log_path FROM scripts WHERE id = ?', (script_id,))
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Script not found'
                }).encode())
                return
            
            pid, log_path = result
            
            # Stop the process
            try:
                if pid:
                    os.kill(pid, signal.SIGTERM)
                    
                    # Log the stop
                    with open(log_path, 'a') as log_file:
                        log_file.write(f"[{time.ctime()}] Script stopped by user\n")
            except ProcessLookupError:
                pass  # Process already stopped
            except Exception as e:
                pass  # Ignore other errors
            
            # Update database
            cursor.execute('''
                UPDATE scripts 
                SET status = ?, end_time = ?
                WHERE id = ?
            ''', ('stopped', int(time.time()), script_id))
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'message': 'Script stopped successfully'
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode())