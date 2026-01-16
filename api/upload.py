import os
import sqlite3
import json
import uuid
from http import HTTPStatus

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
            start_time INTEGER,
            end_time INTEGER,
            log_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    return conn

def handler(request):
    if request.method != 'POST':
        return {
            'statusCode': 405,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': False, 'error': 'Method not allowed'})
        }
    
    try:
        # In Vercel, request body comes as base64 encoded string
        import base64
        
        # Check content type
        content_type = request.headers.get('content-type', '')
        
        # For Vercel, we need to parse multipart form data manually
        # This is simplified - for production you'd use a proper parser
        body = request.body
        
        if not body:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'No file uploaded'})
            }
        
        # In a real implementation, you'd parse multipart form data properly
        # For this example, we'll use a simpler approach with JSON
        
        # For demo purposes, we'll accept JSON with file content as base64
        try:
            data = json.loads(body)
            file_content = base64.b64decode(data.get('file_content', ''))
            file_name = data.get('file_name', 'script.py')
            hours = int(data.get('hours', 1))
        except:
            # Try to parse as regular JSON without base64
            data = json.loads(body)
            file_content = data.get('file_content', '').encode()
            file_name = data.get('file_name', 'script.py')
            hours = int(data.get('hours', 1))
        
        if not file_content:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'No file content'})
            }
        
        if not file_name.endswith('.py'):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Only .py files allowed'})
            }
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        filename = f"{unique_id}_{file_name}"
        script_path = f"/tmp/scripts/{filename}"
        log_path = f"/tmp/logs/{unique_id}.log"
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(script_path), exist_ok=True)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        # Save the file
        with open(script_path, 'wb') as f:
            f.write(file_content)
        
        # Save the script
        conn = init_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO scripts 
            (script_name, script_path, run_time, status, log_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (file_name, script_path, hours, 'uploaded', log_path))
        
        script_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': True,
                'script_id': script_id,
                'filename': file_name,
                'message': 'File uploaded successfully'
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }
