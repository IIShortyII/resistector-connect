import time
import sys
import os
from flask import Flask, jsonify
import threading

sys.path.append(os.path.join(os.path.dirname(__file__), 'ADC'))
from ADC import ADS1263

app = Flask(__name__)

REF = 5.08
channelList = [0, 1, 2, 3, 4, 5, 6, 7, 8]
ADC = None
data = {}

try:
    ADC = ADS1263.ADS1263()
    if ADC.ADS1263_init_ADC1("ADS1263_2d5SPS") == -1:
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

if __name__ == '__main__':
    threading.Thread(target=update_sensor_data, daemon=True).start()
    app.run(host='10.42.0.1', port=5000)
