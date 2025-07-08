
function previewCSV(file) {
    const reader = new FileReader();
    reader.onload = function(e) {
        const csv = e.target.result;
        const lines = csv.split('\n').slice(0, 5); // Показываем первые 5 строк
        const table = document.createElement('table');
        table.style.border = '1px solid #ddd';
        table.style.marginTop = '10px';
        table.style.borderCollapse = 'collapse';
        
        lines.forEach((line, index) => {
            const row = table.insertRow();
            const cells = line.split(';');
            cells.forEach(cell => {
                const cellElement = row.insertCell();
                cellElement.textContent = cell.trim();
                cellElement.style.border = '1px solid #ddd';
                cellElement.style.padding = '5px';
                if (index === 0) {
                    cellElement.style.fontWeight = 'bold';
                    cellElement.style.backgroundColor = '#f5f5f5';
                }
            });
        });
        
        const previewDiv = document.createElement('div');
        previewDiv.appendChild(document.createTextNode(`Preview: ${file.name}`));
        previewDiv.appendChild(table);
        document.getElementById('gallery').appendChild(previewDiv);
    };
    reader.readAsText(file);
}

function previewCSV(file) {
    const reader = new FileReader();
    reader.onload = function(e) {
        const csv = e.target.result;
        const lines = csv.split('\n');
        const headers = lines[0].split(';');
        
        let preview = '<div class="csv-preview">';
        preview += '<table>';
        preview += '<tr>';
        headers.forEach(header => {
            preview += `<th>${header.trim()}</th>`;
        });
        preview += '</tr>';
        
        // Show first 5 rows
        for (let i = 1; i < Math.min(6, lines.length); i++) {
            if (lines[i].trim()) {
                const cells = lines[i].split(';');
                preview += '<tr>';
                cells.forEach(cell => {
                    preview += `<td>${cell.trim()}</td>`;
                });
                preview += '</tr>';
            }
        }
        
        preview += '</table></div>';
        preview += `<div class="message success">📊 CSV файл: ${file.name} (${lines.length - 1} строк данных)</div>`;
        
        document.getElementById('gallery').innerHTML += preview;
    };
    reader.readAsText(file, 'utf-8');
}
