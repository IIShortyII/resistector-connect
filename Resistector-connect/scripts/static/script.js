document.addEventListener('DOMContentLoaded', (event) => {

    const gridContainer = document.getElementById('grid-container');

    gridContainer.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
    gridContainer.style.gridTemplateRows = `repeat(${rows}, 1fr)`;

    const totalWidth = gridContainer.clientWidth;
    const totalHeight = gridContainer.clientHeight;
    const circleSize = Math.min((totalWidth / cols) - 20, (totalHeight / rows) - 20);

    // Elemente in umgekehrter Reihenfolge hinzufügen, um von unten links zu beginnen
    for (let y = rows - 1; y >= 0; y--) {
        for (let x = 0; x < cols; x++) {
            const circle = document.createElement('div');
            circle.className = 'circle';
            circle.style.width = `${circleSize}px`;
            circle.style.height = `${circleSize}px`;
            gridContainer.appendChild(circle);
        }
    }

    const timestampContainer = document.createElement('div');
    timestampContainer.className = 'timestamp-container';
    document.body.appendChild(timestampContainer);

    function fetchData() {
        fetch('/sensor_data')
            .then(response => response.json())
            .then(responseData => {
                const { data, timestamps } = responseData;
                console.log(timestamps)
                // Clear existing circles
                const circles = document.getElementsByClassName('circle');
                for (let circle of circles) {
                    circle.style.backgroundColor = '#2d2d2d';
                }

                // Update circles based on received data
                data.forEach(item => {
                    const { x, y, state } = item;
                    // Index neu berechnen, da wir von unten nach oben gehen
                    const index = (rows - y) * cols + x - 1;
                    if (circles[index]) {
                        if (state === 'X') {
                            circles[index].style.backgroundColor = 'blue';
                        } else if (state === 'XX') {
                            circles[index].style.backgroundColor = 'yellow';
                        } else {
                            circles[index].style.backgroundColor = '#2b2b2b';
                        }
                    }
                });

                // Find the latest timestamp
                const latestTimestamp = Object.values(timestamps).reduce((latest, current) => {
                    return new Date(latest) > new Date(current) ? latest : current;
                }, '');

                timestampContainer.textContent = `MeasurementData Timestamp: ${new Date(latestTimestamp).toLocaleString()}`;
            })
            .catch(error => console.error('Error fetching data:', error));
    }

    // Fetch data initially and then at regular intervals
    fetchData();
    setInterval(fetchData, 1000); // Fetch new data every second
});
