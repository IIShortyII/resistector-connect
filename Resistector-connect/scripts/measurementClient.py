import time
import sys
import os
import threading
import logging
from typing import List, Dict, Any
from flask import Flask, jsonify
import configparser

# Path to the configuration file and log file
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'Client.log')

# Logging configuration
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE)]
)

#Supress Flask Logging below Error
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Add the path to the ADC module
sys.path.append(os.path.join(os.path.dirname(__file__), 'ADC'))
from ADC import ADS1263


class ConfigLoader:
    """
    A helper class for loading and cleaning configuration values.

    Methods:
        load_config(config_path: str) -> configparser.ConfigParser:
            Loads the configuration from a file.

        clean_value(value: str) -> str:
            Cleans a configuration value by removing comments and extra whitespace.
    """

    @staticmethod
    def load_config(config_path: str) -> configparser.ConfigParser:
        """
        Loads the configuration from the specified file.

        Args:
            config_path (str): Path to the configuration file.

        Returns:
            configparser.ConfigParser: The loaded configuration object.
        """
        config = configparser.ConfigParser()
        config.read(config_path)
        return config

    @staticmethod
    def clean_value(value: str) -> str:
        """
        Cleans a configuration value by removing comments and extra whitespace.

        Args:
            value (str): The value to be cleaned.

        Returns:
            str: The cleaned value.
        """
        return value.split(';')[0].split('#')[0].strip()


class ADCHandler:
    """
    A class for handling the ADC (Analog-to-Digital Converter).

    Attributes:
        channel_list (List[int]): List of channels to scan.
        data (Dict[str, Any]): A dictionary for storing sensor data.

    Methods:
        update_sensor_data():
            Updates the sensor data at regular intervals.

        get_data() -> Dict[str, Any]:
            Returns the current sensor data.
    """

    def __init__(self, scan_frequence: str, channel_list: List[int]):
        """
        Initializes the ADCHandler with the given scan frequency and channel list.

        Args:
            scan_frequence (str): The scan frequency for the ADC.
            channel_list (List[int]): List of channels to scan.
        """
        self.channel_list = channel_list
        self.data = {}
        try:
            self.adc = ADS1263.ADS1263()
            if self.adc.ADS1263_init_ADC1(scan_frequence) == -1:
                logging.critical("Error initializing ADC.")
                sys.exit(1)
            self.adc.ADS1263_SetMode(0)
        except IOError as e:
            logging.critical(f"IOError during ADC initialization: {e}")
            sys.exit(1)
        except Exception as e:
            logging.critical(f"General error during ADC initialization: {e}")
            sys.exit(1)

    def convert_to_float(self, values: List[int]) -> List[float]:
        """
        Converts raw values to floating-point numbers by treating the last 6 digits as decimal places.

        Args:
            values (List[int]): The raw ADC values.

        Returns:
            List[float]: The cleaned values as floating-point numbers.
        """
        return [value / 100000000.0 for value in values]

    def update_sensor_data(self):
        """
        Updates the sensor data at regular intervals and stores it in the `data` dictionary.
        """
        while True:
            try:
                adc_values = self.adc.ADS1263_GetAll(self.channel_list)
                float_values = self.convert_to_float(adc_values)
                logging.debug(f"Converted ADC values: {float_values}")  
                for i, adc_value in enumerate(float_values):
                    self.data[f'Channel {i}'] = adc_value
                time.sleep(1)
            except Exception as e:
                logging.error(f"Error updating sensor data: {e}")

    def get_data(self) -> Dict[str, Any]:
        """
        Returns the current sensor data.

        Returns:
            Dict[str, Any]: A dictionary with the current sensor data.
        """
        return self.data


def create_app(adc_handler: ADCHandler, channel_list: List[int], level: str) -> Flask:
    """
    Creates and configures the Flask application.

    Args:
        adc_handler (ADCHandler): The ADCHandler for handling sensor data.
        channel_list (List[int]): List of channels to scan.
        level (str): The level string for the application.

    Returns:
        Flask: The configured Flask application.
    """
    app = Flask(__name__)

    @app.route('/measure', methods=['GET'])
    def measure():
        """
        Flask route for measurement. Returns the current sensor data.

        Returns:
            Flask.Response: A JSON response with the current sensor data.
        """
        return jsonify(adc_handler.get_data())

    @app.route('/mode', methods=['GET'])
    def mode():
        """
        Flask route for mode. Returns the number of channels and the level.

        Returns:
            Flask.Response: A JSON response with the number of channels and the level.
        """
        return jsonify({
            'channelCount': len(channel_list),
            'level': level
        })

    return app


def main():
    """
    Main function of the application. Loads the configuration, initializes the ADCHandler,
    starts the thread for updating sensor data, and starts the Flask application.
    """
    try:
        config = ConfigLoader.load_config(CONFIG_PATH)

        channel_list = list(map(int, ConfigLoader.clean_value(config['Local-Settings']['channelList']).split(',')))
        level = ConfigLoader.clean_value(config['Local-Settings']['level'])
        scan_frequence = ConfigLoader.clean_value(config['Local-Settings']['scan_frequence'])
        ip_address = ConfigLoader.clean_value(config['Local-Settings']['local_client_ip'])
        port = int(ConfigLoader.clean_value(config['Network']['client_port']))

        logging.info("Initializing ADC...")
        adc_handler = ADCHandler(scan_frequence, channel_list)

        logging.debug("Starting thread for updating sensor data...")
        threading.Thread(target=adc_handler.update_sensor_data, daemon=True).start()

        logging.debug("Starting Flask application...")
        app = create_app(adc_handler, channel_list, level)
        app.run(host=ip_address, port=port)
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
    except KeyboardInterrupt:
        logging.error("Program terminated.")
        sys.exit(0)


if __name__ == '__main__':
    main()
