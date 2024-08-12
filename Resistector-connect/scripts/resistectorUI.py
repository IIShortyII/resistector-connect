import os
import json
import logging
import configparser
import numpy as np
from collections import defaultdict, deque
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_cors import CORS


class ConfigManager:
    """Verwaltet das Lesen und Bereinigen der Konfigurationsdaten."""
    
    def __init__(self, config_path):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
    
    def get_value(self, section, option, is_float=False, is_int=False):
        value = self.clean_value(self.config[section][option])
        if is_float:
            return float(value)
        if is_int:
            return int(value)
        return value
    
    @staticmethod
    def clean_value(value):
        """Bereinigt den Wert von Kommentaren und Leerzeichen."""
        return value.split(';')[0].split('#')[0].strip()


class Logger:
    """Verantwortlich für das Setup und das Logging von Nachrichten."""
    
    def __init__(self, log_dir, log_file):
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, log_file)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(self.log_file)]
        )
        self.info("resistectorUI server session started")
    
    @staticmethod
    def info(message):
        logging.info(message)
    
    @staticmethod
    def error(message):
        logging.error(message)


class SensorDataManager:
    """Verwaltet das Laden, Verarbeiten und Speichern von Sensordaten."""
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.mean_values = defaultdict(lambda: defaultdict(lambda: deque(maxlen=50)))
        self.result_register = {}
        self.channel_level_register = {}
        self.display_data = {}
        self.previous_display_data = {}
        self.newest_timestamp = ""
    
    def get_latest_file(self):
        """Findet die neueste Messdatei im Datenverzeichnis."""
        files = [f for f in os.listdir(self.data_dir) if f.endswith('_measurementData.json')]
        if not files:
            Logger.error(f"No measurement data files found in: {self.data_dir}")
            raise FileNotFoundError(f"No measurement data files found in: {self.data_dir}")
        latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(self.data_dir, f)))
        return os.path.join(self.data_dir, latest_file)
    
    def read_sensor_data(self):
        """Liest die neuesten Sensordaten aus der JSON-Datei."""
        latest_file = self.get_latest_file()
        data = []
        with open(latest_file) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                f.seek(0)
                for line in f:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return data
    
    def get_oldest_sensor_data(self, amount):
        """Liefert die ältesten Sensordaten."""
        data = self.read_sensor_data()
        return data[:3 * amount]
    
    def get_newest_sensor_data(self, amount):
        """Liefert die neuesten Sensordaten."""
        data = self.read_sensor_data()
        new_data = data[-3 * amount:]
        self.update_newest_timestamp(new_data)
        return new_data
    
    def update_newest_timestamp(self, timestamp_data):
        """Aktualisiert den neuesten Zeitstempel basierend auf den Sensordaten."""
        self.newest_timestamp = max(timestamp_data, key=lambda x: datetime.fromisoformat(x['timestamp']))['timestamp']
    
    def calculate_means(self, sensor_data, pi_address=None, channels=None):
        """Berechnet die Mittelwerte der Sensordaten."""
        if pi_address and channels:
            for channel in channels:
                channel = f"Kanal {channel}"
                self.mean_values[pi_address][channel].clear()

        for entry in sensor_data:
            entry_pi_address = entry['pi-address']
            if pi_address and entry_pi_address != pi_address:
                continue

            for channel, value in entry['sensor_data'].items():
                if channels and channel not in channels:
                    continue

                self.mean_values[entry_pi_address][channel].append(value)
    
    def get_means(self):
        """Gibt die berechneten Mittelwerte zurück."""
        return {
            pi_address: {channel: np.mean(values) for channel, values in channels.items()}
            for pi_address, channels in self.mean_values.items()
        }
    
    def process_sensor_data(self):
        """Verarbeitet die Sensordaten, indem Mittelwerte berechnet und Zustände aktualisiert werden."""
        if not self.mean_values:
            self.calculate_means(self.get_oldest_sensor_data(50))
        means = self.get_means()
        self.calculate_sensor_data_in_mean(means)
    
    def calculate_sensor_data_in_mean(self, means):
        """Vergleicht Sensordaten mit den Mittelwerten und aktualisiert das Ergebnisregister."""
        config = ConfigManager(CONFIG_PATH)
        threshold = config.get_value('Local-Settings', 'threshold', is_float=True)
        hysteresis_value = config.get_value('Local-Settings', 'hysteresis', is_int=True)

        current_sensor_data = self.get_newest_sensor_data(1)
        Logger.info(f"Current means: {means}")
        Logger.info(f"Current sensor data: {current_sensor_data}")

        for data in current_sensor_data:
            address = data["pi-address"]
            sensor_data = data["sensor_data"]

            if address not in means:
                continue

            if address not in self.result_register:
                self.result_register[address] = {channel: 0 for channel in sensor_data.keys()}

            for channel, value in sensor_data.items():
                mean_value = means[address].get(channel)
                if mean_value is None:
                    continue

                if mean_value - threshold > value:
                    self.result_register[address][channel] -= 1
                elif mean_value + threshold < value:
                    self.result_register[address][channel] += 1
                else:
                    self.result_register[address][channel] = 0

                if CalibrationManager.is_calibration_running:
                    if self.result_register[address][channel] != 0:
                        self.calculate_means(self.get_newest_sensor_data(5), address, [channel])
                else:
                    if self.result_register[address][channel] >= hysteresis_value:
                        Logger.info(f"Above threshold: {address} {channel}")
                        self.result_register[address][channel] = 0
                        self.run_hysteresis_condition(address, channel, "up")
                    elif self.result_register[address][channel] <= -hysteresis_value:
                        Logger.info(f"Below threshold: {address} {channel}")
                        self.result_register[address][channel] = 0
                        self.run_hysteresis_condition(address, channel, "down")
        Logger.info(f"Result register: {self.result_register}")
    
    def run_hysteresis_condition(self, address, channel, condition):
        """Aktualisiert das Kanalregister basierend auf der Hysterese-Bedingung."""
        if address not in self.channel_level_register:
            self.channel_level_register[address] = {}
        if channel not in self.channel_level_register[address]:
            self.channel_level_register[address][channel] = {"level": 0, "lifetime": 5}

        if condition == "up":
            self.channel_level_register[address][channel]["level"] = 1
        elif condition == "down":
            self.channel_level_register[address][channel]["level"] = -1

        Logger.info(f"Channel level register: {self.channel_level_register}")
        self.calculate_means(self.get_newest_sensor_data(5), address, [channel])
    
    def get_system_state(self):
        config = ConfigManager(CONFIG_PATH)
        hysteresis_value = config.get_value('Local-Settings', 'hysteresis', is_int=True)
        """Bestimmt den Systemzustand basierend auf den aktuellen Registern."""
        if self.channel_level_register:
            return "Red"
        
        # Überprüfen, ob alle Werte in result_register 0 sind
        all_zeros = True
        for channels in self.result_register.values():
            if any(value > hysteresis_value / 2 or value < -hysteresis_value / 2 for value in channels.values()):

                all_zeros = False
                break
        
        if all_zeros:
            return "Green"
        else:
            return "Yellow"
    
    def reset_display_data(self):
        """Setzt die Anzeigedaten zurück."""
        self.display_data.clear()
        self.previous_display_data.clear()


class CalibrationManager:
    """Verantwortlich für die Durchführung und Überwachung der Kalibrierung."""
    
    is_calibration_running = False
    calibration_status = {'status': 'Not Started'}
    
    @classmethod
    def start_calibration(cls, sensor_manager):
        """Startet die Kalibrierungsroutine."""
        cls.calibration_status = {'status': 'In Progress'}
        cls.is_calibration_running = True

        if not sensor_manager.mean_values:
            sensor_manager.calculate_means(sensor_manager.get_oldest_sensor_data(50))

        means = sensor_manager.get_means()
        sensor_manager.calculate_sensor_data_in_mean(means)

        while not cls.check_calibration(sensor_manager):
            means = sensor_manager.get_means()
            sensor_manager.calculate_sensor_data_in_mean(means)

        sensor_manager.reset_display_data()
        Logger.info("Calibration completed")
        cls.calibration_status = {'status': 'Completed'}
        cls.is_calibration_running = False
        return True
    
    @classmethod
    def check_calibration(cls, sensor_manager):
        """Überprüft, ob die Kalibrierung erfolgreich abgeschlossen wurde."""
        config = ConfigManager(CONFIG_PATH)
        hysteresis_check = config.get_value('Local-Settings', 'hysteresis', is_int=True) + 2

        while cls.is_calibration_running or hysteresis_check > 0:
            if not cls.is_calibration_running:
                hysteresis_check -= 1
            for address, channels in sensor_manager.result_register.items():
                for channel, value in channels.items():
                    if value != 0:
                        Logger.info("Calibration values not okay")
                        cls.is_calibration_running = True
                        return False
            Logger.info("Calibration values okay")
            cls.is_calibration_running = False

        return True


class DisplayDataManager:
    """Verwaltet die Anzeige- und Komponentenerkennungslogik."""
    
    def __init__(self, sensor_manager):
        self.sensor_manager = sensor_manager
    
    def convert_data_to_display(self):
        """Konvertiert Sensordaten in ein Anzeigeformat."""
        config = ConfigManager(CONFIG_PATH)
        x_dim = config.get_value('Web-UI', 'amountX-Axis', is_int=True)
        y_dim = config.get_value('Web-UI', 'amountY-Axis', is_int=True)

        for x in range(x_dim):
            for y in range(y_dim):
                key = f"{x},{y}"
                self.sensor_manager.display_data[key] = {'State': 'O'}
                if key in self.sensor_manager.previous_display_data:
                    self.sensor_manager.display_data[key]['State'] = self.sensor_manager.previous_display_data[key]['State']

        self.detect_component_levels(x_dim, y_dim)
        self.sensor_manager.previous_display_data = self.sensor_manager.display_data.copy()
        detected_components = self.detect_components(x_dim, y_dim)
        self.delete_lifetime()
        
        return {
            'displayData': self.sensor_manager.display_data,
            'components': detected_components,
            'timestamp': self.sensor_manager.newest_timestamp
        }
    
    def detect_component_levels(self, x_dim, y_dim):
        """Ermittelt die Zustände der verschiedenen Komponenten auf der Anzeige."""
        x_coords_negative, y_coords_negative, logic_dim_negative = set(), set(), set()
        x_coords_positive, y_coords_positive, logic_dim_positive = set(), set(), set()

        for address, channels in self.sensor_manager.channel_level_register.items():
            for channel, data in channels.items():
                level = data["level"]
                channel_number = int(''.join(filter(str.isdigit, channel)))

                if level == -1:
                    self._categorize_negative(address, channel_number, x_coords_negative, y_coords_negative, logic_dim_negative)
                elif level == 1:
                    self._categorize_positive(address, channel_number, x_coords_positive, y_coords_positive, logic_dim_positive)

        self._update_display_data(x_dim, y_dim, x_coords_negative, y_coords_negative, logic_dim_negative, 'X', 'XX')
        self._update_display_data(x_dim, y_dim, x_coords_positive, y_coords_positive, logic_dim_positive, 'O', 'O')

    @staticmethod
    def _categorize_negative(address, channel_number, x_neg, y_neg, logic_neg):
        """Kategorisiert negative Zustände basierend auf der Adresse."""
        if address == "10.42.0.1":
            x_neg.add(channel_number)
        elif address == "10.42.0.2":
            y_neg.add(channel_number)
        elif address == "10.42.0.3":
            logic_neg.add(channel_number)

    @staticmethod
    def _categorize_positive(address, channel_number, x_pos, y_pos, logic_pos):
        """Kategorisiert positive Zustände basierend auf der Adresse."""
        if address == "10.42.0.1":
            x_pos.add(channel_number)
        elif address == "10.42.0.2":
            y_pos.add(channel_number)
        elif address == "10.42.0.3":
            logic_pos.add(channel_number)

    def _update_display_data(self, x_dim, y_dim, x_coords, y_coords, logic_dim, state, logic_state):
        """Aktualisiert die Anzeigedaten basierend auf den erkannten Zuständen."""
        for x in range(x_dim):
            for y in range(y_dim):
                coord_key = f"{x},{y}"
                if x in x_coords and y in y_coords:
                    self.sensor_manager.display_data[coord_key]['State'] = state
                    if y in logic_dim:
                        self.sensor_manager.display_data[coord_key]['State'] = logic_state
                        Logger.info(f"Logical layer detected at {coord_key}")

    def detect_components(self, x_dim, y_dim):
        """Erkennt Komponenten auf der Anzeige basierend auf bekannten Mustern."""
        component_patterns = {
            'LED': [('X', 'X')],
            'Resistor': [('XX', 'XX')],
            'Cable': [('X', 'X', 'X')],
            'Transistor': [('X', 'XX', 'X')]
        }

        detected_components = []

        for x in range(x_dim):
            for y in range(y_dim):
                for component, pattern in component_patterns.items():
                    self._detect_component(x, y, x_dim, y_dim, component, pattern, detected_components)

        return detected_components

    def _detect_component(self, x, y, x_dim, y_dim, component, pattern, detected_components):
        """Prüft, ob ein bestimmtes Komponenten-Muster an der Position vorhanden ist."""
        pattern_length = len(pattern[0])
        if x + pattern_length - 1 < x_dim:
            if all(self.sensor_manager.display_data.get(f"{x + i},{y}", {}).get('State') == pattern[0][i]
                   for i in range(pattern_length)):
                detected_components.append({
                    'type': component,
                    'x': x + pattern_length // 2,
                    'y': y,
                    'orientation': 'horizontal'
                })

        if y + pattern_length - 1 < y_dim:
            if all(self.sensor_manager.display_data.get(f"{x},{y + i}", {}).get('State') == pattern[0][i]
                   for i in range(pattern_length)):
                detected_components.append({
                    'type': component,
                    'x': x,
                    'y': y + pattern_length // 2,
                    'orientation': 'vertical'
                })

    def delete_lifetime(self):
        """Reduziert die Lebensdauer der Kanäle im Kanalregister und entfernt abgelaufene Einträge."""
        for address in list(self.sensor_manager.channel_level_register.keys()):
            for channel in list(self.sensor_manager.channel_level_register[address].keys()):
                Logger.info("Reducing channel lifetime")
                self.sensor_manager.channel_level_register[address][channel]["lifetime"] -= 1
                if self.sensor_manager.channel_level_register[address][channel]["lifetime"] <= 0:
                    del self.sensor_manager.channel_level_register[address][channel]
                    Logger.info(f"Removed {address} {channel} from channel_level_register due to expired lifetime")
            if not self.sensor_manager.channel_level_register[address]:
                del self.sensor_manager.channel_level_register[address]


class AppManager:
    """Verwaltet die Flask-App und deren Routen."""
    
    def __init__(self, sensor_manager, display_manager):
        self.sensor_manager = sensor_manager
        self.display_manager = display_manager
        self.app = Flask(__name__)
        CORS(self.app)
        self.setup_routes()

    def setup_routes(self):
        """Setzt die Flask-Routen für die Web-App."""
        self.app.add_url_rule('/', 'home', self.home, methods=['GET'])
        self.app.add_url_rule('/sensor_data', 'get_sensor_data', self.get_sensor_data, methods=['GET'])
        self.app.add_url_rule('/calibrate', 'start_calibration', self.start_calibration, methods=['GET'])
        self.app.add_url_rule('/calibration_status', 'get_calibration_status', self.get_calibration_status, methods=['GET'])
    
    def home(self):
        """Rendert die Hauptseite der Webanwendung."""
        config = ConfigManager(CONFIG_PATH)
        rows = config.get_value('Web-UI', 'amountY-Axis', is_int=True)
        cols = config.get_value('Web-UI', 'amountX-Axis', is_int=True)
        return render_template('index.html', rows=rows, cols=cols)
    
    def get_sensor_data(self):
        """Liefert die aktuellen Sensordaten und deren Anzeigezustand."""
        if CalibrationManager.is_calibration_running:
            response = jsonify(message="Kalibrierung läuft")
            response.status_code = 423
            return response
        else:
            self.sensor_manager.process_sensor_data()
            data = self.display_manager.convert_data_to_display()

            system_state = sensor_manager.get_system_state()
            data["SystemState"] = system_state
            return jsonify(data)
    
    def start_calibration(self):
        """Startet den Kalibrierungsprozess."""
        CalibrationManager.start_calibration(self.sensor_manager)
        return jsonify(message="Kalibrierung gestartet"), 200
    
    def get_calibration_status(self):
        """Gibt den aktuellen Status der Kalibrierung zurück."""
        Logger.info(f"Calibration Status: {CalibrationManager.calibration_status}")
        return jsonify(CalibrationManager.calibration_status), 200
    
    def run(self):
        """Startet die Flask-Webanwendung."""
        config = ConfigManager(CONFIG_PATH)
        ip_address = config.get_value('Local-Settings', 'local_client_ip')
        port = config.get_value('Network', 'webapp_port', is_int=True)
        self.app.run(host=ip_address, port=port)


if __name__ == '__main__':
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
    DATA_DIR = os.path.join(BASE_DIR, 'measurement_data')
    LOG_DIR = os.path.join(BASE_DIR, 'logs')
    LOG_FILE = 'resistectorUI.log'

    logger = Logger(LOG_DIR, LOG_FILE)
    sensor_manager = SensorDataManager(DATA_DIR)
    display_manager = DisplayDataManager(sensor_manager)
    app_manager = AppManager(sensor_manager, display_manager)
    app_manager.run()
