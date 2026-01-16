import os
import sqlite3
import subprocess
import threading
import time
import json
import signal
from http.server import BaseHTTPRequestHandler

def run_script_with_timeout(script_path, log_path, hours, script_id):
    """Run script and stop it after specified hours"""
    try:
        # Open log file
        with open(log_path, 'a') as log_file:
            # Start the script
            process = subprocess.Popen(
                ['python3', script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Update database with PID
            db_path = '/tmp/database/scripts.db'
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scripts 
                SET status = ?, pid = ?, start_time = ?
                WHERE id = ?
            ''', ('running', process.pid, int(time.time()), script_id))
            conn.commit()
            conn.close()
            
            # Log startup
            log_file.write(f"[{time.ctime()}] Script started (PID: {process.pid})\n")
            log_file.write(f"[{time.ctime()}] Will run for {hours} hours\n")
            log_file.flush()
            
            # Set timeout in seconds
            timeout = hours * 3600
            
            # Start timer
            start_time = time.time()
            
            # Read output in real-time
            def read_output(stream, prefix):
                for line in iter(stream.readline, ''):
                    timestamp = time.ctime()
                    log_file.write(f"[{timestamp}] {prefix}{line}")
                    log_file.flush()
            
            # Start output readers
            import threading
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, ''))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, '[ERROR] '))
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for completion or timeout
            while True:
                if process.poll() is not None:
                    # Process completed
                    log_file.write(f"[{time.ctime()}] Script completed\n")
                    break
                
                if time.time() - start_time > timeout:
                    # Timeout reached
                    log_file.write(f"[{time.ctime()}] Timeout reached, stopping script\n")
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    break
                
                time.sleep(1)
            
            # Wait for output threads
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
            
            # Update database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scripts 
                SET status = ?, end_time = ?
                WHERE id = ?
            ''', ('completed', int(time.time()), script_id))
            conn.commit()
            conn.close()
            
    except Exception as e:
        # Log error
        with open(log_path, 'a') as log_file:
            log_file.write(f"[{time.ctime()}] ERROR: {str(e)}\n")
        
        # Update database
        db_path = '/tmp/database/scripts.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE scripts 
            SET status = ?, end_time = ?
            WHERE id = ?
        ''', ('error', int(time.time()), script_id))
        conn.commit()
        conn.close()

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
            
            # Check if another script is running
            db_path = '/tmp/database/scripts.db'
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM scripts WHERE status = ?', ('running',))
            running_count = cursor.fetchone()[0]
            
            if running_count > 0:
                conn.close()
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Another script is already running'
                }).encode())
                return
            
            # Get script info
            cursor.execute('''
                SELECT script_path, run_time, log_path 
                FROM scripts 
                WHERE id = ?
            ''', (script_id,))
            
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
            
            script_path, run_time, log_path = result
            
            # Start script in background thread
            thread = threading.Thread(
                target=run_script_with_timeout,
                args=(script_path, log_path, run_time, script_id),
                daemon=True
            )
            thread.start()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'message': 'Script started',
                'script_id': script_id,
                'run_time': run_time
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode())