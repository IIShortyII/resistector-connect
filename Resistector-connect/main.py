import tkinter as tk
from tkinter import scrolledtext
import subprocess
import os
import time
import atexit
import signal
import requests

# Locations and Temps
base_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.join(base_dir, "scripts")
tmp_dir = os.path.join(scripts_dir, "tmp")
os.makedirs(tmp_dir, exist_ok=True)


exit_handlers = []

# Startup Scripts
script_names = ["app.py"]

 #"measurement-server.py"

# Client IPs
clientIPs = ["10.42.0.1","10.42.0.2","10.42.0.3",]

registeredClients = len(clientIPs)

# Stating Scripts
def start_script(script_name):
    script_path = os.path.join(scripts_dir, script_name)
    pid_file_path = os.path.join(tmp_dir, f"{script_name}_pid.txt")
    
    subprocess.Popen(["x-terminal-emulator", "-e", f"bash -c 'python3 {script_path} & echo $! > {pid_file_path}; exec bash'"])
    time.sleep(1)
    with open(pid_file_path, "r") as file:
        process_pid = int(file.read().strip())
    append_to_console(f"{script_name} mit PID {process_pid} gestartet.")
    return process_pid, pid_file_path

def is_process_running(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

# Resistector Console Messages
def append_to_console(message, color=None):
    console.config(state=tk.NORMAL)
    if color:
        console.tag_config(color, foreground=color)
        console.insert(tk.END, message + "\n", color)
    else:
        console.insert(tk.END, message + "\n")
    console.config(state=tk.DISABLED)
    console.see(tk.END) 

def monitor_process(script_name, process_pid, pid_file_path):
    if is_process_running(process_pid):
        root.after(5000, monitor_process, script_name, process_pid, pid_file_path)  
    else:
        append_to_console(f"{script_name} ist gestoppt.", "red")
        os.remove(pid_file_path)  

def startRegularProcess(script_name):
	def inner():
		process_pid, pid_file_path = start_script(script_name)
		monitor_process(script_name, process_pid, pid_file_path)
		exit_handler(process_pid)
		
	return inner

def welcome_text():
	ascii_art = """ 
    ____            _      __            __                
   / __ \___  _____(______/ /____  _____/ /_____  _____    
  / /_/ / _ \/ ___/ / ___/ __/ _ \/ ___/ __/ __ \/ ___/    
 / _, _/  __(__  / (__  / /_/  __/ /__/ /_/ /_/ / /        
/_/________/____/_/____/\__/\___/\_______/\____/_/         
  / ________  ____  ____  ___  _____/ /_                   
 / /   / __ \/ __ \/ __ \/ _ \/ ___/ __/                   
/ /___/ /_/ / / / / / / /  __/ /__/ /_                     
\____/\____/_/ /_/_/ /_/\___/\___/\__/     
	"""
	append_to_console(ascii_art, "yellow")
	
def startup_Scripts():
	for script_name in script_names:
		process_pid, pid_file_path = start_script(script_name)
		monitor_process(script_name, process_pid, pid_file_path)
		exit_handler(process_pid)
    
def exit_handler(pid):
	exit_handlers.append(pid)

def run_exit():
	for pid in exit_handlers:
		try: 
			os.kill(pid, signal.SIGTERM)
		except:
			print(f"Prozess {pid} konnte nicht beendet werden.")

def checkClients(clientIP):
	status = ping(clientIP)
	if status == 0:
		append_to_console(f"Client {clientIP} is available, but not registered", color="green")
		return 0
	else: 
		append_to_console(f"Client {clientIP} is NOT available. Check if connected to Network", color="red")
		return 1


def ping(ip):
	command = ['ping', '-c', '1', ip]
	try: 
		result = subprocess.run(command, capture_output=True, text=True, timeout=5)
		return result.returncode
	except subprocess.CalledProcessError as e:
		return f"Ping fehlgeschlagen: {e}"
	except subprocess.TimeoutExpired:
		return "Ping Timeout"

def connectClients(clientIP):
	try: 
		responseData = requests.get(f"http://{clientIP}:5000/measure", timeout=5)
		if responseData.status_code == 200:
			append_to_console(f"Client {clientIP} is registered. Ready for Measurement.", color="green")
			return 0
		else:
			append_to_console(f"Client {clientIP} is NOT registered. Check if app.py is running on client.", color="yellow")
			return 1
	except Exception as e:
		append_to_console(f"Client {clientIP} is NOT registered. Check if app.py is running on client.", color="yellow")
		return 1
	

def ClientWatchdog():
	global registeredClients 
	for clientIP in clientIPs:
		responsePing = checkClients(clientIP)
		time.sleep(1)
		if responsePing == 0:
			responseData = connectClients(clientIP)
			if responseData == 0:
				print("")
			else: 
				registeredClients = registeredClients-1
		else: 
			registeredClients = registeredClients-1
	if registeredClients == len(clientIPs):
		button_Plotter.config(state=tk.NORMAL)
	else: 
		button_Plotter.config(state=tk.DISABLED)




#Size and Stuff
root = tk.Tk()
root.title("Resistector Status")
root.geometry("1080x1920")

#Console Definieren
console = scrolledtext.ScrolledText(root, state='disabled', bg='black', fg='white', font=('Courier New', 12), height=15)
console.pack(fill=tk.BOTH, expand=False, padx=10, pady=10)

#Buttons Definieren
button_Plotter = tk.Button(root, text="Starte Plotter", width=30, height=5,state="disabled" , command=startRegularProcess("plot.py"))
button_Plotter.pack(side=tk.LEFT, padx=(150,0))
button_UI = tk.Button(root, text="Starte Resistector UI", width=30, height=5)
button_UI.pack(side=tk.RIGHT, padx=(0,150))

root.after(1000,welcome_text)
root.after(1100,startup_Scripts)
root.after(1300,ClientWatchdog)
root.after_idle(atexit.register(run_exit))
root.mainloop()
