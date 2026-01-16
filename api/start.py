import os
import sqlite3
import subprocess
import threading
import time
import json
import atexit

# Store running processes
running_processes = {}

def run_script_with_timeout(script_path, log_path, hours, script_id):
    """Run script and stop it after specified hours"""
    try:
        # Open log file
        with open(log_path, 'w') as log_file:
            log_file.write(f"[{time.ctime()}] Script starting...\n")
            log_file.flush()
            
            # Start the script
            process = subprocess.Popen(
                ['python', script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Store process
            running_processes[script_id] = process
            
            # Update database
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
            with open(log_path, 'a') as log_file:
                log_file.write(f"[{time.ctime()}] Script started (PID: {process.pid})\n")
                log_file.write(f"[{time.ctime()}] Will run for {hours} hours\n")
                log_file.flush()
            
            # Read output in real-time
            def capture_output():
                try:
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            timestamp = time.ctime()
                            with open(log_path, 'a') as f:
                                f.write(f"[{timestamp}] {line}")
                                f.flush()
                except:
                    pass
            
            # Start output reader thread
            output_thread = threading.Thread(target=capture_output)
            output_thread.daemon = True
            output_thread.start()
            
            # Calculate timeout
            timeout = hours * 3600
            start_time = time.time()
            
            # Wait for completion or timeout
            while True:
                # Check if process is still running
                if process.poll() is not None:
                    status = process.returncode
                    with open(log_path, 'a') as log_file:
                        log_file.write(f"[{time.ctime()}] Script completed with exit code: {status}\n")
                    break
                
                # Check for timeout
                if time.time() - start_time > timeout:
                    with open(log_path, 'a') as log_file:
                        log_file.write(f"[{time.ctime()}] Timeout reached, stopping script\n")
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    break
                
                time.sleep(1)
            
            # Clean up
            if script_id in running_processes:
                del running_processes[script_id]
            
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
        try:
            with open(log_path, 'a') as log_file:
                log_file.write(f"[{time.ctime()}] ERROR: {str(e)}\n")
        except:
            pass
        
        # Update database
        try:
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
        except:
            pass

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
        
        # Check if another script is running
        db_path = '/tmp/database/scripts.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM scripts WHERE status = ?', ('running',))
        running_count = cursor.fetchone()[0]
        
        if running_count > 0:
            conn.close()
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Another script is already running'})
            }
        
        # Get script info
        cursor.execute('''
            SELECT script_path, run_time, log_path 
            FROM scripts 
            WHERE id = ?
        ''', (script_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Script not found'})
            }
        
        script_path, run_time, log_path = result
        
        # Check if script file exists
        if not os.path.exists(script_path):
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Script file not found'})
            }
        
        # Start script in background thread
        thread = threading.Thread(
            target=run_script_with_timeout,
            args=(script_path, log_path, run_time, script_id),
            daemon=True
        )
        thread.start()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': True,
                'message': 'Script started',
                'script_id': script_id,
                'run_time': run_time
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
