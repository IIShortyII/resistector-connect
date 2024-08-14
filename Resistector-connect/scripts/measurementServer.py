import os
import time
import json
import requests
import logging
from datetime import datetime
import configparser
from collections import defaultdict, deque
import numpy as np

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
DATA_DIR = 'measurement_data'
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'MeasurementServer.log')

# Logging-Konfiguration
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
    ]
)

logging.info("Measurement server session started")

def read_config(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

def clean_value(value):
    return value.split(';')[0].split('#')[0].strip()

def initialize_directories(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def generate_filename(directory):
    current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
    return os.path.join(directory, f"{current_datetime}_measurementData.json")

def request_data(pis, port, filename):
    for pi in pis:
        try:
            response = requests.get(f'http://{pi}:{port}/measure')
            response.raise_for_status()
            data = response.json()
            filtered_data = filter_data(pi, data)
            save_data(filtered_data, pi, filename)
        except requests.exceptions.RequestException as e:
            logging.error(f"Could not connect to {pi}: {e}")
            save_data("nodata", pi, filename)

def save_data(data, pi, filename):
    timestamp = datetime.now().isoformat()
    formatted_data = {
        'pi-address': pi,
        'sensor_data': data,
        'timestamp': timestamp
    }
    with open(filename, 'a') as file:
        json.dump(formatted_data, file)
        file.write('\n')

def validate_config(config):
    if 'Network' not in config or 'client_ips' not in config['Network'] or 'client_port' not in config['Network']:
        raise ValueError("Invalid configuration: 'Network' section or keys missing")

def apply_ema_filter(data_points, alpha=0.1):
    """
    Wendet den Exponential Moving Average (EMA) Filter auf die Daten an.

    Args:
        data_points (list): Die zu filternden Daten.
        alpha (float): Der Glättungsfaktor. Je kleiner der Wert, desto stärker wird geglättet.

    Returns:
        float: Der gefilterte Wert.
    """
    if not data_points:
        return 0
    ema = data_points[0]
    for point in data_points[1:]:
        ema = alpha * point + (1 - alpha) * ema
    return ema

def apply_threshold_filter(value, previous_value, total_min, total_max, min_threshold, max_threshold):
    """
    Wendet den Schwellwertfilter auf den Wert an.

    Args:
        value (float): Der aktuelle Messwert.
        previous_value (float): Der vorherige gefilterte Wert.
        total_min (float): Das totale Minimum.
        total_max (float): Das totale Maximum.
        min_threshold (float): Das Schwellwertminimum.
        max_threshold (float): Das Schwellwertmaximum.

    Returns:
        float: Der gefilterte Wert.
    """
    
    #ignore too high or too low values
    if value < total_min or value > total_max:
        return previous_value

    delta = value - previous_value
    if delta > max_threshold:
        return previous_value + max_threshold
    if delta < -min_threshold:
        return previous_value - min_threshold
    return value

# Globales Dictionary zum Speichern der letzten Datenpunkte für jede Adresse und jeden Kanal
ema_recent_data = defaultdict(lambda: defaultdict(deque))
thres_recent_data = defaultdict(lambda: defaultdict(deque))

def filter_data(pi, data, alpha=0.1):
    ema_filtered_data = {}
    thres_filtered_data = {}
    
    for channel, value in data.items():
        # Fügt den neuen Wert zu den letzten Datenpunkten hinzu und wendet den EMA-Filter an
        ema_recent_data[pi][channel].append(value)
        ema_filtered_value = apply_ema_filter(list(ema_recent_data[pi][channel]), alpha)
        ema_filtered_data[channel] = ema_filtered_value
        
        # Optional: Größe der Deque beschränken
        if len(ema_recent_data[pi][channel]) > 10:
            ema_recent_data[pi][channel].popleft()

        # Wenn die Pi-Adresse in den speziellen Adressen enthalten ist, Threshold-Filter anwenden
        if pi in ["10.42.0.1"]:
            previous_value = thres_recent_data[pi][channel][-1] if thres_recent_data[pi][channel] else ema_filtered_value
            thres_filtered_value = apply_threshold_filter(ema_filtered_value, previous_value, 8, 17, 0.3, 0.3)
            thres_filtered_data[channel] = thres_filtered_value

        if pi in ["10.42.0.2"]:
            previous_value = thres_recent_data[pi][channel][-1] if thres_recent_data[pi][channel] else ema_filtered_value
            thres_filtered_value = apply_threshold_filter(ema_filtered_value, previous_value, 10, 22, 0.3, 0.3)
            thres_filtered_data[channel] = thres_filtered_value

        if pi in ["10.42.0.3"]:
            previous_value = thres_recent_data[pi][channel][-1] if thres_recent_data[pi][channel] else ema_filtered_value
            thres_filtered_value = apply_threshold_filter(ema_filtered_value, previous_value, 8, 17, 0.3, 0.3)
            thres_filtered_data[channel] = thres_filtered_value


            # Gefilterten Wert zur Deque hinzufügen
            thres_recent_data[pi][channel].append(thres_filtered_value)
            if len(thres_recent_data[pi][channel]) > 10:
                thres_recent_data[pi][channel].popleft()

    # Wenn ein Threshold-Filter angewendet wurde, diese gefilterten Daten zurückgeben, sonst die EMA-gefilterten Daten
    if thres_filtered_data:
        return thres_filtered_data
    else:
        return ema_filtered_data


def main():
    config = read_config(CONFIG_PATH)
    validate_config(config)
    
    pis = list(map(clean_value, config['Network']['client_ips'].split(',')))
    port = clean_value(config['Network']['client_port'])

    initialize_directories(DATA_DIR)
    filename = generate_filename(DATA_DIR)

    try:
        while True:
            request_data(pis, port, filename)
            time.sleep(0.8)
    except KeyboardInterrupt:
        logging.info("Measurement server stopped by user")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
