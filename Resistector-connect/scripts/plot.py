import json
import pandas as pd
import matplotlib.pyplot as plt
import glob
import os
import logging
import numpy as np
from matplotlib.animation import FuncAnimation
from datetime import datetime

# Konfigurationsparameter
CONFIG = {
    'data_dir': 'measurement_data',
    'log_dir': os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs'),
    'log_file': 'plot.log',
    'plot_interval': 1,
    'figsize': (10, 18),
    'num_subplots': 3,
    'y_max': 22,
    'y_min': 12,
    'default_value': 30,  # Standardwert für fehlende Sensordaten
    'line_colors': ['#377eb8', '#e41a1c', '#4daf4a', '#984ea3', '#a65628', '#f781bf', '#ff7f00', '#00CED1'],  # Farben
    'line_styles': ['-', '--', ':', '-.', 'solid', 'dashed', 'dashdot', 'dotted']  # Linienstile
}

# Logging-Konfiguration
LOG_PATH = os.path.join(CONFIG['log_dir'], CONFIG['log_file'])
if not os.path.exists(CONFIG['log_dir']):
    os.makedirs(CONFIG['log_dir'])

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_PATH)]
)

def load_latest_data(folder_path, last_timestamp=None):
    json_files = glob.glob(os.path.join(folder_path, '*_measurementData.json'))
    
    if not json_files:
        logging.info("Keine JSON-Dateien im Ordner gefunden.")
        return []

    sorted_files = sorted(json_files, key=os.path.getmtime, reverse=True)
    latest_file = sorted_files[0]
    
    data = []
    with open(latest_file, 'r') as file:
        for line in file:
            try:
                record = json.loads(line)
                if last_timestamp is None or record['timestamp'] > last_timestamp:
                    if not record['sensor_data']:
                        record['sensor_data'] = {'default_channel': CONFIG['default_value']}
                    data.append(record)
            except json.JSONDecodeError as e:
                logging.error(f"Fehler beim Laden der JSON-Daten aus Zeile: {e}")
    
    return data

def plot_data(axs, data):
    if not data:
        logging.info("Keine Daten vorhanden.")
        return []

    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    unique_addresses = df['pi-address'].unique()
    lines = []

    for ax in axs:
        ax.clear()
        ax.set_ylim(CONFIG['y_min'], CONFIG['y_max'])

    for i, pi_address in enumerate(unique_addresses):
        df_pi = df[df['pi-address'] == pi_address]
        axs[i].set_title(f'Daten für Pi-Adresse: {pi_address}')
        axs[i].set_ylabel('Wert')

        sensor_data_keys = df_pi['sensor_data'].apply(lambda x: x.keys() if isinstance(x, dict) else {}).explode().unique()
        for j, channel in enumerate(sensor_data_keys):
            values = df_pi['sensor_data'].apply(lambda x: x.get(channel, CONFIG['default_value']) if isinstance(x, dict) else CONFIG['default_value']).to_numpy()
            timestamps = df_pi['timestamp'].to_numpy()
            color = CONFIG['line_colors'][j % len(CONFIG['line_colors'])]
            style = CONFIG['line_styles'][j % len(CONFIG['line_styles'])]
            line, = axs[i].plot(timestamps, values, label=channel, color=color, linestyle=style)
            lines.append(line)

        axs[i].legend(loc='upper left')
        axs[i].grid(True)

    axs[-1].set_xlabel('Zeitstempel')
    plt.tight_layout()
    
    return lines

def update_plot(frame, folder_path, axs, lines, last_timestamp):
    new_data = load_latest_data(folder_path, last_timestamp)
    if not new_data:
        return last_timestamp

    last_timestamp = new_data[-1]['timestamp']
    df = pd.DataFrame(new_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    unique_addresses = df['pi-address'].unique()
    line_index = 0

    for i, pi_address in enumerate(unique_addresses):
        df_pi = df[df['pi-address'] == pi_address]

        sensor_data_keys = df_pi['sensor_data'].apply(lambda x: x.keys() if isinstance(x, dict) else {}).explode().unique()
        for channel in sensor_data_keys:
            values = df_pi['sensor_data'].apply(lambda x: x.get(channel, CONFIG['default_value']) if isinstance(x, dict) else CONFIG['default_value']).to_numpy()
            timestamps = df_pi['timestamp'].to_numpy()
            lines[line_index].set_data(timestamps, values)
            line_index += 1

    for ax in axs:
        ax.relim()
        ax.autoscale_view()

    plt.tight_layout()
    return last_timestamp

def main():
    folder_path = CONFIG['data_dir']
    
    fig, axs = plt.subplots(CONFIG['num_subplots'], 1, figsize=CONFIG['figsize'], sharex=True)
    last_timestamp = None
    initial_data = load_latest_data(folder_path, last_timestamp)
    lines = plot_data(axs, initial_data)
    last_timestamp = initial_data[-1]['timestamp'] if initial_data else None
    
    ani = FuncAnimation(fig, update_plot, fargs=(folder_path, axs, lines, last_timestamp), interval=CONFIG['plot_interval'])
    logging.info("Plotting session started")
    plt.show()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
