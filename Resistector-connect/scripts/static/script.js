document.addEventListener('DOMContentLoaded', (event) => {
  const gridContainer = document.getElementById('grid-container');

  gridContainer.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  gridContainer.style.gridTemplateRows = `repeat(${rows}, 1fr)`;

  const totalWidth = gridContainer.clientWidth;
  const totalHeight = gridContainer.clientHeight;
  const circleSize = Math.min((totalWidth / cols) - 20, (totalHeight / rows) - 20); // Adjusted gap size

  for (let i = 0; i < rows * cols; i++) {
    const circle = document.createElement('div');
    circle.className = 'circle';
    circle.style.width = `${circleSize}px`;
    circle.style.height = `${circleSize}px`;
    gridContainer.appendChild(circle);
  }
});
