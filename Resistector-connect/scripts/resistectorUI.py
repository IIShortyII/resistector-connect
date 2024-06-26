import os
import configparser
from flask import Flask, render_template


def read_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)
    return config


def clean_value(value):
    return value.split(';')[0].split('#')[0].strip()


def create_app():
    app = Flask(__name__)

    @app.route('/')
    def index():
        rows = 6
        cols = 10
        return render_template('index.html', rows=rows, cols=cols)

    return app


if __name__ == '__main__':
    config = read_config()
    ip_address = clean_value(config['Local-Settings']['local_client_ip'])
    port = int(clean_value(config['Network']['webapp_port']))

    app = create_app()
    app.run(host=ip_address, port=port)
