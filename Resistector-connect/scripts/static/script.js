document.addEventListener('DOMContentLoaded', (event) => {
    const gridContainer = document.getElementById('grid-container');
    gridContainer.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
    gridContainer.style.gridTemplateRows = `repeat(${rows}, 1fr)`;

    const totalWidth = gridContainer.clientWidth;
    const totalHeight = gridContainer.clientHeight;
    const circleSize = Math.min((totalWidth / cols) - 30, (totalHeight / rows) - 30);
    let calibrationIsRunning = false;
    let fetchDataInterval;
    let fetchTimestampInterval;

    // Initialize circles with correct coordinates starting from 0
    for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
            const circle = document.createElement('div');
            circle.className = 'circle';
            circle.style.width = `${circleSize}px`;
            circle.style.height = `${circleSize}px`;
            circle.dataset.x = x;
            circle.dataset.y = y;
            gridContainer.appendChild(circle);
        }
    }

    const timestampContainer = document.createElement('div');
    timestampContainer.className = 'timestamp-container';
    document.body.appendChild(timestampContainer);

    let latestDate = null;
    let showDetails = false; // Default state for the toggle

    function updateTimestampStatus() {
        const currentDate = new Date();
        if (latestDate) {
            const delay = (currentDate - latestDate) / 1000;
            if (delay > 10) {
                console.error('Delay too big to system time. Possible connection error detected!');
                timestampContainer.style.color = 'red';
                timestampContainer.innerHTML += ' <span>&#9888;</span>'; // Adds a warning icon
            } else if (delay > 5) {
                console.warn('Small delay of MeasurementData transfer. Check system stability!');
                timestampContainer.style.color = 'yellow';
            } else {
                timestampContainer.style.color = 'white';
            }
        } else {
            timestampContainer.style.color = 'red';
            timestampContainer.innerHTML = 'No data received &#9888;'; // Adds a warning icon
        }
    }

    function fetchData() {
        fetch('/sensor_data')
            .then(response => {
                if (response.status === 423) {
                    // Wenn der Statuscode 423 ist, mache eine Konsolenausgabe mit dem Inhalt der Antwort
                    return response.json().then(responseData => {
                        console.error('Resource is currently locked:', responseData);
                        // Beende die Funktion ohne weiter zu machen
                        return;
                    });
                }
    
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
    
                return response.json();
            })
            .then(responseData => {
                if (responseData === undefined) {
                    // Falls responseData undefined ist, beende die Funktion
                    return;
                }
    
                const data = getDataFromResponse(responseData);
                if (!data) {
                    console.error('Data is undefined, null, or empty');
                    return;
                }
    
                resetCircles();
                updateCirclesWithData(data);
                updateTimestamp(responseData);
            })
            .catch(handleFetchError);
    }
    
    
    function getDataFromResponse(responseData) {
        // Prüfe, ob die Daten direkt in responseData oder unter data enthalten sind
        const data = responseData.data || responseData;
        return Object.keys(data).length ? data : null;
    }
    
    function resetCircles() {
        const circles = document.getElementsByClassName('circle');
        for (let circle of circles) {
            circle.style.backgroundColor = '#2d2d2d';
            circle.removeAttribute('title');
        }
    }
    
    function updateCirclesWithData(data) {
        const circles = document.getElementsByClassName('circle');
        Object.keys(data).forEach(key => {
            const [x, y] = key.split(',').map(Number);
            const { State: state } = data[key];
            //console.log(`Key: ${key}, X: ${x}, Y: ${y}, State: ${state}`);
    
            const index = (rows - 1 - y) * cols + x;
            if (circles[index]) {
                circles[index].style.backgroundColor = getColorForState(state);
                if (showDetails) {
                    circles[index].setAttribute('title', `X: ${x}, Y: ${y}, State: ${state}`);
                }
            }
        });
    }
    
    function getColorForState(state) {
        switch (state) {
            case 'X':
                return 'blue';
            case 'XX':
                return 'yellow';
            default:
                return '#2b2b2b';
        }
    }
    
    function updateTimestamp(timestampsData) {
            latestDate = timestampsData.timestamp
            
    
            timestampContainer.textContent = `MeasurementData Timestamp: ${new Date(latestDate).toLocaleString()}`;
            updateTimestampStatus();
        };
    
    function handleFetchError(error) {
        console.error('Fetch error:', error);
        timestampContainer.style.color = 'red';
        timestampContainer.innerHTML = 'Connection error &#9888;'; // Fügt ein Warnsymbol hinzu
    }
    
    
    checkCalibrationStatus();
    setInterval(checkCalibrationStatus,1000);
    fetchData();
    fetchDataInterval = setInterval(fetchData, 1000);
    fetchTimestampInterval= setInterval(updateTimestampStatus, 1000);

    function stopProcesses(){
        clearInterval(fetchDataInterval);
        clearInterval(fetchTimestampInterval);
        timestampContainer.innerHTML = 'Calibration in progress &#9888;';
    }
    function startProcesses(){
        fetchDataInterval = setInterval(fetchData, 1000);
        fetchTimestampInterval= setInterval(updateTimestampStatus, 1000);
    }

    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggle-btn');
    const toggleDetailsCheckbox = document.getElementById('toggle-details');

    toggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        if (sidebar.classList.contains('collapsed')) {
            toggleBtn.innerHTML = '&#9776;'; // Hamburger menu icon
        } else {
            toggleBtn.innerHTML = '&#11144;'; // Arrow icon
        }
    });

    toggleDetailsCheckbox.addEventListener('change', () => {
        showDetails = toggleDetailsCheckbox.checked;
        const circles = document.getElementsByClassName('circle');
        if (showDetails) {
            // Add tooltips for all circles
            for (let circle of circles) {
                const x = circle.dataset.x;
                const y = circle.dataset.y;
                const state = circle.style.backgroundColor === 'blue' ? 'X' : circle.style.backgroundColor === 'yellow' ? 'XX' : '';
                if (state) {
                    circle.setAttribute('title', `X: ${x}, Y: ${y}, State: ${state}`);
                }
            }
        } else {
            // Remove tooltips for all circles
            for (let circle of circles) {
                circle.removeAttribute('title');
            }
        }
    });


    const CalibrateButton = document.getElementById('CalibrateButton')
    CalibrateButton.addEventListener('click', handleCalibrate)





    const calibrateButton = document.getElementById('CalibrateButton');
    const modal = document.getElementById('calibrationModal');
    const modalText = document.getElementById('modalText');
    const finishButton = document.getElementById('finishButton');

    calibrateButton.addEventListener('click', handleCalibrate);

    finishButton.addEventListener('click', () => {
        startProcesses();
        modal.style.display = 'none';
        // Optionally, trigger any actions needed after finishing calibration
    });

    function handleCalibrate() {
        stopProcesses();
        modal.style.display = 'block'; // Show the modal

        fetch('/calibrate')
            .then(response => response.json())
            .catch(error => console.error('Error:', error));

        // Optionally, check calibration status immediately

        checkCalibrationStatus();
    }

    function checkCalibrationStatus() {
        fetch('/calibration_status')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'Completed') {
                    calibrationIsRunning = false;
                    modalText.textContent = 'Calibration finished. Please continue';
                    finishButton.style.display = 'block'; // Show the finish button
                } else if (data.status === 'Not Started') {
                    calibrationIsRunning = false;
                    
                } else {
                    calibrationIsRunning = true;
                    modalText.textContent = 'Calibration is running. Please wait';
                    finishButton.style.display = 'none'; // Hide the finish button
                    
                }
            })
            .catch(error => console.error('Error:', error));
    }

    setInterval(checkCalibrationStatus, 1000); // Check every second

    
});

