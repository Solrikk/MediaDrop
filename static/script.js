
async function copyToClipboard(text, event) {
    event.preventDefault();
    try {
        await navigator.clipboard.writeText(text);
        const target = event.target;
        const originalText = target.innerHTML;
        target.innerHTML = "Copied! ✓";
        setTimeout(() => {
            target.innerHTML = originalText;
        }, 1000);
    } catch (err) {
        console.error('Failed to copy text: ', err);
    }
}

let dropArea = document.getElementById('drop-area');
let progress = document.getElementById('progress');
let responseDiv = document.getElementById('response');

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
    dropArea.addEventListener(eventName, () => dropArea.classList.add('highlight'), false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, () => dropArea.classList.remove('highlight'), false);
});

dropArea.addEventListener('drop', handleDrop, false);

function handleDrop(e) {
    let dt = e.dataTransfer;
    let files = dt.files;
    handleFiles(files);
}

async function handleFiles(files) {
    const fileList = document.getElementById('fileElem').files;
    let newFileList = new DataTransfer();
    let fileNames = new Set();

    for (let i = 0; i < fileList.length; i++) {
        newFileList.items.add(fileList[i]);
        fileNames.add(fileList[i].name);
    }
    for (let i = 0; i < files.length; i++) {
        if (!fileNames.has(files[i].name)) {
            newFileList.items.add(files[i]);
        }
    }
    document.getElementById('fileElem').files = newFileList.files;
    files = [...newFileList.files];
    files.forEach(previewFile);
}

function previewFile(file) {
    if (file.name.toLowerCase().endsWith('.csv')) {
        previewCSV(file);
        return;
    }
    
    let reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onloadend = function() {
        let elem;
        if (file.type.startsWith('video/')) {
            elem = document.createElement('video');
            elem.src = reader.result;
            elem.controls = true;
            elem.style.maxWidth = '120px';
            elem.style.margin = '10px';
            elem.style.border = '2px solid #ddd';
            elem.style.borderRadius = '10px';
        } else if (file.type.startsWith('image/')) {
            elem = document.createElement('img');
            elem.src = reader.result;
            elem.style.maxWidth = '120px';
            elem.style.margin = '10px';
            elem.style.border = '2px solid #ddd';
            elem.style.borderRadius = '10px';
        }

        if (elem) {
            document.getElementById('gallery').appendChild(elem);
        }
    }
}

function previewCSV(file) {
    let reader = new FileReader();
    reader.readAsText(file);
    reader.onload = function(e) {
        const csv = e.target.result;
        const lines = csv.split('\n');
        const headers = lines[0].split(';');
        
        let table = '<table border="1" style="margin: 10px; border-collapse: collapse;">';
        table += '<tr>';
        headers.forEach(header => {
            table += `<th style="padding: 5px; background: #f0f0f0;">${header}</th>`;
        });
        table += '</tr>';
        
        for (let i = 1; i < Math.min(6, lines.length); i++) {
            if (lines[i].trim()) {
                const cells = lines[i].split(';');
                table += '<tr>';
                cells.forEach(cell => {
                    table += `<td style="padding: 5px;">${cell}</td>`;
                });
                table += '</tr>';
            }
        }
        table += '</table>';
        
        document.getElementById('gallery').innerHTML += `<div style="margin: 10px;"><strong>${file.name}:</strong><br>${table}</div>`;
    };
}

function shortenFilename(filename, maxLength = 10) {
    const ext = filename.slice(filename.lastIndexOf('.'));
    const baseName = filename.slice(0, filename.lastIndexOf('.'));
    return baseName.slice(0, maxLength).replace(/\s/g, '_') + ext;
}

function handleTextFiles(files) {
    const textFilesList = document.getElementById('textFilesList');
    const processBtn = document.getElementById('processTextBtn');
    
    if (files.length > 0) {
        let fileListHTML = '<h4>Выбранные файлы:</h4><ul>';
        for (let i = 0; i < files.length; i++) {
            const fileType = files[i].name.toLowerCase().endsWith('.csv') ? 'CSV' : 'TXT';
            fileListHTML += `<li>${files[i].name} (${fileType})</li>`;
        }
        fileListHTML += '</ul>';
        textFilesList.innerHTML = fileListHTML;
        processBtn.style.display = 'inline-block';
    } else {
        textFilesList.innerHTML = '';
        processBtn.style.display = 'none';
    }
}

async function processTextFiles() {
    const textFileInput = document.getElementById('textFiles');
    const progress = document.getElementById('progress');
    const responseDiv = document.getElementById('response');
    const files = textFileInput.files;

    if (files.length === 0) {
        responseDiv.innerHTML = 'Пожалуйста, выберите текстовые или CSV файлы!';
        return;
    }

    // Проверяем, что все файлы имеют правильный формат
    for (let i = 0; i < files.length; i++) {
        const fileName = files[i].name.toLowerCase();
        if (!fileName.endsWith('.txt') && !fileName.endsWith('.csv')) {
            responseDiv.innerHTML = `Файл ${files[i].name} не является текстовым или CSV файлом!`;
            return;
        }
    }

    progress.innerHTML = '<div class="progress-bar"><div class="progress-fill"></div></div><span>Обрабатываем файлы... Пожалуйста, подождите.</span>';

    try {
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        // Устанавливаем timeout для больших файлов
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 минут

        const response = await fetch('/process_multiple_text_files/', {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
        }

        const result = await response.json();

        if (result.success) {
            progress.innerText = 'Текстовые файлы успешно обработаны!';
            
            let displayHTML = `<div style="margin: 10px 0;">
                <strong>Обработано файлов:</strong> ${result.total_files}<br>
                <strong>Результаты обработки:</strong><br>
                <div style="margin-top: 10px;">`;
            
            result.processed_files.forEach(file => {
                if (file.error) {
                    displayHTML += `<div style="margin: 5px 0; padding: 10px; background: #ffe6e6; border-radius: 5px;">
                        <strong>${file.original_filename}:</strong> Ошибка - ${file.error}
                    </div>`;
                } else {
                    displayHTML += `<div style="margin: 5px 0; padding: 10px; background: #e6ffe6; border-radius: 5px;">
                        <strong>${file.original_filename}:</strong> Обработано ссылок: ${file.urls_processed}<br>
                        <a href="${file.download_url}" target="_blank" class="button" style="display: inline-block; margin-top: 5px;">Скачать ${file.processed_filename}</a>
                    </div>`;
                }
            });
            
            displayHTML += '</div></div>';
            responseDiv.innerHTML = displayHTML;
            
            textFileInput.value = '';
            handleTextFiles([]);
        } else {
            progress.innerText = 'Ошибка при обработке файлов';
            responseDiv.innerHTML = 'Произошла ошибка при обработке файлов';
        }
    } catch (error) {
        progress.innerText = 'Ошибка при обработке файлов';
        
        if (error.name === 'AbortError') {
            responseDiv.innerHTML = 'Ошибка: Превышено время ожидания (5 минут). Попробуйте обработать файлы по частям или файлы меньшего размера.';
        } else if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
            responseDiv.innerHTML = 'Ошибка сети: Соединение прервано. Попробуйте перезагрузить страницу и попробовать снова.';
        } else if (error.message.includes('500')) {
            responseDiv.innerHTML = 'Ошибка сервера: Проблема при обработке файлов. Проверьте логи сервера.';
        } else {
            responseDiv.innerHTML = `Ошибка: ${error.message}`;
        }
        console.error('Error:', error);
    }
}

async function uploadFiles() {
    const fileInput = document.getElementById('fileElem');
    const progress = document.getElementById('progress');
    const responseDiv = document.getElementById('response');
    const files = fileInput.files;
    const singleLineCheckbox = document.getElementById('singleLineCheckbox');
    const delimiter = document.getElementById('delimiter').value || ' ';

    if (files.length === 1 && files[0].name.toLowerCase().endsWith('.txt')) {
        progress.innerText = 'Processing text file...';
        const formData = new FormData();
        formData.append('file', files[0]);

        try {
            const response = await fetch('/process_text_file/', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `processed_${files[0].name}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                progress.innerText = 'Text file processed successfully!';
                return;
            } else {
                throw new Error('Failed to process text file');
            }
        } catch (error) {
            progress.innerText = 'Failed to process text file';
            console.error('Error:', error);
            return;
        }
    }

    if (files.length === 0) {
        responseDiv.innerText = "Please select files!";
        return;
    }

    let formData = new FormData();
    let hasCSV = false;
    let csvFile = null;

    for (let i = 0; i < files.length; i++) {
        if (files[i].name.toLowerCase().endsWith('.csv')) {
            hasCSV = true;
            csvFile = files[i];
        }
        formData.append('files', files[i]);
    }

    if (hasCSV) {
        formData.append('columns', 'Образец ткани,Фотоконтент,Техническая информация');
    }

    progress.innerHTML = '<div class="progress-bar"><div class="progress-fill"></div></div><span>Uploading... Please wait.</span>';

    try {
        let response = await fetch('/upload/', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        let result = await response.json();

        if (!result || !result.file_urls) {
            throw new Error('Invalid server response format');
        }

        progress.innerText = 'Upload complete.';

        let singleLineCheckbox = document.getElementById('singleLineCheckbox');
        let delimiter = document.getElementById('delimiter').value || '/';

        let links = result.file_urls.map(url => {
            const fullUrl = url.startsWith('http') ? url : window.location.origin + url;
            return `<a href="${fullUrl}" target="_blank">${fullUrl}</a>`;
        });

        if (singleLineCheckbox.checked) {
            responseDiv.innerHTML = links.join(delimiter);
        } else {
            responseDiv.innerHTML = links.join('<br>');
        }
    } catch (error) {
        progress.innerText = 'Ошибка при загрузке.';
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            responseDiv.innerHTML = 'Ошибка сети. Проверьте подключение к интернету и попробуйте снова.';
        } else if (error.message.includes('timeout')) {
            responseDiv.innerHTML = 'Превышено время ожидания. Попробуйте загрузить файлы меньшего размера.';
        } else {
            responseDiv.innerHTML = `Ошибка: ${error.message}`;
        }
        console.error('Upload error:', error);
    }
}

async function processYandexUrl() {
    const urlInput = document.getElementById('yandexUrl');
    const progress = document.getElementById('progress');
    const responseDiv = document.getElementById('response');
    const url = urlInput.value.trim();

    if (!url) {
        responseDiv.innerHTML = 'Пожалуйста, введите ссылку на Яндекс.Диск';
        return;
    }

    if (!url.startsWith('https://disk.yandex.ru/')) {
        responseDiv.innerHTML = 'Некорректная ссылка. Используйте ссылки вида https://disk.yandex.ru/...';
        return;
    }

    progress.innerHTML = '<div class="progress-bar"><div class="progress-fill"></div></div><span>Обрабатываем ссылку... Пожалуйста, подождите.</span>';

    try {
        const formData = new FormData();
        formData.append('url', url);

        const response = await fetch('/process_yandex_url/', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
            progress.innerText = 'Ссылка успешно обработана!';
            
            if (result.type === 'folder' && result.processed_files) {
                const singleLineCheckbox = document.getElementById('singleLineCheckbox');
                const delimiter = document.getElementById('delimiter').value || '///';
                
                let links = result.processed_files.map(file => {
                    const fullUrl = file.new_url.startsWith('http') ? file.new_url : window.location.origin + file.new_url;
                    return `<a href="${fullUrl}" target="_blank" onclick="copyToClipboard('${fullUrl}', event)">${fullUrl}</a>`;
                });

                let displayText;
                if (singleLineCheckbox.checked) {
                    displayText = links.join(delimiter);
                } else {
                    displayText = links.join('<br>');
                }

                responseDiv.innerHTML = `
                    <div style="margin: 10px 0;">
                        <strong>Оригинальная ссылка:</strong> ${result.original_url}<br>
                        <strong>Обработано файлов:</strong> ${result.total_files}<br>
                        <strong>Новые ссылки:</strong><br>
                        <div style="margin-top: 10px; padding: 10px; background: #f5f5f5; border-radius: 5px; word-break: break-all;">
                            ${displayText}
                        </div>
                    </div>
                `;
            } else {
                const fullUrl = result.new_url.startsWith('http') ? result.new_url : window.location.origin + result.new_url;
                responseDiv.innerHTML = `
                    <div style="margin: 10px 0;">
                        <strong>Оригинальная ссылка:</strong> ${result.original_url}<br>
                        <strong>Новая ссылка:</strong> <a href="${fullUrl}" target="_blank" onclick="copyToClipboard('${fullUrl}', event)">${fullUrl}</a>
                    </div>
                `;
            }
            
            urlInput.value = '';
        } else {
            throw new Error('Не удалось обработать ссылку');
        }

    } catch (error) {
        progress.innerText = 'Ошибка при обработке ссылки';
        responseDiv.innerHTML = `Ошибка: ${error.message}`;
        console.error('Yandex URL processing error:', error);
    }
}
