import os
import subprocess
from dotenv import load_dotenv

def get_cron_command():
    venv_python = os.path.join(os.getcwd(), "venv/bin/python")
    script_path = os.path.join(os.getcwd(), "run_strategy.py")
    return f"{venv_python} {script_path} >> {os.getcwd()}/dca_bot.log 2>&1"

def add_cron_job():
    load_dotenv()
    cron_time = os.getenv("CRON_TIME", "19:10")
    hour, minute = cron_time.split(":")
    
    command = get_cron_command()
    cron_entry = f"{minute} {hour} * * * {command}"
    
    # Get current crontab
    try:
        current_cron = subprocess.check_output("crontab -l", shell=True, stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError:
        current_cron = ""
    
    # Remove existing entry if any
    lines = [line for line in current_cron.splitlines() if "run_strategy.py" not in line]
    lines.append(cron_entry)
    
    # Save back
    new_cron = "\n".join(lines) + "\n"
    process = subprocess.Popen("crontab -", shell=True, stdin=subprocess.PIPE)
    process.communicate(input=new_cron.encode())

def remove_cron_job():
    try:
        current_cron = subprocess.check_output("crontab -l", shell=True, stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError:
        return
    
    lines = [line for line in current_cron.splitlines() if "run_strategy.py" not in line]
    
    new_cron = "\n".join(lines) + "\n"
    if not new_cron.strip():
        subprocess.run("crontab -r", shell=True)
    else:
        process = subprocess.Popen("crontab -", shell=True, stdin=subprocess.PIPE)
        process.communicate(input=new_cron.encode())

def is_cron_active():
    try:
        current_cron = subprocess.check_output("crontab -l", shell=True, stderr=subprocess.STDOUT).decode()
        return any("run_strategy.py" in line for line in current_cron.splitlines())
    except subprocess.CalledProcessError:
        return False
