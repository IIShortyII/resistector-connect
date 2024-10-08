import os
import json
import logging
import configparser
import uuid
import copy
import numpy as np
from collections import defaultdict, deque
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_cors import CORS


class ConfigManager:
    """Manages reading and cleaning configuration data."""
    
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
        """Cleans the value of comments and whitespace."""
        return value.split(';')[0].split('#')[0].strip()


class Logger:
    """Responsible for setting up and logging messages."""
    
    def __init__(self, log_dir, log_file):
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, log_file)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(self.log_file)]
        )
        self.info("resistectorUI server session started")
        self.configure_werkzeug_logging()
    
    @staticmethod
    def info(message):
        logging.info(message)
    
    @staticmethod
    def error(message):
        logging.error(message)

    @staticmethod
    def debug(message):
        logging.debug(message)

    @staticmethod
    def configure_werkzeug_logging():
        """Configures Werkzeug logging to suppress GET request logs."""
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.ERROR)  # Only log errors from Werkzeug

class SensorDataManager:
    """Manages loading, processing, and storing sensor data."""
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.mean_values = defaultdict(lambda: defaultdict(lambda: deque(maxlen=50)))
        self.result_register = {}
        self.channel_level_register = {}
        self.display_data = {}
        self.previous_display_data = {}
        self.newest_timestamp = ""
    
    def get_latest_file(self):
        """Finds the latest measurement file in the data directory."""
        files = [f for f in os.listdir(self.data_dir) if f.endswith('_measurementData.json')]
        if not files:
            Logger.error(f"No measurement data files found in: {self.data_dir}")
            raise FileNotFoundError(f"No measurement data files found in: {self.data_dir}")
        latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(self.data_dir, f)))
        return os.path.join(self.data_dir, latest_file)
    
    def read_sensor_data(self):
        """Reads the latest sensor data from the JSON file."""
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
        """Returns the oldest sensor data."""
        data = self.read_sensor_data()
        return data[:3 * amount]
    
    def get_newest_sensor_data(self, amount):
        """Returns the newest sensor data."""
        data = self.read_sensor_data()
        new_data = data[-3 * amount:]
        self.update_newest_timestamp(new_data)
        return new_data
    
    def update_newest_timestamp(self, timestamp_data):
        """Updates the newest timestamp based on the sensor data."""
        self.newest_timestamp = max(timestamp_data, key=lambda x: datetime.fromisoformat(x['timestamp']))['timestamp']
    
    def calculate_means(self, sensor_data, pi_address=None, channels=None):
        """Calculates the means of the sensor data."""
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
        """Returns the calculated means."""
        means = {}
        for pi_address, channels in self.mean_values.items():
            means[pi_address] = {}
            for channel, values in channels.items():
                if len(values) > 0:
                    means[pi_address][channel] = np.mean(values)
                else:
                    means[pi_address][channel] = np.nan  # Oder ein anderer Standardwert, z.B. 0
        return means

    
    def process_sensor_data(self):
        """Processes the sensor data by calculating means and updating states."""
        if not self.mean_values:
            self.calculate_means(self.get_oldest_sensor_data(50))
        means = self.get_means()
        self.calculate_sensor_data_in_mean(means)
    
    def calculate_sensor_data_in_mean(self, means):
        """Compares sensor data with the means and updates the result register."""
        config = ConfigManager(CONFIG_PATH)
        threshold = config.get_value('Local-Settings', 'threshold', is_float=True)
        hysteresis_value = config.get_value('Local-Settings', 'hysteresis', is_int=True)

        current_sensor_data = self.get_newest_sensor_data(1)
        Logger.debug(f"Current means: {means}")
        Logger.debug(f"Current sensor data: {current_sensor_data}")

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
                        Logger.debug(f"Above threshold: {address} {channel}")
                        self.result_register[address][channel] = 0
                        self.run_hysteresis_condition(address, channel, "up")
                    elif self.result_register[address][channel] <= -hysteresis_value:
                        Logger.debug(f"Below threshold: {address} {channel}")
                        self.result_register[address][channel] = 0
                        self.run_hysteresis_condition(address, channel, "down")
        Logger.debug(f"Result register: {self.result_register}")
    
    def run_hysteresis_condition(self, address, channel, condition):
        """Updates the channel register based on the hysteresis condition."""
        if address not in self.channel_level_register:
            self.channel_level_register[address] = {}
        if channel not in self.channel_level_register[address]:
            self.channel_level_register[address][channel] = {"level": 0, "lifetime": 10}

        if condition == "up":
            self.channel_level_register[address][channel]["level"] = 1
        elif condition == "down":
            self.channel_level_register[address][channel]["level"] = -1

        Logger.debug(f"Channel level register: {self.channel_level_register}")
        self.calculate_means(self.get_newest_sensor_data(5), address, [channel])
    
    def get_system_state(self):
        config = ConfigManager(CONFIG_PATH)
        hysteresis_value = config.get_value('Local-Settings', 'hysteresis', is_int=True)
        """Determines the system state based on the current registers."""
        if self.channel_level_register:
            return "Red"

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
        """Resets the display data."""
        self.display_data.clear()
        self.previous_display_data.clear()


class CalibrationManager:
    """Responsible for performing and monitoring calibration."""
    
    is_calibration_running = False
    calibration_status = {'status': 'Not Started'}
    
    @classmethod
    def start_calibration(cls, sensor_manager):
        """Starts the calibration routine."""
        cls.calibration_status = {'status': 'In Progress'}
        cls.is_calibration_running = True

        if not sensor_manager.mean_values:
            sensor_manager.calculate_means(sensor_manager.get_oldest_sensor_data(50))

        means = sensor_manager.get_means()
        sensor_manager.calculate_sensor_data_in_mean(means)

        while not cls.is_calibration_successful(sensor_manager):
            means = sensor_manager.get_means()
            sensor_manager.calculate_sensor_data_in_mean(means)

        sensor_manager.reset_display_data()
        Logger.debug("Calibration completed")
        cls.calibration_status = {'status': 'Completed'}
        cls.is_calibration_running = False
        return True
    
    @classmethod
    def is_calibration_successful(cls, sensor_manager):
        """Checks if the calibration has been successfully completed."""
        config = ConfigManager(CONFIG_PATH)
        hysteresis_check = config.get_value('Local-Settings', 'hysteresis', is_int=True) + 2

        while cls.is_calibration_running or hysteresis_check > 0:
            if not cls.is_calibration_running:
                hysteresis_check -= 1
            for address, channels in sensor_manager.result_register.items():
                for channel, value in channels.items():
                    if value != 0:
                        Logger.debug("Calibration values not okay")
                        cls.is_calibration_running = True
                        return False
            Logger.debug("Calibration values okay")
            cls.is_calibration_running = False

        return True


class DisplayDataManager:
    """Manages the display and component recognition logic."""

    def __init__(self, sensor_manager):
        self.sensor_manager = sensor_manager
        self.old_detected_components = {}
        self.detection_counter = {}

    def prepare_display_data(self):
        """Converts sensor data into a display format."""
        config = ConfigManager(CONFIG_PATH)
        x_dim = config.get_value('Web-UI', 'amountX-Axis', is_int=True)
        y_dim = config.get_value('Web-UI', 'amountY-Axis', is_int=True)

        for x in range(x_dim):
            for y in range(y_dim):
                key = f"{x},{y}"
                self.sensor_manager.display_data[key] = {'State': 'O'}
                if key in self.sensor_manager.previous_display_data:
                    self.sensor_manager.display_data[key]['State'] = self.sensor_manager.previous_display_data[key]['State']

        self.update_component_levels(x_dim, y_dim) # ist es X, XX oder O -> Es kommt ein DisplayData Datensatz raus
        self.sensor_manager.previous_display_data = self.sensor_manager.display_data.copy()
        detected_components = self.find_components(x_dim, y_dim)
        self.old_detected_components = copy.deepcopy(detected_components)
        self.delete_lifetime()

        return {
            'displayData': self.sensor_manager.display_data,
            'components': detected_components,
            'timestamp': self.sensor_manager.newest_timestamp
        }

    def update_component_levels(self, x_dim, y_dim):
        """Determines the states of various components on the display."""
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
        """Categorizes negative states based on the address."""
        if address == "10.42.0.1":
            x_neg.add(channel_number)
        elif address == "10.42.0.2":
            y_neg.add(channel_number)
        elif address == "10.42.0.3":
            logic_neg.add(channel_number)

    @staticmethod
    def _categorize_positive(address, channel_number, x_pos, y_pos, logic_pos):
        """Categorizes positive states based on the address."""
        if address == "10.42.0.1":
            x_pos.add(channel_number)
        elif address == "10.42.0.2":
            y_pos.add(channel_number)
        elif address == "10.42.0.3":
            logic_pos.add(channel_number)

    def _update_display_data(self, x_dim, y_dim, x_coords, y_coords, logic_dim, state, logic_state):
        """Updates the display data based on detected states."""
        for x in range(x_dim):
            for y in range(y_dim):
                coord_key = f"{x},{y}"
                if x in x_coords and y in y_coords:
                    self.sensor_manager.display_data[coord_key]['State'] = state
                    if y in logic_dim:
                        self.sensor_manager.display_data[coord_key]['State'] = logic_state
                        Logger.debug(f"Logical layer detected at {coord_key}")

    def find_components(self, x_dim, y_dim):
        """Detects components on the display based on known patterns."""
        component_patterns = {
            'Transistor': [('X', 'XX', 'X')],
            'Resistor': [('XX', 'XX')],
            'Cable': [('X', 'X', 'X')],
            'LED': [('X', 'X')]
        }

        self.required_counts = {
            'LED': 8,
            'Resistor': 6,
            'Transistor': 1,
            'Cable': 4
        }

        occupied_coords = set()
        self.check_old_grid(occupied_coords)
        detected_components = copy.deepcopy(self.old_detected_components)
        
        for comp in detected_components.values():
            occupied_coords.update(comp['coordinates'])

        for x in range(x_dim):
            for y in range(y_dim):
                if not self.is_coord_occupied(detected_components, x, y):
                    for component, pattern in component_patterns.items():
                        self._detect_component(x, y, x_dim, y_dim, component, pattern, detected_components, occupied_coords)

        return detected_components

    def _detect_component(self, x, y, x_dim, y_dim, component, pattern, detected_components, occupied_coords):
        """Checks if a specific component pattern is present at the position."""
        pattern_length = len(pattern[0])

        def update_detection_counter(coords, component_type):
            key = (component_type, tuple(coords))
            if key not in self.detection_counter:
                self.detection_counter[key] = 0
            self.detection_counter[key] += 1
            return self.detection_counter[key]

        def is_component_fully_detected(count, component_type):
            required_count = self.required_counts.get(component_type, 10)
            return count >= required_count

        # Check horizontal pattern
        if x + pattern_length - 1 < x_dim:
            if all(self.sensor_manager.display_data.get(f"{x + i},{y}", {}).get('State') == pattern[0][i]
                   and (x + i, y) not in occupied_coords for i in range(pattern_length)):

                coordinates = [(x + i, y) for i in range(pattern_length)]
                count = update_detection_counter(coordinates, component)
                if is_component_fully_detected(count, component):
                    comp_id = str(uuid.uuid4())
                    detected_components[comp_id] = {
                        'type': component,
                        'x': x + pattern_length -1,
                        'y': y,
                        'orientation': 'horizontal',
                        'coordinates': coordinates
                    }
                    self.detection_counter.clear()
                    occupied_coords.update(coordinates)

        # Check vertical pattern
        if y + pattern_length - 1 < y_dim:
            if all(self.sensor_manager.display_data.get(f"{x},{y + i}", {}).get('State') == pattern[0][i]
                   and (x, y + i) not in occupied_coords for i in range(pattern_length)):

                coordinates = [(x, y + i) for i in range(pattern_length)]
                count = update_detection_counter(coordinates, component)
                if is_component_fully_detected(count, component):
                    comp_id = str(uuid.uuid4())
                    detected_components[comp_id] = {
                        'type': component,
                        'x': x,
                        'y': y + pattern_length // 2,
                        'orientation': 'vertical',
                        'coordinates': coordinates
                    }
                    self.detection_counter.clear()
                    occupied_coords.update(coordinates)


    def check_old_grid(self, occupied_coords):
        display_data = self.sensor_manager.display_data
        old_grid_data = self.old_detected_components

        removed_Components_id = []

        if old_grid_data:
            for id, component_detail in old_grid_data.items():
                still_existing_component = True
                for x, y in component_detail['coordinates']:
                    coord_key = f"{x},{y}"
                    state = display_data.get(coord_key, {}).get('State')
                    if state not in ['X', 'XX']:
                        still_existing_component = False
                        occupied_coords.discard((x,y))
                        break
                if not still_existing_component:
                    removed_Components_id.append(id)
            for id in removed_Components_id:
                del old_grid_data[id]

                Logger.debug(f"Removed component with UUID {id} from old components because it was removed from user.")
        else:
            Logger.debug(f"No old Component Grid Data available. It is empty.")
                    
    def is_coord_occupied(self, components_dict, x, y):
        for component in components_dict.values():
            # Überprüfe, ob 'coordinates' im aktuellen Eintrag vorhanden ist
            if 'coordinates' in component:
             # Überprüfe, ob das Koordinatenpaar (x, y) in 'coordinates' enthalten ist
                if (x, y) in component['coordinates']:
                 return True
        return False

    def delete_lifetime(self):
        """Reduces the lifetime of channels in the channel register and removes expired entries."""
        for address in list(self.sensor_manager.channel_level_register.keys()):
            for channel in list(self.sensor_manager.channel_level_register[address].keys()):
                Logger.debug("Reducing channel lifetime")
                self.sensor_manager.channel_level_register[address][channel]["lifetime"] -= 1
                if self.sensor_manager.channel_level_register[address][channel]["lifetime"] <= 0:
                    del self.sensor_manager.channel_level_register[address][channel]
                    Logger.debug(f"Removed {address} {channel} from channel_level_register due to expired lifetime")
            if not self.sensor_manager.channel_level_register[address]:
                del self.sensor_manager.channel_level_register[address]


class AppManager:
    """Manages the Flask app and its routes."""
    
    def __init__(self, sensor_manager, display_manager):
        self.sensor_manager = sensor_manager
        self.display_manager = display_manager
        self.app = Flask(__name__)
        CORS(self.app)
        self.setup_routes()

    def setup_routes(self):
        """Sets up the Flask routes for the web app."""
        self.app.add_url_rule('/', 'home', self.home, methods=['GET'])
        self.app.add_url_rule('/sensor_data', 'get_sensor_data', self.get_sensor_data, methods=['GET'])
        self.app.add_url_rule('/calibrate', 'start_calibration', self.start_calibration, methods=['GET'])
        self.app.add_url_rule('/calibration_status', 'get_calibration_status', self.get_calibration_status, methods=['GET'])
    
    def home(self):
        """Renders the main page of the web application."""
        config = ConfigManager(CONFIG_PATH)
        rows = config.get_value('Web-UI', 'amountY-Axis', is_int=True)
        cols = config.get_value('Web-UI', 'amountX-Axis', is_int=True)
        return render_template('index.html', rows=rows, cols=cols)
    
    def get_sensor_data(self):
        """Provides the current sensor data and its display state."""
        if CalibrationManager.is_calibration_running:
            response = jsonify(message="Kalibrierung läuft")
            response.status_code = 423
            return response
        else:
            self.sensor_manager.process_sensor_data()
            data = self.display_manager.prepare_display_data()

            system_state = sensor_manager.get_system_state()
            data["SystemState"] = system_state
            return jsonify(data)
    
    def start_calibration(self):
        """Starts the calibration process."""
        CalibrationManager.start_calibration(self.sensor_manager)
        return jsonify(message="Kalibrierung gestartet"), 200
    
    def get_calibration_status(self):
        """Returns the current status of the calibration."""
        Logger.debug(f"Calibration Status: {CalibrationManager.calibration_status}")
        return jsonify(CalibrationManager.calibration_status), 200
    
    def run(self):
        """Starts the Flask web application."""
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
