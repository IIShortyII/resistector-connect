import time
import sys
import os
import threading
from flask import Flask, jsonify
import configparser

sys.path.append(os.path.join(os.path.dirname(__file__), 'ADC'))
from ADC import ADS1263

config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
config = configparser.ConfigParser()
config.read(config_path)

def clean_value(value):
    return value.split(';')[0].split('#')[0].strip()

# Clean the channel list string and then split into a list of integers
channelList = list(map(int, clean_value(config['Local-Settings']['channelList']).split(',')))
level = clean_value(config['Local-Settings']['level'])
scan_frequence = clean_value(config['Local-Settings']['scan_frequence'])
ip_address = clean_value(config['Local-Settings']['local_client_ip'])
port = int(clean_value(config['Network']['client_port']))

app = Flask(__name__)

ADC = None
data = {}

try:
    ADC = ADS1263.ADS1263()
    if ADC.ADS1263_init_ADC1(scan_frequence) == -1:
        exit()
    ADC.ADS1263_SetMode(0)
except IOError as e:
    print(e)
except KeyboardInterrupt:
    print("Programm beendet.")
    exit()

def update_sensor_data():
    global data
    while True:
        ADC_Value = ADC.ADS1263_GetAll(channelList)
        for i, adc_value in enumerate(ADC_Value):
            data[f'Kanal {i}'] = int(str(adc_value)[:-6])
        time.sleep(1)

@app.route('/measure', methods=['GET'])
def measure():
    return jsonify(data)

@app.route('/modus', methods=['GET'])
def modus():
    return jsonify({
        'channelCount': len(channelList),
        'level': level
    })

if __name__ == '__main__':
    threading.Thread(target=update_sensor_data, daemon=True).start()
    app.run(host=ip_address, port=port)
