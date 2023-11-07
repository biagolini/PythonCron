import shutil
from datetime import datetime, timezone, timedelta
import json
from dateutil import parser
from croniter import croniter
import time
import sys
import threading
import uuid
from threading import Lock
from contextlib import contextmanager

# Set up initial task file from backup
shutil.copyfile("backup/model.json", "tasks.json")

lock = Lock()

@contextmanager
def file_lock():
    """ Context manager to handle file locking. """
    lock.acquire()
    try:
        yield
    finally:
        lock.release()

# Configuration parameters
TIMEOUT = 1  # The time limit in minutes for each job to execute before it times out.
RETENTION_CRON_SUCCESS = 3  # The time in minutes to keep logs of successfully completed jobs.
RETENTION_CRON_FAIL = 5  # The time in minutes to keep logs of failed jobs.
RETENTION_SCHEDULED_SUCCESS = 3  # Time in minutes to retain successful scheduled tasks.
RETENTION_SCHEDULED_FAIL = 5  # Time in minutes to retain failed scheduled tasks.


# This condition ensures that log retention times for both successful and failed jobs
# are not set shorter than the job timeout duration, preventing premature log deletion.
if not all(retention >= TIMEOUT for retention in [RETENTION_CRON_SUCCESS, RETENTION_CRON_FAIL, RETENTION_SCHEDULED_SUCCESS, RETENTION_SCHEDULED_FAIL]):
    sys.exit("Log retention periods must be equal to or longer than the job timeout duration.")

def load_tasks():
    """ Loads tasks from the JSON file safely. """
    with file_lock():
        with open('tasks.json', 'r') as file:
            return json.load(file)

def update_task(tasks):
    """ Safely updates the tasks in the JSON file. """
    with file_lock():
        with open('tasks.json', 'w') as file:
            json.dump(tasks, file, indent=2)

def review_and_start_tasks():
    """ Reviews and starts due tasks based on their schedule. """
    current_time = datetime.now(timezone.utc)
    tasks = load_tasks()
    for task in tasks:
        if "schedule" in task:
            scheduled_time = parser.parse(task["schedule"])
            if current_time >= scheduled_time and "execution" not in task:
                start(task, tasks)
        elif "cron" in task:
            cron_schedule = croniter(task["cron"], current_time)
            current_period_start = cron_schedule.get_prev(datetime)
            next_period_start = cron_schedule.get_next(datetime)
            if "execution" not in task or not any(current_period_start <= parser.parse(execution["start_at"]) < next_period_start for execution in task["execution"]):
                start(task, tasks)

def start(task, tasks):
    """ Starts a job asynchronously. """
    if '_id' not in task:
        task_id = task.get('_id', str(uuid.uuid4()))
        task['_id'] = task_id
    else:
        task_id = task['_id']
    execution_id = str(uuid.uuid4())
    execution_entry = {
        "_id": execution_id,
        "start_at": datetime.now(timezone.utc).isoformat(),
        "status": "started"
    }
    if 'execution' not in task:
        task['execution'] = [execution_entry]
    else:
        task['execution'].append(execution_entry)
    update_task(tasks)  
    update_single_execution_status(task_id, execution_id, "started")    
    threading.Thread(target=execute_job, args=(task['job'], execution_entry, TIMEOUT, task_id, execution_id)).start()
    
def update_single_execution_status(task_id, execution_id, status):
    """ Updates the status of a specific execution within a task. """
    tasks = load_tasks() 
    tasks_updated = False
    for task in tasks:    
        if task.get('_id') == task_id and 'execution' in task:
            for execution in task['execution']:
                if execution.get('_id') == execution_id:
                    execution['status'] = status
                    now =  datetime.now(timezone.utc).isoformat()
                    execution['last_update'] = now
                    if status == 'completed':
                        execution['finished_at'] = now                        
                    tasks_updated = True
                    break
            if tasks_updated:
                break
    if tasks_updated:
        update_task(tasks)

def execute_job(job_details, execution_entry, timeout, task_id, execution_id):
    """ Executes the job based on the details provided in job_details. """
    repeats = job_details.get('repeats', job_details.get('repeat', 1))
    interval = job_details.get('interval', 1)
    max_end_time = datetime.now(timezone.utc) + timedelta(minutes=timeout)
    for _ in range(repeats):
        if datetime.now(timezone.utc) > max_end_time:
            execution_entry['status'] = 'timeout'
            break
        with open('results.txt', 'a') as results_file:
            current_time = datetime.now(timezone.utc).isoformat()
            message = f"{current_time} | Task ID: {task_id} | Execution ID: {execution_id} | Message: {job_details['message']}\n"
            results_file.write(message)
        time.sleep(interval)
    else:
        execution_entry['status'] = 'completed'
    
    with open('results.txt', 'a') as results_file:
        current_time = datetime.now(timezone.utc).isoformat()
        status_message = f"{current_time} | Execution ID: {execution_id} | Job status: {execution_entry['status']}\n"
        results_file.write(status_message)
    update_single_execution_status(task_id, execution_id, execution_entry['status'])

def cleanup_cron_executions():
    """ Cleans up old cron job executions based on the retention period. """
    current_time = datetime.now(timezone.utc)
    tasks = load_tasks()  
    for task in tasks:
        if 'execution' in task and "cron" in task:
            executions = task['execution']
            cleaned_executions = []
            for execution in executions:
                time_since_start = current_time - parser.parse(execution['start_at'])
                if execution['status'] == 'completed' and time_since_start < timedelta(minutes=RETENTION_CRON_SUCCESS):
                    cleaned_executions.append(execution)
                elif execution['status'] != 'completed' and time_since_start < timedelta(minutes=RETENTION_CRON_FAIL):
                    cleaned_executions.append(execution)
            task['execution'] = cleaned_executions
    update_task(tasks) 


def cleanup_scheduled_tasks():
    """
    Cleans up scheduled tasks by removing those whose start time is older than the
    retention period defined by RETENTION_SCHEDULED_SUCCESS or RETENTION_SCHEDULED_FAIL.
    """
    current_time = datetime.now(timezone.utc)
    tasks = load_tasks()
    filtered_tasks = []

    for task in tasks:
        if 'schedule' in task and 'execution' in task:
            scheduled_time = parser.parse(task["schedule"])
            time_since_scheduled = current_time - scheduled_time
            last_execution_status = task['execution'][-1]['status'] if task['execution'] else None
            if last_execution_status == 'completed':
                if time_since_scheduled >= timedelta(minutes=RETENTION_SCHEDULED_SUCCESS):
                    continue
            else:
                if time_since_scheduled >= timedelta(minutes=RETENTION_SCHEDULED_FAIL):
                    continue
        filtered_tasks.append(task)
    update_task(filtered_tasks)

def main():
    interval = 60
    start_time = datetime.now(timezone.utc)
    n = 0
    while True:
        n += 1
        current_time = datetime.now(timezone.utc)
        total_running_time = current_time - start_time
        print(f"Starting new execution cycle (n = {n}) at {current_time.isoformat()}")
        next_run = current_time + timedelta(seconds=interval)
        cleanup_cron_executions()  # Call the function to clean old cron executions 
        cleanup_scheduled_tasks()  # Call the function to clean old scheduled executions 
        review_and_start_tasks() # Call the function to review and start tasks

        # Calculate remaining time for the next cycle
        while datetime.now(timezone.utc) < next_run:
            remaining_time = int((next_run - datetime.now(timezone.utc)).total_seconds())
            total_running_time = datetime.now(timezone.utc) - start_time
            sys.stdout.write(f"\rWaiting to start the next cycle in {remaining_time} seconds. Total running time: {total_running_time.total_seconds()} (s)")
            sys.stdout.flush()
            time.sleep(1)
        print()

if __name__ == '__main__':
    main()