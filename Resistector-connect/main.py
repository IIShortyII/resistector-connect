import tkinter as tk
from tkinter import scrolledtext
import tkinter.ttk as ttk
import subprocess
import os
import time
import atexit
import requests
import logging
import sys
import configparser

#logging config
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler(os.path.join(log_dir, "resistector_connect.log")),
])

config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config = configparser.ConfigParser()
config.read(config_path)

def clean_value(value):
    return value.split(';')[0].split('#')[0].strip()




subprocess.run(["xdotool", "search", "--class", "lxterminal", "set_window", "--name", "Resistector-Status", "%@"], check=True)
logging.info("Startup")
time.sleep(1)


class ScriptManager:
    def __init__(self, script_name, scripts_dir, tmp_dir, append_to_console):
        self.script_name = script_name
        self.script_base_name = os.path.splitext(script_name)[0]
        self.script_path = os.path.join(scripts_dir, script_name)
        self.pid_file_path = os.path.join(tmp_dir, f"{script_name}_pid.txt")
        self.process_pid = None
        self.append_to_console = append_to_console

    def start_script(self, minimized=False):
        subprocess.Popen(["lxterminal", "-e", f"bash -c 'python3 {self.script_path} & echo $! > {self.pid_file_path}; exec bash'"])
        if minimized:
            self.minimize_terminal()
        with open(self.pid_file_path, "r") as file:
            self.process_pid = int(file.read().strip())
        self.append_to_console(f"{self.script_base_name} started...")
        logging.info(f"{self.script_name} started")
        return self.process_pid

    def minimize_terminal(self):
        time.sleep(0.5)  # Give the terminal some time to start
        try:
            window_id_string = subprocess.check_output(["xdotool", "search", "--sync", "--onlyvisible", "--class", "lxterminal"]).strip().decode('utf-8')
            window_ids = window_id_string.split('\n')
            for window_id in window_ids:
                try:
                    window_name = subprocess.check_output(["xdotool", "getwindowname", window_id]).decode('utf-8').strip()
                    if "Resistector-connect" in window_name:
                        subprocess.Popen(["xdotool", "windowminimize", window_id])
                except subprocess.CalledProcessError:
                    self.append_to_console(f"Error minimizing window for {self.script_name}", "red")
                    logging.exception(f"While minimizing window {self.script_name} an error occured")
        except subprocess.CalledProcessError:
            self.append_to_console(f"Error minimizing window for {self.script_name}", "red")
            logging.exception(f"While minimizing window {self.script_name} an error occured")

    def is_process_running(self):
        if self.process_pid:
            try:
                os.kill(self.process_pid, 0)
                return True
            except OSError:
                return False
        return False

    def monitor_process(self):
        if self.is_process_running():
            root.after(5000, self.monitor_process)
        else:
            self.append_to_console(f"{self.script_name} stopped.", "red")
            logging.info(f"The script {self.script_name} was terminated unexpectedly")
            if os.path.exists(self.pid_file_path):
                os.remove(self.pid_file_path)
            if self.script_name == "measurementServer.py":
                global measurement_server_running
                measurement_server_running = False

class ClientStatus:
    def __init__(self):
        self.is_available = False
        self.is_registered = False

class ClientManager:
    def __init__(self, ip):
        self.ip = ip
        self.status = ClientStatus()

    def ping(self):
        command = ['ping', '-c', '1', self.ip]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    def connect(self):
        try:
            response = requests.get(f"http://{self.ip}:5000/measure", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

class App:
    def __init__(self, root):
        self.root = root
        self.registeredClients = 0
        self.measurement_server_running = False
        self.bootupCheck = True
        self.init_ui()
        self.clientIPs = list(map(clean_value, config['Network']['client_ips'].split(',')))
        self.clients = {ip: ClientManager(ip) for ip in self.clientIPs}
        self.scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
        self.tmp_dir = os.path.join(self.scripts_dir, "tmp")
        os.makedirs(self.tmp_dir, exist_ok=True)
        self.script_names = ["measurementClient.py"]
        self.welcome_text()
        self.startup_scripts()
        self.schedule_tasks()

    def init_ui(self):
        self.root.title("Resistector Status")
        self.root.geometry("1351x755+180+138")
        self.console = scrolledtext.ScrolledText(self.root, state='disabled', bg='black', fg='white', font=('Courier New', 12), height=15, width=97)
        self.console.place(relx=0.015, rely=0.026, relheight=0.531, relwidth=0.97)
        
        self.button_close = tk.Button(self.root, text="Herunterfahren", width=30, height=5, command=self.on_closing)
        self.button_close.place(relx=0.844, rely=0.583, height=36, width=177)
        
        self.button_Plotter = tk.Button(self.root, text="Starte Plotter", width=30, height=5, state="disabled", command=lambda: self.start_regular_process("plot.py"))
        self.button_Plotter.place(relx=0.192, rely=0.728, height=76, width=287)
        
        self.button_UI = tk.Button(self.root, text="Starte Resistector UI", width=30, height=5, command=lambda: self.start_regular_process("resistectorUI.py"))
        self.button_UI.place(relx=0.585, rely=0.728, height=76, width=287)
        
        separator = ttk.Separator(self.root)
        separator.place(relx=0.0, rely=0.662, relwidth=1.0)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def append_to_console(self, message, color=None):
        self.console.config(state=tk.NORMAL)
        if color:
            self.console.tag_config(color, foreground=color)
            self.console.insert(tk.END, message + "\n", color)
        else:
            self.console.insert(tk.END, message + "\n")
        self.console.config(state=tk.DISABLED)
        self.console.see(tk.END)

    def welcome_text(self):
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
        self.append_to_console(ascii_art, "yellow")

    def kill_windows(self):
        try:
            window_id_string = subprocess.check_output(["xdotool", "search", "--class", "lxterminal"]).strip().decode('utf-8')
            window_ids = window_id_string.split('\n')
            for window_id in window_ids:
                try:
                    window_name = subprocess.check_output(["xdotool", "getwindowname", window_id]).decode('utf-8').strip()
                    if "Resistector-connect" in window_name:
                        subprocess.check_output(["xdotool", "windowclose", window_id])
                except subprocess.CalledProcessError:
                    logging.exception(f"Error closing window with ID {window_id}")
        except subprocess.CalledProcessError:
            logging.exception("Error searching for windows with class 'lxterminal'")

    def start_regular_process(self, script_name):
        script_manager = ScriptManager(script_name, self.scripts_dir, self.tmp_dir, self.append_to_console)
        script_manager.start_script(minimized=True)
        script_manager.monitor_process()

    def startup_scripts(self):
        for script_name in self.script_names:
            self.start_regular_process(script_name)

    def client_watchdog(self):
        self.registeredClients = 0
        for clientIP in self.clientIPs:
            client_manager = self.clients[clientIP]
            current_availability = client_manager.ping()
            current_registration = client_manager.connect() if current_availability else False

            if client_manager.status.is_available != current_availability or self.bootupCheck:
                client_manager.status.is_available = current_availability
                if current_availability:
                    self.append_to_console(f"Client {clientIP} is available, but not registered", "yellow")
                    logging.info(f"Client {clientIP} is available, but not registered")
                else:
                    self.append_to_console(f"Client {clientIP} is NOT available. Check if connected to Network", "red")
                    logging.info(f"Client {clientIP} is NOT available. Check if connected to Network")
            if client_manager.status.is_registered != current_registration:
                client_manager.status.is_registered = current_registration
                if current_registration:
                    self.append_to_console(f"Client {clientIP} is registered. Ready for measurement", "green")
                    logging.info(f"Client {clientIP} is registered. Ready for measurement")
                else:
                    if current_availability:
                        self.append_to_console(f"Client {clientIP} is NOT registered. Check if measurementClient.py is running on client", "yellow")
                        logging.info(f"Client {clientIP} is NOT registered. Check if measurementClient.py is running on client")

            if current_availability and current_registration:
                self.registeredClients += 1

        if self.registeredClients == len(self.clientIPs):
            self.button_Plotter.config(state=tk.NORMAL)
            if not self.measurement_server_running:
                self.append_to_console("All clients registered. Measurement server startup", "green")
                logging.info("All clients registered. Measurement server is starting")
                self.start_regular_process("measurementServer.py")
                self.measurement_server_running = True
        else:
            self.button_Plotter.config(state=tk.DISABLED)
            self.measurement_server_running = False

        self.bootupCheck = False
        self.root.after(10000, self.client_watchdog)

    def on_closing(self):
        self.append_to_console("Stopping processes... Please stand by...", color="yellow")
        logging.info("Shutdown initialised ")
        self.kill_windows()
        self.root.after(3000, self.root.destroy)

    def schedule_tasks(self):
        #self.root.after(1000, self.welcome_text)
        self.root.after(5000, self.client_watchdog)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Ignoriere Tastaturunterbrechungen, damit das Programm normal beendet werden kann
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # Protokolliere die Ausnahme
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception


# Initialize Tkinter Window
root = tk.Tk()
app = App(root)
atexit.register(app.kill_windows)
root.mainloop()
