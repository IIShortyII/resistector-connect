import requests
import json
from datetime import datetime
import os
import time
import configparser

config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
config = configparser.ConfigParser()
config.read(config_path)

def clean_value(value):
    return value.split(';')[0].split('#')[0].strip()

pis = list(map(clean_value, config['Network']['client_ips'].split(',')))
port = clean_value(config['Network']['client_port'])

if not os.path.exists('measurement_data'):
    os.makedirs('measurement_data')

current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
filename = f"measurement_data/{current_datetime}_measurementData.json"

def request_data():
    for pi in pis:
        try:
            response = requests.get(f'http://{pi}:{port}/measure')
            if response.status_code == 200:
                data = response.json()
                save_data(data, pi)
            else:
                print(f"Error from {pi}: {response.status_code}")
        except Exception as e:
            print(f"Could not connect to {pi}")
            data = "nodata"
            save_data(data, pi)

def save_data(data, pi):
    timestamp = datetime.now().isoformat()
    formatted_data = {
        'pi-address': pi,
        'sensor_data': data,
        'timestamp': timestamp
    }
    with open(filename, 'a') as file:
        json.dump(formatted_data, file)
        file.write('\n')
    print(f"Data from {pi} saved: {formatted_data}")

if __name__ == '__main__':
    while True:
        request_data()
        time.sleep(1)
