import os
import sqlite3
import json

def handler(request):
    if request.method != 'GET':
        return {
            'statusCode': 405,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': False, 'error': 'Method not allowed'})
        }
    
    try:
        # Parse query parameters
        script_id = request.query.get('script_id')
        
        if not script_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Script ID is required'})
            }
        
        db_path = '/tmp/database/scripts.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get log path
        cursor.execute('SELECT log_path FROM scripts WHERE id = ?', (script_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Script not found'})
            }
        
        log_path = result[0]
        
        # Read logs
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    logs = f.read()
            except:
                logs = "Error reading log file"
        else:
            logs = "No logs available yet..."
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache, no-store, must-revalidate'
            },
            'body': json.dumps({
                'success': True,
                'logs': logs,
                'script_id': script_id
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
