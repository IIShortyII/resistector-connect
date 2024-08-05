import os
import json
import logging
import configparser
from flask import Flask, render_template, jsonify
from flask_cors import CORS
import numpy as np
from collections import defaultdict, deque
from datetime import datetime

#TODO: LOGICLAYER IMPLEMENTIEREN!!!
# Konfigurations- und Log-Pfade relativ zum Skriptverzeichnis
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
DATA_DIR = os.path.join(BASE_DIR, 'measurement_data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'resistectorUI.log')

# Sicherstellen, dass das Log-Verzeichnis existiert
os.makedirs(LOG_DIR, exist_ok=True)

# Logging-Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE)]
)

logging.info("resistectorUI server session started")

# Flask-App initialisieren
app = Flask(__name__)
CORS(app)

mean_values = defaultdict(lambda: defaultdict(lambda: deque(maxlen=50)))
result_register = {}
channel_level_register = {}
previous_display_data = {}
newestTimestamp = ""
isCalibrationRunning = False
calibration_status = {'status': 'Not Started'}

def read_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config

def clean_value(value):
    return value.split(';')[0].split('#')[0].strip()

def get_pi_addresses(config):
    raw_addresses = config['Network']['client_ips']
    return [clean_value(addr) for addr in raw_addresses.split(',')]

def get_latest_file():
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('_measurementData.json')]
    if not files:
        logging.error(f"No measurement data files found in: {DATA_DIR}")
        raise FileNotFoundError(f"No measurement data files found in: {DATA_DIR}")
    latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(DATA_DIR, f)))
    return os.path.join(DATA_DIR, latest_file)

def read_sensor_data():
    latest_file = get_latest_file()
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

def get_oldest_sensor_data(amountData):
    data = read_sensor_data()
    oldest_data = data[:(3*amountData)]
    return oldest_data

def get_newest_sensor_data(amountData):
    data = read_sensor_data()
    new_data = data[-(3*amountData):]
    loadnewestTimestamp(new_data)
    return new_data

def loadnewestTimestamp(timeStampdata):
    global newestTimestamp
    newestTimestamp = max(timeStampdata, key=lambda x: datetime.fromisoformat(x['timestamp']))['timestamp']

def is_empty(ddict):
    return len(ddict) == 0

def calculate_means(sensor_data, pi_address=None, channels=None):
    if pi_address and channels:
        for channel in channels:
            channel = "Kanal "+ str(channel)
            if pi_address in mean_values and channel in mean_values[pi_address]:
                mean_values[pi_address][channel].clear()

    for entry in sensor_data:
        entry_pi_address = entry['pi-address']
        
        if pi_address and entry_pi_address != pi_address:
            continue
        
        for channel, value in entry['sensor_data'].items():
            if channels and channel not in channels:
                continue
            
            if entry_pi_address not in mean_values:
                mean_values[entry_pi_address] = {}
            if channel not in mean_values[entry_pi_address]:
                mean_values[entry_pi_address][channel] = []
            
            mean_values[entry_pi_address][channel].append(value)

def get_means():
    means = {}
    for pi_address, channels in mean_values.items():
        means[pi_address] = {channel: np.mean(values) for channel, values in channels.items()}

    logging.info(f"Current means: {means}")

    return means

def calculate_SensorData_inMean(means):
    global result_register
    global isCalibrationRunning
    global mean_values
    config = read_config()
    threshold = float(clean_value(config['Local-Settings']['threshold']))
    hystersis_value = int(clean_value(config['Local-Settings']['hysteresis']))

    currentSensordata = get_newest_sensor_data(1)

    for data in currentSensordata:
        address = data["pi-address"]
        sensor_data = data["sensor_data"]

        if address in means:
            if address not in result_register:
                result_register[address] = {kanal: 0 for kanal in sensor_data.keys()}

            for kanal, value2 in sensor_data.items():
                value1 = means[address].get(kanal)

                if value1 is not None:
                    if value1 - threshold > value2:
                        result_register[address][kanal] -= 1
                    elif value1 + threshold < value2:
                        result_register[address][kanal] += 1
                    else:
                        result_register[address][kanal] = 0

                if isCalibrationRunning:
                    if result_register[address][kanal] != 0:
                        calculate_means(get_newest_sensor_data(5), address, kanal)
                
                else:
                    if result_register[address][kanal] == hystersis_value:
                        logging.info(f"Drüber {address} {kanal}")
                        runHystersisCondition(address, kanal, "up")
                        result_register[address][kanal] = 0
                    elif result_register[address][kanal] == -hystersis_value:
                        logging.info(f"Drunter {address} {kanal}")
                        runHystersisCondition(address, kanal, "down")
                        result_register[address][kanal] = 0
    logging.info(f"result_register: {result_register}")

def runHystersisCondition(address, channel, condition):
    global channel_level_register
    if address not in channel_level_register:
        channel_level_register[address] = {}
    if channel not in channel_level_register[address]:
        channel_level_register[address][channel] = {"level": 0, "lifetime": 9}
        
    if condition == "up":
        channel_level_register[address][channel]["level"] = +1
    elif condition == "down":
        channel_level_register[address][channel]["level"] = -1
    logging.info(f"channel_level_register: {channel_level_register}")
    calculate_means(get_newest_sensor_data(5), address, channel)

def checkCalibration():
    global isCalibrationRunning
    global result_register

    config = read_config()
    hystersisCheck =  int(clean_value(config['Local-Settings']['hysteresis']))+2
    while isCalibrationRunning or hystersisCheck > 0:
        if not isCalibrationRunning: 
            hystersisCheck -= 1; 
        for address, channels in result_register.items():
            for channel, wert in channels.items():
                if wert != 0:
                    logging.info(f"Werte NICHT ok")
                    isCalibrationRunning = True 
                    return False
                else: 
                    isCalibrationRunning = False  
    logging.info("Werte ok, Kalibierung ist fertig")
    return True



def calibrationRoutine():
    global isCalibrationRunning 
    global calibration_status
    checktheCalibration = False
    calibration_status = {'status': 'In Progress'}

    if is_empty(mean_values):
        calculate_means(get_oldest_sensor_data(50))
    means = get_means()
    isCalibrationRunning = True
    calculate_SensorData_inMean(means)
    while not checktheCalibration:
        checktheCalibration = checkCalibration()
        means = get_means()
        calculate_SensorData_inMean(means)

    logging.info("Kalibrierung Done")
    calibration_status = {'status': 'Completed'}
    return True

    

def convertDatatoDisplay():
    global previous_display_data

    config = read_config()
    x_dim = int(clean_value(config['Web-UI']['amountX-Axis']))
    y_dim = int(clean_value(config['Web-UI']['amountY-Axis']))
    logic_dim = int(clean_value(config['Web-UI']['amountY-Axis']))

    displayData = {}
    for x in range(x_dim):
        for y in range(y_dim):
            key = f"{x},{y}"
            displayData[key] = {'State': 'O'}
            if key in previous_display_data:
                displayData[key]['State'] = previous_display_data[key]['State']

    x_coords_negative = set()
    y_coords_negative = set()
    logic_dim_negative= set()

    x_coords_positive = set()
    y_coords_positive = set()
    logic_dim_positive= set()


    for address, channels in channel_level_register.items():
        for channel, data in channels.items():
            level = data["level"]
            channel_number = int(''.join(filter(str.isdigit, channel)))
            if level == -1:
                if address == "10.42.0.1":
                    x_coords_negative.add(channel_number)
                elif address == "10.42.0.2":
                    y_coords_negative.add(channel_number)
                elif address == "10.42.0.3":
                    logic_dim_negative.add(channel_number)
            elif level == +1:
                if address == "10.42.0.1":
                    x_coords_positive.add(channel_number)
                elif address == "10.42.0.2":
                    y_coords_positive.add(channel_number)
                elif address == "10.42.0.3":
                    logic_dim_positive.add(channel_number)

    for x in range(x_dim):
        for y in range(y_dim):
            coord_key = f"{x},{y}"
            if x in x_coords_negative and y in y_coords_negative:
                displayData[coord_key]['State'] = 'X'
                channel_level_register['10.42.0.1']["Kanal "+ str(x)]["lifetime"] -= 1
                channel_level_register['10.42.0.2']["Kanal "+ str(y)]["lifetime"] -= 1
                if y in logic_dim_negative: 
                    displayData[coord_key]['State'] = 'XX'
                    channel_level_register['10.42.0.3']["Kanal "+ str(y)]["lifetime"] -= 1
                    logging.info(f"We have a LOGICLAYER!")
                deleteLifeTime()
                logging.info(f"Have one! {coord_key}")
            elif x in x_coords_positive and y in y_coords_positive and displayData[coord_key]['State'] == 'X':
                displayData[coord_key]['State'] = 'O'
                channel_level_register['10.42.0.1']["Kanal "+ str(x)]["lifetime"] -= 1
                channel_level_register['10.42.0.2']["Kanal "+ str(y)]["lifetime"] -= 1
                logging.info(f"Lost one! {coord_key}")

    previous_display_data = displayData

    return displayData

def deleteLifeTime():
    for address in list(channel_level_register.keys()):
        for channel in list(channel_level_register[address].keys()):
            if channel_level_register[address][channel]["lifetime"] <= 0:
                del channel_level_register[address][channel]
                logging.info(f"Removed {address} {channel} from channel_level_register due to lifetime <= 0")
        # Lösche die Adresse, wenn keine Kanäle mehr vorhanden sind
        if not channel_level_register[address]:
            del channel_level_register[address]

def process_sensor_Data():
    if is_empty(mean_values):
        calculate_means(get_oldest_sensor_data(50))
    means = get_means()
    calculate_SensorData_inMean(means)

@app.route('/', methods =['GET'])
def home():
    """
    Rendert die Hauptseite der Webanwendung.
    Returns:
        str: Gerenderter HTML-Inhalt der Hauptseite.
    """
    config = read_config()
    rows = int(clean_value(config['Web-UI']['amountY-Axis']))
    cols = int(clean_value(config['Web-UI']['amountX-Axis']))
    return render_template('index.html', rows=rows, cols=cols)

@app.route('/sensor_data', methods=['GET'])
def get_sensor_data():
    global isCalibrationRunning

    if isCalibrationRunning:
        response = jsonify(message="Kalibierung läuft")
        response.status_code = 423
        return response
    else:
        process_sensor_Data()
        data = convertDatatoDisplay()
        data['timestamp'] = newestTimestamp
        return jsonify(data)

@app.route('/calibrate', methods=['GET'])
def startCalibration():
    calibrationRoutine()
    return jsonify(message="Kalibrierung gestartet"), 200

@app.route('/calibration_status', methods=['GET'])
def get_calibration_status():
    logging.info(f"Calibration Status: {calibration_status}")
    return jsonify(calibration_status), 200

if __name__ == '__main__':
    config = read_config()
    ip_address = clean_value(config['Local-Settings']['local_client_ip'])
    port = int(clean_value(config['Network']['webapp_port']))
    app.run(host=ip_address, port=port)
