
# Resistector Connect

## Table of Contents
1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
  1. [MainPi](###mainpi)
  2. [ClientPis](#clientpis)
5. [Configuration](#configuration-mainpi)
6. [Usage](#usage)
7. [File Structure](#file-structure)

## Introduction
Resistector Connect is the software part of the master thesis at LMU Munich Media Informatics Group. 
It monitors and controls data flow from multiple Raspberry Pis over a network. Allowing to see and work with the data in plot charts and a WebApp. 
It is based on an ADS1263 ADC and Raspberry Pi 4s. 

The master's thesis is about recognising objects without camera support or image recognition. The entire hardware is 3D printed.
This software is divided into different subscripts. 
The centrepiece is Resistector connect (main.py), which establishes the connection between the MainPi and the ClientPis. 
From there, a data connection is established and measurement data is exchanged between client (measurementClient.py) and server (measurementServer.py). This data is filtered and stored in a measurement data JSON. This JSON is then processed further. Measurement data changes can be used to recognise objects, which are then displayed in a frontend. This all happens in ResistectorUI.py. 

For a detailed explanation and further information, please refer to my thesis. 

## Prerequisites
- Raspberry Pi with Raspbian OS
- Python 3.x
- The following Python libraries:
  - `flask`
  - `flask-CORS`
  - `numpy`
  - `matplotlib`
  - `pandas`
  - `requests`

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
 2. Install prerequiriers 
    ```sh
    pip install Flask Flask-CORS numpy pandas matplotlib requests
    ```
 3. Install`xdotool`: 
    ```sh
    sudo apt-get install xdotool
    ```
 4. Setup an AccessPoint for your ClientPis
 5. Adjust the config.ini to fit your Network Setting
    
### ClientPis
1. Copy the scripts folder and `config.ini`  to your ClientPi/home/USER/Resistector-connect
2. Connect to the MainPi AccessPoint
3. Adjust the config.ini to fit your Network Settings
4. Optional: Add the `measurementClient.py` to `rc.local` to automatically start the Client with every reboot
    - Open terminal and open the rc.local file:  
      ```sh
      sudo nano /etc/rc.local
      ```
    -  Add the following above `exit 0`, you may have to adjust the path    
       to fit your location:
        ```sh
        /usr/bin/python3 /home/resistector/Resistector-connect/scripts/measurementClient.py > /home/resistector/Resistector-connect/logs/autostart.log 2>&1 &  
        ```
    - save with `ctrl + S` and exit nano with `ctrl + X`
    - reboot with command:
      ```sh
      reboot
      ```

## Configuration MainPi
Adjust the `config.ini` file according to your network and sensor configuration:

```ini
#Resistector Config

#Local Settings are for local measurement adjustments 
[Local-Settings]
channelList = 0, 1, 2, 3, 4, 5, 6, 7      #can be between 0 to 9
level = bb                                #only bb = breadboard, and ll1 = logiclayer1 is allowed
local_client_ip = 10.42.0.1               #the IP adress of the measurementClient running on THIS RaspberryPi
scan_frequence = ADS1263_2d5SPS           #ADC scanning frequency DO NOT CHANGE
hysteresis = 8                            #Time for under or over measurement mean to count as detected
threshold = 0.2                           #Absolute Amount under or over measurement mean 

#Network Settings are for data exchange between client Pis and the server WebApp
[Network]
client_ips = 10.42.0.1, 10.42.0.2, 10.42.0.3    #all ip adresses of clients FORMAT for Axis is X Y LL
client_port = 5000                              #all client share the same port
webapp_port = 5050                              #the ResistectorUI port

[Web-UI]
amountX-Axis = 8                                # The amount of measurement points in the horizontal(X) axis
amountY-Axis = 6                                # The amount of measurement poins in the vertical(Y) axis
```
## Usage
1. Launch the main program `main.py`
    ```sh
    python3 main.py
    ```
2. The GUI opens and connects to the clients.

    If all clients are connected the console shows a confirmation like this:
    ```
      All clients registered. Measurement server startup
    ```
    This means, that the measurement data is now beeing processed and saved in the measurementData folder. 

    If there is a problem with the connection or transmitting the sensor data an error message is shown in the console.
3. Once all clients are connected, you can perform the following actions:
    -   "Start Plotter": Opens the plotter to display respective measurement data on a line chart.
    -   "Start Resistector UI": Launches the web app that can be used within the network.
    -   "Shutdown": Exits Resistector Connect and all subscripts.


## File Structure
```
\Resistector-connect
├──\pycache 
├──\logs 
├──\measurement_data 
├──\scripts 
│ ├──\ADC
│ │ ├──ADS1263.py
│ │ ├──config.py
│ ├──\static
│ │ ├──\Bauteilbilder
│ │ ├──\fonts
│ │ ├──ResistectorUI.ico
│ │ ├──ResistectorUI.png
│ │ ├──script.js
│ │ ├──styles.css
│ ├──\templates
│ │ ├──index.html
│ ├──\tmp
│ ├──measurementClient.py
│ ├──measurementServer.py 
│ ├──plot.py 
│ ├──ResistectorUI.py 
├──config.ini 
└──main.py 
```


