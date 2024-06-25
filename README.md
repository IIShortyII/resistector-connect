
# Resistector Connect

## Table of Contents
1. Introduction
2. Prerequisites
3. Installation
3.1 MainPi
3.2 ClientPis
5. Configuration
6. Usage
7. File Structure
8. Troubleshooting
9. License

## Introduction
Resistector Connect is an application for monitoring and data acquisition from multiple Raspberry Pis over a network. The application includes a main control interface that pings clients and collects data from them, along with a graphical user interface for visualizing the collected data.

## Prerequisites
- Raspberry Pi with Raspbian OS
- Python 3.x
- The following Python libraries:
  - `tkinter`
  - `requests`
  - `flask`
  - `configparser`
  - `matplotlib`
  - `pandas`
- And the ADS1263 working on RaspberryPi. For example Waveshare AD HAT: https://www.waveshare.com/wiki/High-Precision_AD_HAT

## Installation 
The installation is split in one MainPi which holds the servers and measurement coordination
and the ClientPis which hold the measuring and data providing. 
### MainPi
1. Clone this repository on your main Raspberry Pi:
    ```sh
    git clone https://github.com/IIShortyII/resistector-connect.git
    cd resistector-connect
    ```
 2. Install`xdotool`: 
    ```sh
    sudo apt-get install xdotool
    ```
 3. Setup an AccessPoint for your ClientPis
 4. Adjust the config.ini to fit your Network Setting
    
### ClientPis
1. Copy `measurementClient.py`, `config.ini` and the ADC folder to your ClientPi
2. Connect to the MainPi AccessPoint
3. Adjust the config.ini to fit your Network Settings

## Configuration MainPi
Adjust the `config.ini` file according to your network and sensor configuration:

```ini
#Resistector Config

#Local Settings are for local measurement adjustments 
[Local-Settings]
channelList = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9#can be between 0 and 9
level = bb                                #only bb = breadboard, and ll1 = logiclayer1 are allowed
local_client_ip = 10.42.0.1               #IP address of the MeasurementClient running on THIS RaspberryPi
scan_frequence = ADS1263_2d5SPS           #ADC scan frequency DO NOT CHANGE

#Network Settings are for data exchange between client Pis and the server WebApp
[Network]
client_ips = 10.42.0.1, 10.42.0.2, 10.42.0.3    #all IP addresses of the clients
client_port = 5000                              #all clients share the same port
webapp_port = 5050                              #the ResistectorUI port


```
## Usage
1. Launch the main program `main.py`
```sh
python3 main.py
```
2. The GUI opens and connects to the clients.
3. Once all clients are connected, you can perform the following actions:
    -   "Start Plotter": Opens the plotter to display respective measurement data on a line chart.
    -   "Start Resistector UI": Launches the web app that can be used within the network.
    -   "Shutdown": Exits Resistector Connect and all subscripts.


## File Structure
-   logs: Contains logs related to Resistector Connect
-   measurement_data: Contains measurement data from all sessions
-   scripts: Contains the subscripts
-   config.ini: Configuration file for Resistector Connect, measurementClients, measurementServer, and ResistectorUI
-   main.py: Main script controlling Resistector Connect
-   measurementClient.py: Script running on each client Raspberry Pi, capturing sensor data.
-   measurementServer.py: Script for collecting and storing sensor data from the clients.
-   plot.py: Script for displaying the collected sensor data.
-   resistectorUI.py: Flask web application for displaying a graphical user interface.
-   ADC/: Contains the ADS1263 driver


