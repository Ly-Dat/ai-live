import subprocess
import json
import os, time, logging
import signal

config_json = '''
{
  "coordination_program": [
    {
      "name": "captions_printer",
      "path": "E://GitHub_pro//captions_printer//pkg//captions_printer-v4.1//Miniconda3//python.exe",
      "parameters": ["E://GitHub_pro//captions_printer//pkg//captions_printer-v4.1//app.py"]
    },
    {
      "name": "audio_player",
      "path": "E://GitHub_pro//audio_player//pkg//audio_player_v2-20240320//Miniconda3//python.exe",
      "parameters": ["E://GitHub_pro//audio_player//pkg//audio_player_v2-20240320//app.py"]
    }
  ]
}
'''

# Parse the JSON config
config = json.loads(config_json)

# Store the started processes
processes = {}

def start_programs(config):
    """Start all programs according to the config.

    Args:
        config (dict): Dict containing the program config.
    """
    for program in config.get("programs", []):
        name = program["name"]
        python_path = program["path"]  # Python Path of the interpreter
        app_path = program["parameters"][0]  # Assume the first argument is always the app.py path
        
        # Extract the directory from the app.py path
        app_dir = os.path.dirname(app_path)
        
        # Build the command from the Python interpreter path and the app.py path
        cmd = [python_path, app_path]

        logging.info(f"Running program: {name} located at: {app_dir}")
        
        # Start the program in the directory containing app.py
        process = subprocess.Popen(cmd, cwd=app_dir, shell=True)
        processes[name] = process

def stop_program(name):
    """Stop a running program and all its child processes; works on Windows, Linux and macOS.

    Args:
        name (str): Name of the program to stop.
    """
    if name in processes:
        pid = processes[name].pid  # Get the processID
        logging.info(f"Stop the program and all its child processes: {name} with PID {pid}")

        try:
            if os.name == 'nt':  # Windows
                command = ["taskkill", "/F", "/T", "/PID", str(pid)]
                subprocess.run(command, check=True)
            else:  # POSIXsystems such as Linux andmacOS
                os.killpg(os.getpgid(pid), signal.SIGKILL)

            logging.info(f"Program {name} and all its child processes were terminated.")
        except Exception as e:
            logging.error(f"Failed to terminate program {name}: {e}")

        del processes[name]  # Remove from the process dict
    else:
        logging.warning(f"Program {name} is not running.")

# Start all programs in the config
start_programs(config)

# ...Do other tasks...
time.sleep(10)

# When you want to stop a program
stop_program("captions_logging.infoer")
stop_program("audio_player")
