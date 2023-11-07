# Python Message Scheduler

The Python Message Scheduler is an automated tool designed to schedule and execute messages/tasks at specific times or intervals. It's built with Python and utilizes cron-like scheduling features to provide precise timing operations.

## Features

- Cron-like scheduling for message/task execution.
- Execution of tasks based on one-time schedules or recurring intervals.
- Automatic retention policy for execution logs.
- Threaded task execution to handle concurrent jobs.
- Safe file handling with locking mechanisms to prevent data races.

## Installation

Ensure you have Python 3.x installed on your machine. Clone this repository using:

```bash
git clone https://github.com/biagolini/PythonCron.git
```

Navigate to the project directory and install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Edit the `backup/model.json` with your desired tasks and their schedules. To run the scheduler, execute:

```bash
python3 scheduler.py
```

The scheduler will manage the tasks as per the configurations set in the model.json file.

## Configuration

Configure your tasks in the backup/model.json file. The task structure includes a unique identifier, schedule, and job details like message content, repeat intervals, and execution status.

Here's an example of a task configuration:

```json
[
  {
    "schedule": "2023-11-01T00:00:00Z",
    "job": {
      "message": "ONCE This job will be executed once and then removed",
      "repeats": 10,
      "interval": 1
    }
  },
  {
    "cron": "* * * * *",
    "job": {
      "message": "CRON This job will be executed several times",
      "repeats": 3,
      "interval": 2
    }
  }
]
```

## Contributing

Feel free to submit issues, create pull requests, or fork the repository to help improve the project.

## License and Disclaimer

This project is open-source and available under the MIT License. You are free to copy, modify, and use the project as you wish. However, any responsibility for the use of the code is solely yours. Please use it at your own risk and discretion.
