import os
import sqlite3
import json
import signal
import time

# Import running_processes from start.py
import sys
sys.path.append('/var/task')
from start import running_processes

def handler(request):
    if request.method != 'POST':
        return {
            'statusCode': 405,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': False, 'error': 'Method not allowed'})
        }
    
    try:
        data = json.loads(request.body)
        script_id = data.get('script_id')
        
        if not script_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Script ID is required'})
            }
        
        db_path = '/tmp/database/scripts.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get script info
        cursor.execute('SELECT pid, log_path, script_path FROM scripts WHERE id = ? AND status = ?', 
                      (script_id, 'running'))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'No running script found with this ID'})
            }
        
        pid, log_path, script_path = result
        
        # Stop the process
        try:
            # Try to stop via running_processes dict
            if script_id in running_processes:
                process = running_processes[script_id]
                process.terminate()
                try:
                    process.wait(timeout=2)
                except:
                    process.kill()
                del running_processes[script_id]
            elif pid:
                # Try to kill by PID
                os.kill(pid, signal.SIGTERM)
                
            # Log the stop
            if os.path.exists(log_path):
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
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': True,
                'message': 'Script stopped successfully'
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
