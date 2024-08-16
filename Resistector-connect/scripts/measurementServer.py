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

# Logging configuration
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
    """
    Reads the configuration file.

    Args:
        config_path (str): Path to the configuration file.

    Returns:
        configparser.ConfigParser: The loaded configuration object.
    """
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

def clean_value(value):
    """
    Cleans a configuration value by removing comments and extra whitespace.

    Args:
        value (str): The value to be cleaned.

    Returns:
        str: The cleaned value.
    """
    return value.split(';')[0].split('#')[0].strip()

def initialize_directories(directory):
    """
    Creates the specified directory if it does not exist.

    Args:
        directory (str): The directory to create.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)

def generate_filename(directory, suffix):
    """
    Generates a filename for storing measurement data, including a timestamp.

    Args:
        directory (str): The directory where the file will be saved.

    Returns:
        str: The generated filename.
    """
    current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
    return os.path.join(directory, f"{current_datetime}_{suffix}.json")

def request_data(pis, port, filename, raw_filename):
    """
    Requests measurement data from the specified Raspberry Pi devices and saves it to a file.

    Args:
        pis (list): List of Raspberry Pi addresses.
        port (str): The port number to use for the requests.
        filename (str): The file where the data will be saved.
    """
    for pi in pis:
        try:
            response = requests.get(f'http://{pi}:{port}/measure')
            response.raise_for_status()
            data = response.json()
            save_data(data, pi, raw_filename)

            filtered_data = filter_data(pi, data)
            save_data(filtered_data, pi, filename)
        except requests.exceptions.RequestException as e:
            logging.error(f"Could not connect to {pi}: {e}")
            save_data("nodata", pi, filename)

def save_data(data, pi, filename):
    """
    Saves the measurement data to a file with a timestamp.

    Args:
        data (dict): The data to save.
        pi (str): The Raspberry Pi address.
        filename (str): The file where the data will be saved.
    """
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
    """
    Validates the configuration object to ensure required sections and keys are present.

    Args:
        config (configparser.ConfigParser): The configuration object.

    Raises:
        ValueError: If required sections or keys are missing.
    """
    if 'Network' not in config or 'client_ips' not in config['Network'] or 'client_port' not in config['Network']:
        raise ValueError("Invalid configuration: 'Network' section or keys missing")

def apply_ema_filter(data_points, alpha=0.1):
    """
    Applies the Exponential Moving Average (EMA) filter to the data.

    Args:
        data_points (list): The data points to filter.
        alpha (float): The smoothing factor. A smaller value means stronger smoothing.

    Returns:
        float: The filtered value.
    """
    if not data_points:
        return 0
    ema = data_points[0]
    for point in data_points[1:]:
        ema = alpha * point + (1 - alpha) * ema
    return ema

def apply_threshold_filter(value, previous_value, total_min, total_max, min_threshold, max_threshold):
    """
    Applies a threshold filter to the value.

    Args:
        value (float): The current measurement value.
        previous_value (float): The previous filtered value.
        total_min (float): The total minimum.
        total_max (float): The total maximum.
        min_threshold (float): The minimum threshold.
        max_threshold (float): The maximum threshold.

    Returns:
        float: The filtered value.
    """
    # Ignore values that are too high or too low
    if value < total_min or value > total_max:
        return previous_value

    delta = value - previous_value
    if delta > max_threshold:
        return previous_value + max_threshold
    if delta < -min_threshold:
        return previous_value - min_threshold
    return value

# Global dictionary to store recent data points for each address and channel
ema_recent_data = defaultdict(lambda: defaultdict(deque))
thres_recent_data = defaultdict(lambda: defaultdict(deque))

def filter_data(pi, data, alpha=0.1):
    """
    Filters the measurement data using EMA and threshold filters.

    Args:
        pi (str): The Raspberry Pi address.
        data (dict): The raw measurement data.
        alpha (float): The smoothing factor for the EMA filter.

    Returns:
        dict: The filtered data.
    """
    ema_filtered_data = {}
    thres_filtered_data = {}
    
    for channel, value in data.items():
        # Add the new value to the recent data points and apply the EMA filter
        ema_recent_data[pi][channel].append(value)
        ema_filtered_value = apply_ema_filter(list(ema_recent_data[pi][channel]), alpha)
        ema_filtered_data[channel] = ema_filtered_value
        
        # Optionally limit the size of the deque
        if len(ema_recent_data[pi][channel]) > 10:
            ema_recent_data[pi][channel].popleft()

        # Apply the threshold filter if the Pi address is in the special addresses
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
            thres_filtered_value = apply_threshold_filter(ema_filtered_value, previous_value, 10, 22, 0.3, 0.3)
            thres_filtered_data[channel] = thres_filtered_value

            # Add the filtered value to the deque
            thres_recent_data[pi][channel].append(thres_filtered_value)
            if len(thres_recent_data[pi][channel]) > 10:
                thres_recent_data[pi][channel].popleft()
   
    # Return threshold-filtered data if applied, otherwise return EMA-filtered data
    if thres_filtered_data:
        return thres_filtered_data
    else:
        return ema_filtered_data

def main():
    """
    Main function of the application. Reads the configuration, initializes directories,
    and periodically requests data from the Raspberry Pi devices.
    """
    config = read_config(CONFIG_PATH)
    validate_config(config)
    
    pis = list(map(clean_value, config['Network']['client_ips'].split(',')))
    port = clean_value(config['Network']['client_port'])

    initialize_directories(DATA_DIR)
    filename = generate_filename(DATA_DIR, "measurementData")
    raw_filename = generate_filename(DATA_DIR, "rawData")

    try:
        while True:
            request_data(pis, port, filename, raw_filename)
            time.sleep(0.8)
    except KeyboardInterrupt:
        logging.info("Measurement server stopped by user")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
