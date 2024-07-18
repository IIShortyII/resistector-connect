import os
import time
import json
import requests
import logging
from datetime import datetime
import configparser


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
    """
    Liest die Konfiguration aus der angegebenen Datei.

    Args:
        config_path (str): Pfad zur Konfigurationsdatei.

    Returns:
        configparser.ConfigParser: Das geladene Konfigurationsobjekt.
    """
    config = configparser.ConfigParser()
    config.read(config_path)
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

def initialize_directories(directory):
    """
    Initialisiert ein Verzeichnis, falls es nicht existiert.

    Args:
        directory (str): Der Pfad des zu initialisierenden Verzeichnisses.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)

def generate_filename(directory):
    """
    Generiert einen Dateinamen basierend auf dem aktuellen Datum und der Uhrzeit.

    Args:
        directory (str): Das Verzeichnis, in dem die Datei gespeichert wird.

    Returns:
        str: Der generierte Dateiname mit Pfad.
    """
    current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
    return os.path.join(directory, f"{current_datetime}_measurementData.json")

def request_data(pis, port, filename):
    """
    Fordert Sensordaten von den angegebenen Raspberry Pis an und speichert diese.

    Args:
        pis (list): Liste der IP-Adressen der Raspberry Pis.
        port (str): Der Port, auf dem die Raspberry Pis auf Anfragen hören.
        filename (str): Der Dateiname, in dem die Sensordaten gespeichert werden.
    """
    for pi in pis:
        try:
            response = requests.get(f'http://{pi}:{port}/measure')
            response.raise_for_status()
            data = response.json()
            save_data(data, pi, filename)
        except requests.exceptions.RequestException as e:
            logging.error(f"Could not connect to {pi}: {e}")
            save_data("nodata", pi, filename)

def save_data(data, pi, filename):
    """
    Speichert die Sensordaten in einer JSON-Datei.

    Args:
        data (dict or str): Die Sensordaten oder ein Fehlerstring.
        pi (str): Die IP-Adresse des Raspberry Pi, von dem die Daten stammen.
        filename (str): Der Dateiname, in dem die Daten gespeichert werden.
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
    Validiert die Konfiguration, um sicherzustellen, dass notwendige Einstellungen vorhanden sind.

    Args:
        config (configparser.ConfigParser): Das zu validierende Konfigurationsobjekt.

    Raises:
        ValueError: Wenn die Konfiguration ungültig ist.
    """
    if 'Network' not in config or 'client_ips' not in config['Network'] or 'client_port' not in config['Network']:
        raise ValueError("Invalid configuration: 'Network' section or keys missing")

def main():
    """
    Hauptfunktion der Anwendung. Liest die Konfiguration, validiert sie, initialisiert Verzeichnisse,
    generiert Dateinamen und fordert kontinuierlich Sensordaten an.
    """
    config = read_config(CONFIG_PATH)
    validate_config(config)
    
    pis = list(map(clean_value, config['Network']['client_ips'].split(',')))
    port = clean_value(config['Network']['client_port'])

    initialize_directories(DATA_DIR)
    filename = generate_filename(DATA_DIR)

    try:
        while True:
            request_data(pis, port, filename)
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Measurement server stopped by user")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
