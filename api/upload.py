import os
import sqlite3
import uuid
import time
import json
from http.server import BaseHTTPRequestHandler

# Database setup
def init_db():
    os.makedirs('/tmp/database', exist_ok=True)
    os.makedirs('/tmp/scripts', exist_ok=True)
    os.makedirs('/tmp/logs', exist_ok=True)
    
    db_path = '/tmp/database/scripts.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create scripts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_name TEXT,
            script_path TEXT,
            run_time INTEGER,
            status TEXT,
            pid INTEGER,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            log_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    return conn

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_type = self.headers.get('Content-Type', '')
            
            if 'multipart/form-data' not in content_type:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Content-Type must be multipart/form-data'
                }).encode())
                return
            
            # Parse multipart form data
            import cgi
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST',
                        'CONTENT_TYPE': self.headers['Content-Type']}
            )
            
            # Get file and hours
            file_item = form['file']
            hours = int(form['hours'].value)
            
            if not file_item.filename.endswith('.py'):
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Only .py files are allowed'
                }).encode())
                return
            
            # Generate unique filename
            unique_id = str(uuid.uuid4())
            filename = f"{unique_id}_{file_item.filename}"
            script_path = f"/tmp/scripts/{filename}"
            log_path = f"/tmp/logs/{unique_id}.log"
            
            # Save the file
            with open(script_path, 'wb') as f:
                f.write(file_item.file.read())
            
            # Initialize database and save script info
            conn = init_db()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO scripts 
                (script_name, script_path, run_time, status, log_path)
                VALUES (?, ?, ?, ?, ?)
            ''', (file_item.filename, script_path, hours, 'uploaded', log_path))
            
            script_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'script_id': script_id,
                'filename': file_item.filename,
                'message': 'File uploaded successfully'
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode())