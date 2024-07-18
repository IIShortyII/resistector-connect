import time
import sys
import os
import threading
import logging
from typing import List, Dict, Any
from flask import Flask, jsonify
import configparser

# Pfad zur Konfigurationsdatei und Logdatei
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'Client.log')

# Logging-Konfiguration
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE)]
)

# Pfad zum ADC-Modul hinzufügen
sys.path.append(os.path.join(os.path.dirname(__file__), 'ADC'))
from ADC import ADS1263


class ConfigLoader:
    """
    Eine Hilfsklasse zum Laden und Bereinigen von Konfigurationswerten.

    Methoden:
        load_config(config_path: str) -> configparser.ConfigParser:
            Lädt die Konfiguration aus einer Datei.

        clean_value(value: str) -> str:
            Bereinigt einen Konfigurationswert, indem Kommentare und überflüssige Leerzeichen entfernt werden.
    """

    @staticmethod
    def load_config(config_path: str) -> configparser.ConfigParser:
        """
        Lädt die Konfiguration aus der angegebenen Datei.

        Args:
            config_path (str): Pfad zur Konfigurationsdatei.

        Returns:
            configparser.ConfigParser: Das geladene Konfigurationsobjekt.
        """
        config = configparser.ConfigParser()
        config.read(config_path)
        return config

    @staticmethod
    def clean_value(value: str) -> str:
        """
        Bereinigt einen Konfigurationswert, indem Kommentare und überflüssige Leerzeichen entfernt werden.

        Args:
            value (str): Der zu bereinigende Wert.

        Returns:
            str: Der bereinigte Wert.
        """
        return value.split(';')[0].split('#')[0].strip()


class ADCHandler:
    """
    Eine Klasse zur Handhabung des ADC (Analog-Digital-Converter).

    Attribute:
        channel_list (List[int]): Liste der zu scannenden Kanäle.
        data (Dict[str, Any]): Ein Dictionary zur Speicherung der Sensordaten.

    Methoden:
        update_sensor_data():
            Aktualisiert die Sensordaten in regelmäßigen Abständen.

        get_data() -> Dict[str, Any]:
            Gibt die aktuellen Sensordaten zurück.
    """

    def __init__(self, scan_frequence: str, channel_list: List[int]):
        """
        Initialisiert den ADCHandler mit der angegebenen Scan-Frequenz und Kanal-Liste.

        Args:
            scan_frequence (str): Die Scan-Frequenz für den ADC.
            channel_list (List[int]): Liste der zu scannenden Kanäle.
        """
        self.channel_list = channel_list
        self.data = {}
        try:
            self.adc = ADS1263.ADS1263()
            if self.adc.ADS1263_init_ADC1(scan_frequence) == -1:
                logging.critical("Fehler bei der Initialisierung des ADC.")
                sys.exit(1)
            self.adc.ADS1263_SetMode(0)
        except IOError as e:
            logging.critical(f"IOError bei der ADC-Initialisierung: {e}")
            sys.exit(1)
        except Exception as e:
            logging.critical(f"Allgemeiner Fehler bei der ADC-Initialisierung: {e}")
            sys.exit(1)

    def update_sensor_data(self):
        """
        Aktualisiert die Sensordaten in regelmäßigen Abständen und speichert sie im `data` Dictionary.
        """
        while True:
            try:
                adc_values = self.adc.ADS1263_GetAll(self.channel_list)
                for i, adc_value in enumerate(adc_values):
                    self.data[f'Kanal {i}'] = int(str(adc_value)[:-6])
                time.sleep(1)
            except Exception as e:
                logging.error(f"Fehler beim Aktualisieren der Sensordaten: {e}")

    def get_data(self) -> Dict[str, Any]:
        """
        Gibt die aktuellen Sensordaten zurück.

        Returns:
            Dict[str, Any]: Ein Dictionary mit den aktuellen Sensordaten.
        """
        return self.data


def create_app(adc_handler: ADCHandler, channel_list: List[int], level: str) -> Flask:
    """
    Erstellt und konfiguriert die Flask-Anwendung.

    Args:
        adc_handler (ADCHandler): Der ADCHandler zur Handhabung der Sensordaten.
        channel_list (List[int]): Liste der zu scannenden Kanäle.
        level (str): Der Level-String für die Anwendung.

    Returns:
        Flask: Die konfigurierte Flask-Anwendung.
    """
    app = Flask(__name__)

    @app.route('/measure', methods=['GET'])
    def measure():
        """
        Flask-Route für die Messung. Gibt die aktuellen Sensordaten zurück.

        Returns:
            Flask.Response: Eine JSON-Antwort mit den aktuellen Sensordaten.
        """
        return jsonify(adc_handler.get_data())

    @app.route('/modus', methods=['GET'])
    def modus():
        """
        Flask-Route für den Modus. Gibt die Anzahl der Kanäle und das Level zurück.

        Returns:
            Flask.Response: Eine JSON-Antwort mit der Anzahl der Kanäle und dem Level.
        """
        return jsonify({
            'channelCount': len(channel_list),
            'level': level
        })

    return app


def main():
    """
    Hauptfunktion der Anwendung. Lädt die Konfiguration, initialisiert den ADCHandler,
    startet den Thread zur Aktualisierung der Sensordaten und die Flask-Anwendung.
    """
    try:
        config = ConfigLoader.load_config(CONFIG_PATH)

        channel_list = list(map(int, ConfigLoader.clean_value(config['Local-Settings']['channelList']).split(',')))
        level = ConfigLoader.clean_value(config['Local-Settings']['level'])
        scan_frequence = ConfigLoader.clean_value(config['Local-Settings']['scan_frequence'])
        ip_address = ConfigLoader.clean_value(config['Local-Settings']['local_client_ip'])
        port = int(ConfigLoader.clean_value(config['Network']['client_port']))

        logging.info("Initialisierung des ADC...")
        adc_handler = ADCHandler(scan_frequence, channel_list)

        logging.info("Starten des Threads zur Aktualisierung der Sensordaten...")
        threading.Thread(target=adc_handler.update_sensor_data, daemon=True).start()

        logging.info("Starten der Flask-Anwendung...")
        app = create_app(adc_handler, channel_list, level)
        app.run(host=ip_address, port=port)
    except Exception as e:
        logging.critical(f"Unbehandelte Ausnahme: {e}", exc_info=True)
    except KeyboardInterrupt:
        logging.info("Programm beendet.")
        sys.exit(0)


if __name__ == '__main__':
    main()
