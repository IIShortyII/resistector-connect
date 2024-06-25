from flask import Flask, render_template
import os
import configparser

config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
config = configparser.ConfigParser()
config.read(config_path)

def clean_value(value):
    return value.split(';')[0].split('#')[0].strip()

ip_address = clean_value(config['Local-Settings']['local_client_ip'])
port = clean_value(config['Network']['webapp_port'])


app = Flask(__name__)

@app.route('/')
def index():
    rows = 6
    cols = 10
    return render_template('index.html', rows=rows, cols=cols)

if __name__ == '__main__':
    app.run(host=ip_address, port=port)
