document.addEventListener('DOMContentLoaded', (event) => {
    const gridContainer = document.getElementById('grid-container');
    gridContainer.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
    gridContainer.style.gridTemplateRows = `repeat(${rows}, 1fr)`;

    const totalWidth = gridContainer.clientWidth;
    const totalHeight = gridContainer.clientHeight;
    const circleSize = Math.min((totalWidth / cols) - 20, (totalHeight / rows) - 20);

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
            .then(response => response.json())
            .then(responseData => {
                const { data, timestamps } = responseData;
                const circles = document.getElementsByClassName('circle');
                for (let circle of circles) {
                    circle.style.backgroundColor = '#2d2d2d';
                    circle.removeAttribute('title');
                }

                data.forEach(item => {
                    const { x, y, state } = item;
                    const index = (rows - 1 - y) * cols + x; // Adjusted to start from 0 and flip y-axis
                    if (circles[index]) {
                        if (state === 'X') {
                            circles[index].style.backgroundColor = 'blue';
                        } else if (state === 'XX') {
                            circles[index].style.backgroundColor = 'yellow';
                        } else {
                            circles[index].style.backgroundColor = '#2b2b2b';
                        }
                        if (showDetails) {
                            circles[index].setAttribute('title', `X: ${x}, Y: ${y}, State: ${state}`);
                        }
                    }
                });

                latestDate = Object.values(timestamps).reduce((latest, current) => {
                    return new Date(latest) > new Date(current) ? latest : current;
                }, '');

                timestampContainer.textContent = `MeasurementData Timestamp: ${new Date(latestDate).toLocaleString()}`;
                updateTimestampStatus();
            })
            .catch(error => {
                timestampContainer.style.color = 'red';
                timestampContainer.innerHTML = 'Connection error &#9888;'; // Adds a warning icon
            });
    }

    fetchData();
    setInterval(fetchData, 1000);
    setInterval(updateTimestampStatus, 1000); // Check delay every second

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
});
