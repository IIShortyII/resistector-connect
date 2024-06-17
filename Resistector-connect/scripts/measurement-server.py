import requests
import json
from datetime import datetime
import os
import time

pis = ['10.42.0.1', '10.42.0.2', '10.42.0.3']

if not os.path.exists('measurement_data'):
    os.makedirs('measurement_data')

current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
filename = f"measurement_data/{current_datetime}_measurementData.json"

def request_data():
    for pi in pis:
        try:
            response = requests.get(f'http://{pi}:5000/measure')
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
