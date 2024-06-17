# save this as app.py
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/measure', methods=['GET'])
def measure():
    # Hier wird die Messung durchgeführt, ersetze die Dummy-Daten durch echte Messdaten
    data = {
        #'timestamp': datetime.now().isoformat(),
        'sensor1': 23.4,  # Beispielwert, ersetze durch echten Messwert
        'sensor2': 45.6   # Beispielwert, ersetze durch echten Messwert
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='10.42.0.1', port=5000)
