import json
import pandas as pd
import matplotlib.pyplot as plt
import glob
import os
import time

def load_latest_data(folder_path):
    # Suche alle JSON-Dateien im Ordner
    json_files = glob.glob(os.path.join(folder_path, '*_measurementData.json'))
    
    # Sortiere die Dateien nach dem Datum im Dateinamen
    sorted_files = sorted(json_files, key=os.path.getmtime, reverse=True)
    
    # Lade die neueste JSON-Datei
    latest_file = sorted_files[0]
    
    data_list = []
    
    with open(latest_file, 'r') as file:
        for line in file:
            try:
                data = json.loads(line.strip())
                data_list.append(data)
            except json.JSONDecodeError as e:
                print(f"Fehler beim Parsen der Zeile: {e}")
    
    return data_list

def plot_data(data):
    if not data:
        print("Keine Daten vorhanden.")
        return
    
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    unique_addresses = df['pi-address'].unique()

    fig, axs = plt.subplots(len(unique_addresses), 1, figsize=(10, 6*len(unique_addresses)), sharex=True)

    for i, pi_address in enumerate(unique_addresses):
        df_pi = df[df['pi-address'] == pi_address]
        axs[i].set_title(f'Data for Pi Address: {pi_address}')
        axs[i].set_ylabel('Value')
        
        for channel in df_pi['sensor_data'].iloc[0].keys():
            values = [entry[channel] for entry in df_pi['sensor_data']]
            timestamps = df_pi['timestamp'].values
            axs[i].plot(timestamps, values, label=channel)

        axs[i].legend()
        axs[i].grid(True)

    plt.xlabel('Timestamp')
    plt.show()




if __name__ == "__main__":
    folder_path = 'measurement_data'

    while True:
        data = load_latest_data(folder_path)
        plot_data(data)
        time.sleep(5) 
