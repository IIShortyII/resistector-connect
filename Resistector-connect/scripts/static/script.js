document.addEventListener('DOMContentLoaded', () => {
    const gridContainer = document.getElementById('grid-container');
    const upperLight = document.getElementById('upper');
    const middleLight = document.getElementById('middle');
    const lowerLight = document.getElementById('lower');
    const timestampContainer = createTimestampContainer();
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggle-btn');
    const toggleDetailsCheckbox = document.getElementById('toggle-details');
    const calibrateButton = document.getElementById('CalibrateButton');
    const modal = document.getElementById('calibrationModal');
    const modalText = document.getElementById('modalText');
    const finishButton = document.getElementById('finishButton');
    
    let calibrationIsRunning = false;
    let fetchDataInterval, fetchTimestampInterval;
    let latestDate = null;
    let showDetails = false;

    setupGrid();
    fetchData();
    fetchDataInterval = setInterval(fetchData, 1000);
    fetchTimestampInterval = setInterval(updateTimestampStatus, 1000);
    setInterval(checkCalibrationStatus, 1000);

    toggleBtn.addEventListener('click', toggleSidebar);
    toggleDetailsCheckbox.addEventListener('change', toggleDetails);
    calibrateButton.addEventListener('click', handleCalibrate);
    finishButton.addEventListener('click', finishCalibration);

    function setupGrid() {
        gridContainer.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
        gridContainer.style.gridTemplateRows = `repeat(${rows}, 1fr)`;

        const totalWidth = gridContainer.clientWidth;
        const totalHeight = gridContainer.clientHeight;
        const circleSize = Math.min((totalWidth / cols) - 30, (totalHeight / rows) - 30);

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
    }

    function createTimestampContainer() {
        const container = document.createElement('div');
        container.className = 'timestamp-container';
        document.body.appendChild(container);
        return container;
    }

    function updateTimestampStatus() {
        if (!latestDate) {
            timestampContainer.style.color = 'red';
            timestampContainer.innerHTML = 'No data received &#9888;';
            return;
        }

        const delay = (new Date() - latestDate) / 1000;
        if (delay > 10) {
            setWarning('Delay too big to system time. Possible connection error detected!', 'red');
        } else if (delay > 5) {
            setWarning('Small delay of MeasurementData transfer. Check system stability!', 'yellow');
        } else {
            timestampContainer.style.color = 'white';
        }
    }

    function fetchData() {
        fetch('/sensor_data')
            .then(handleFetchResponse)
            .then(handleResponseData)
            .catch(handleFetchError);
    }

    function handleFetchResponse(response) {
        if (response.status === 423) {
            return response.json().then(responseData => {
                console.error('Resource is currently locked:', responseData);
                return Promise.reject('Resource locked');
            });
        }

        if (!response.ok) {
            return response.text().then(text => {
                try {
                    const json = JSON.parse(text);
                    throw new Error('Network response was not ok. Response: ' + JSON.stringify(json));
                } catch {
                    throw new Error('Network response was not ok. Response: ' + text);
                }
            });
        }

        return response.json();
    }

    function handleResponseData(responseData) {
        const data = responseData?.data || responseData;

        if (!data || !Object.keys(data).length) {
            console.error('Data is undefined, null, or empty');
            return;
        }

        resetCircles();
        updateCirclesWithData(data);
        updateTimestamp(responseData);
        updateSystemState(responseData);
    }

    function resetCircles() {
        const circles = document.getElementsByClassName('circle');
        Array.from(circles).forEach(circle => {
            circle.style.backgroundColor = '#2d2d2d';
            circle.removeAttribute('title');
        });
    }

    function updateCirclesWithData(data) {
        const circles = document.getElementsByClassName('circle');

        Object.entries(data.displayData).forEach(([key, value]) => {
            const [x, y] = key.split(',').map(Number);
            const index = (rows - 1 - y) * cols + x;
            const circle = circles[index];
            if (circle) {
                circle.style.backgroundColor = getColorForState(value.State);
                if (showDetails) {
                    circle.setAttribute('title', `X: ${x}, Y: ${y}, State: ${value.State}`);
                }
            }
        });

        updateComponents(data.components);
    }

    function updateComponents(components) {
        removeExistingComponents();

        Object.entries(components).forEach(([key, component]) => {
            const img = document.createElement('img');
            img.src = `static/Bauteilbilder/${component.type}.png`;
            img.className = 'component';
            img.style.position = 'absolute';

            const circleLocation = getCirclePosition(
                component.orientation === 'horizontal' ? component.x - 1 : component.x,
                component.y
            );

            setComponentPosition(img, component, circleLocation);
            gridContainer.appendChild(img);
        });
    }

    function removeExistingComponents() {
        const componentImages = document.getElementsByClassName('component');
        while (componentImages[0]) {
            componentImages[0].parentNode.removeChild(componentImages[0]);
        }
    }

    function setComponentPosition(img, component, circleLocation) {
        const circleSize = getCircleSize();
        if (component.orientation === 'horizontal') {
            img.style.left = `${circleLocation.left}px`;
            img.style.width = component.type === 'LED' || component.type === 'Resistor'
                ? `${circleSize * 2.7}px`
                : `${circleSize * 4.25}px`;
            img.style.top = `${circleLocation.top}px`;
            img.style.height = `${circleSize * 1.2}px`;
        } else {
            img.style.width = component.type === 'LED' || component.type === 'Resistor'
                ? `${circleSize * 2.5}px`
                : `${circleSize * 3.75}px`;
            img.style.left = `${circleLocation.left - (circleSize / 2.5 * 2)}px`;
            img.style.top = component.type === 'LED' || component.type === 'Resistor'
                ? `${circleLocation.top + (circleSize / 3 * 2) - 10}px`
                : `${circleLocation.top - 5}px`;
            img.style.height = `${circleSize * 1.2}px`;
        }
        img.style.transform = component.orientation === 'horizontal' ? 'rotate(0deg)' : 'rotate(90deg)';
    }

    function getCircleSize() {
        const totalWidth = gridContainer.clientWidth;
        const totalHeight = gridContainer.clientHeight;
        return Math.min((totalWidth / cols) - 30, (totalHeight / rows) - 30);
    }

    function getCirclePosition(x, y) {
        y = rows - y - 1;
        const circle = document.querySelector(`.circle[data-x='${x}'][data-y='${y}']`);
        if (!circle) {
            console.error(`Circle at (${x}, ${y}) not found.`);
            return {};
        }

        const rect = circle.getBoundingClientRect();
        return { top: rect.top, left: rect.left };
    }

    function getColorForState(state) {
        const stateColors = {
            'X': 'blue',
            'XX': 'yellow',
            default: '#2b2b2b'
        };
        return stateColors[state] || stateColors.default;
    }

    function updateTimestamp(responseData) {
        latestDate = responseData.timestamp;
        timestampContainer.textContent = `MeasurementData Timestamp: ${new Date(latestDate).toLocaleString()}`;
        updateTimestampStatus();
    }

    function updateSystemState(SystemStateData) {
        const systemStateColors = {
            'Red': { upper: 'red', middle: '#242323', lower: '#242323' },
            'Yellow': { upper: '#242323', middle: 'yellow', lower: '#242323' },
            'Green': { upper: '#242323', middle: '#242323', lower: 'green' }
        };

        const colors = systemStateColors[SystemStateData.SystemState];
        if (colors) {
            upperLight.style.background = colors.upper;
            middleLight.style.background = colors.middle;
            lowerLight.style.background = colors.lower;
        }
    }

    function setWarning(message, color) {
        console.warn(message);
        timestampContainer.style.color = color;
        timestampContainer.innerHTML += ' <span>&#9888;</span>';
    }

    function handleFetchError(error) {
        console.error('Fetch error:', error);
        timestampContainer.style.color = 'red';
        timestampContainer.innerHTML = 'Connection error &#9888;';
    }

    function toggleSidebar() {
        sidebar.classList.toggle('collapsed');
        toggleBtn.innerHTML = sidebar.classList.contains('collapsed') ? '&#9776;' : '&#11144;';
    }

    function toggleDetails() {
        showDetails = toggleDetailsCheckbox.checked;
        const circles = document.getElementsByClassName('circle');
        Array.from(circles).forEach(circle => {
            if (showDetails) {
                const x = circle.dataset.x;
                const y = circle.dataset.y;
                const state = getStateFromColor(circle.style.backgroundColor);
                if (state) {
                    circle.setAttribute('title', `X: ${x}, Y: ${y}, State: ${state}`);
                }
            } else {
                circle.removeAttribute('title');
            }
        });
    }

    function getStateFromColor(color) {
        const colorStateMap = {
            'blue': 'X',
            'yellow': 'XX'
        };
        return colorStateMap[color] || '';
    }

    function handleCalibrate() {
        stopProcesses();
        modal.style.display = 'block';
        fetch('/calibrate')
            .then(response => response.json())
            .catch(error => console.error('Error:', error));
        checkCalibrationStatus();
    }

    function checkCalibrationStatus() {
        fetch('/calibration_status')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'Completed') {
                    calibrationIsRunning = false;
                    modalText.textContent = 'Calibration finished. Please continue';
                    finishButton.style.display = 'block';
                } else if (data.status === 'Not Started') {
                    calibrationIsRunning = false;
                } else {
                    calibrationIsRunning = true;
                    modalText.textContent = 'Calibration is running. Please wait';
                    finishButton.style.display = 'none';
                }
            })
            .catch(error => console.error('Error:', error));
    }

    function finishCalibration() {
        startProcesses();
        modal.style.display = 'none';
    }

    function stopProcesses() {
        clearInterval(fetchDataInterval);
        clearInterval(fetchTimestampInterval);
        timestampContainer.innerHTML = 'Calibration in progress &#9888;';
    }

    function startProcesses() {
        fetchDataInterval = setInterval(fetchData, 1000);
        fetchTimestampInterval = setInterval(updateTimestampStatus, 1000);
    }
});
