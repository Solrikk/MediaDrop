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
        }

        if (elem) {
            document.getElementById('gallery').appendChild(elem);
        }
    }
}

function shortenFilename(filename, maxLength = 10) {
    const ext = filename.slice(filename.lastIndexOf('.'));
    const baseName = filename.slice(0, filename.lastIndexOf('.'));
    return baseName.slice(0, maxLength).replace(/\s/g, '_') + ext;
}

async function uploadFiles() {
    const fileInput = document.getElementById('fileElem');
    const progress = document.getElementById('progress');
    const responseDiv = document.getElementById('response');
    const files = fileInput.files;
    const singleLineCheckbox = document.getElementById('singleLine');
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
        // Read CSV columns
        const reader = new FileReader();
        reader.onload = async (e) => {
            const text = e.target.result;
            const lines = text.split('\n');
            if (lines.length > 0) {
                const headers = lines[0].split(';');
                document.getElementById('csvColumns').value = headers.join(',');
            }
        };
        reader.readAsText(csvFile);

        const columns = await new Promise((resolve) => {
            const modal = document.getElementById('csvModal');
            modal.style.display = 'block';

            document.getElementById('confirmColumns').onclick = () => {
                const columns = document.getElementById('csvColumns').value;
                modal.style.display = 'none';
                resolve(columns);
            };
        });

        if (columns) {
            formData.append('columns', columns);
        }
    }

    if (hasCSV) {
        const columns = document.getElementById('columns').value;
        if (columns) {
            formData.append('columns', columns);
        }
    }

    progress.innerText = 'Uploading... Please wait.';

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
            const fullUrl = window.location.origin + url;
            return `<a href="${fullUrl}" target="_blank" onclick="copyToClipboard('${fullUrl}', event)">${fullUrl} 📋</a>`;
        });

        if (singleLineCheckbox.checked) {
            responseDiv.innerHTML = links.join(delimiter);
        } else {
            responseDiv.innerHTML = links.join('<br>');
        }
    } catch (error) {
        progress.innerText = 'Upload failed.';
        responseDiv.innerHTML = `Error: ${error.message}. Check if S3 credentials are set in Secrets.`;
        console.error('Upload error:', error);
    }
}
