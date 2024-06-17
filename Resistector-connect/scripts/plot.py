import json
import pandas as pd
import matplotlib.pyplot as plt
import glob
import os
from matplotlib.animation import FuncAnimation

def load_latest_data(folder_path, last_timestamp=None):
    json_files = glob.glob(os.path.join(folder_path, '*_measurementData.json'))
    
    if not json_files:
        print("Keine JSON-Dateien im Ordner gefunden.")
        return []

    sorted_files = sorted(json_files, key=os.path.getmtime, reverse=True)
    latest_file = sorted_files[0]
    
    data = []
    with open(latest_file, 'r') as file:
        for line in file:
            try:
                record = json.loads(line)
                if last_timestamp is None or record['timestamp'] > last_timestamp:
                    data.append(record)
            except json.JSONDecodeError as e:
                print(f"Fehler beim Laden der JSON-Daten aus Zeile: {e}")
    
    return data

def plot_data(axs, data):
    if not data:
        print("Keine Daten vorhanden.")
        return []

    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    unique_addresses = df['pi-address'].unique()

    lines = []

    for ax in axs:
        ax.clear()
        ax.set_ylim(0, 2200)

    for i, pi_address in enumerate(unique_addresses):
        df_pi = df[df['pi-address'] == pi_address]
        axs[i].set_title(f'Daten für Pi-Adresse: {pi_address}')
        axs[i].set_ylabel('Wert')

        for channel in df_pi['sensor_data'].iloc[0].keys():
            values = [entry[channel] for entry in df_pi['sensor_data']]
            timestamps = df_pi['timestamp'].values
            line, = axs[i].plot(timestamps, values, label=channel)
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

        for channel in df_pi['sensor_data'].iloc[0].keys():
            values = [entry[channel] for entry in df_pi['sensor_data']]
            timestamps = df_pi['timestamp'].values
            lines[line_index].set_data(timestamps, values)
            line_index += 1

    for ax in axs:
        ax.relim()
        ax.autoscale_view()

    plt.tight_layout()
    return last_timestamp

if __name__ == "__main__":
    folder_path = 'measurement_data'
    
    fig, axs = plt.subplots(3, 1, figsize=(10, 18), sharex=True)
    last_timestamp = None
    initial_data = load_latest_data(folder_path, last_timestamp)
    lines = plot_data(axs, initial_data)
    last_timestamp = initial_data[-1]['timestamp'] if initial_data else None
    
    ani = FuncAnimation(fig, update_plot, fargs=(folder_path, axs, lines, last_timestamp), interval=500)
    plt.show()
