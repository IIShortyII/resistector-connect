import os
import json
import logging
import configparser
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_cors import CORS
from collections import defaultdict
import numpy as np

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

# Variable für die Anzahl der Messungen zur Baseline-Berechnung
AmountMeasurementForBaseline = 50
meanThreshold = 150
baseline_logged = False

def read_config():
    """
    Liest die Konfigurationsdatei und gibt das Konfigurationsobjekt zurück.
    Returns:
        configparser.ConfigParser: Das geladene Konfigurationsobjekt.
    """
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config

def clean_value(value):
    """
    Bereinigt einen Konfigurationswert, indem Kommentare und überflüssige Leerzeichen entfernt werden.
    Args:
        value (str): Der zu bereinigende Wert.
    Returns:
        str: Der bereinigte Wert.
    """
    return value.split(';')[0].split('#')[0].strip()

def get_pi_addresses(config):
    """
    Extrahiert die IP-Adressen der Raspberry Pis aus der Konfiguration.
    Args:
        config (configparser.ConfigParser): Das Konfigurationsobjekt.
    Returns:
        list: Liste der IP-Adressen.
    """
    raw_addresses = config['Network']['client_ips']
    return [clean_value(addr) for addr in raw_addresses.split(',')]

def get_latest_file():
    """
    Ermittelt die neueste Messdatendatei im Datenverzeichnis.
    Returns:
        str: Der Pfad zur neuesten Messdatendatei.
    Raises:
        FileNotFoundError: Wenn keine Messdatendateien gefunden werden.
    """
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('_measurementData.json')]
    if not files:
        logging.error(f"No measurement data files found in: {DATA_DIR}")
        raise FileNotFoundError(f"No measurement data files found in: {DATA_DIR}")
    latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(DATA_DIR, f)))
    return os.path.join(DATA_DIR, latest_file)

def read_sensor_data():
    """
    Liest die Sensordaten aus der neuesten Messdatendatei.
    Returns:
        list: Liste der Sensordaten.
    """
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

def calculate_baselines(sensor_data):
    """
    Berechnet die Baseline für jeden Kanal und jede Adresse aus den ersten AmountMeasurementForBaseline Messungen.
    Args:
        sensor_data (list): Die zu verarbeitenden Sensordaten.
    Returns:
        dict: Ein Dictionary mit Baselines für jede Adresse und jeden Kanal.
    """
    global baseline_logged
    baselines = defaultdict(lambda: defaultdict(list))
    
    # Sammeln der ersten AmountMeasurementForBaseline Messungen für jede Adresse und jeden Kanal
    for data in sensor_data:
        pi_address = data["pi-address"]
        sensor_values = data["sensor_data"]
        
        if len(baselines[pi_address]['Kanal 0']) < AmountMeasurementForBaseline:
            for channel, value in sensor_values.items():
                baselines[pi_address][channel].append(value)
        
        # Stoppen, wenn genügend Messungen vorliegen
        if all(len(baselines[pi_address][channel]) >= AmountMeasurementForBaseline for channel in sensor_values.keys()):
            break

    # Durchschnittswerte für die Baseline berechnen
    baseline_values = {}
    for pi_address, channels in baselines.items():
        baseline_values[pi_address] = {channel: np.mean(values) - meanThreshold for channel, values in channels.items()}

    # Baseline-Werte in den Logs ausgeben, wenn noch nicht geloggt
    if not baseline_logged:
        for pi_address, channels in baseline_values.items():
            logging.info(f"Baseline for {pi_address}:")
            for channel, baseline in channels.items():
                logging.info(f"  {channel}: {baseline:.2f}")
        baseline_logged = True

    return baseline_values

def process_sensor_data(sensor_data, pi_addresses, baselines):
    """
    Verarbeitet die Sensordaten und erstellt eine Liste von Zuständen für das Web-UI.
    Args:
        sensor_data (list): Die zu verarbeitenden Sensordaten.
        pi_addresses (list): Liste der IP-Adressen der Raspberry Pis.
        baselines (dict): Baseline-Werte für jeden Kanal und jede Adresse.
    Returns:
        tuple: Ein Tuple mit der Liste der verarbeiteten Daten und den neuesten Zeitstempeln.
    """
    config = read_config()
    threshold_value = 2000
    max_x_coord = int(clean_value(config['Web-UI']['amountX-Axis']))
    max_y_coord = int(clean_value(config['Web-UI']['amountY-Axis']))

    pi_data = {pi: {} for pi in pi_addresses}
    latest_timestamps = {pi: "" for pi in pi_addresses}

    for data in sensor_data:
        pi_address = data["pi-address"]
        sensor_data = data["sensor_data"]
        timestamp = data["timestamp"]
        pi_data[pi_address] = sensor_data
        latest_timestamps[pi_address] = timestamp

    result = []

    for x_channel, x_value in pi_data[pi_addresses[0]].items():
        for y_channel, y_value in pi_data[pi_addresses[1]].items():
            x_coord = int(x_channel.split()[1])
            y_coord = int(y_channel.split()[1])

            if x_coord > max_x_coord or y_coord > max_y_coord:
                continue

            state = "O"
            x_baseline = baselines[pi_addresses[0]].get(x_channel, threshold_value)
            y_baseline = baselines[pi_addresses[1]].get(y_channel, threshold_value)
            
            if x_value < x_baseline and y_value < y_baseline:
                state = "X"
                if f"Kanal {y_coord}" in pi_data[pi_addresses[2]]:
                    y_additional_value = pi_data[pi_addresses[2]].get(f"Kanal {y_coord}", threshold_value)
                    y_additional_baseline = baselines[pi_addresses[2]].get(f"Kanal {y_coord}", threshold_value)
                    if y_additional_value < y_additional_baseline:
                        state = "XX"
            result.append({"x": x_coord, "y": y_coord, "state": state})

    return result, latest_timestamps

@app.route('/')
def index():
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
def sensor_data():
    """
    Liefert die verarbeiteten Sensordaten als JSON.
    Returns:
        Response: JSON-Antwort mit den Sensordaten und Zeitstempeln.
    """
    try:
        config = read_config()
        pi_addresses = get_pi_addresses(config)
        data = read_sensor_data()
        baselines = calculate_baselines(data)
        processed_data, latest_timestamps = process_sensor_data(data, pi_addresses, baselines)
        return jsonify({"data": processed_data, "timestamps": latest_timestamps})
    except Exception as e:
        logging.error(f"Error processing sensor data: {e}", exc_info=True)
        return jsonify({"error": "Error processing sensor data"}), 500

if __name__ == '__main__':
    try:
        config = read_config()
        ip_address = clean_value(config['Local-Settings']['local_client_ip'])
        port = int(clean_value(config['Network']['webapp_port']))
        app.run(host=ip_address, port=port)
    except KeyError as e:
        logging.critical(f"Missing configuration: {e}", exc_info=True)
        exit(1)
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
        exit(1)
