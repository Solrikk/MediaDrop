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
    let fileElem = document.getElementById('fileElem');
    let files = fileElem.files;
    
    if (files.length === 0) {
        responseDiv.innerText = "Please select files!";
        return;
    }

    let formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
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
            const filename = url.split('/').pop();
            const shortenedName = shortenFilename(filename);
            return `<a href="${url}" target="_blank">${shortenedName}</a>`;
        });

        if (singleLineCheckbox.checked) {
            responseDiv.innerHTML = links.join(delimiter);
        } else {
            responseDiv.innerHTML = links.join('<br>');
        }
    } catch (error) {
        progress.innerText = 'Upload failed.';
        responseDiv.innerHTML = `Error: ${error.message}`;
        console.error('Upload error:', error);
    }
}
