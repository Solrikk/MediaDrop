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

function handleFiles(files) {
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
        let img = document.createElement('img');
        img.src = reader.result;
        document.getElementById('gallery').appendChild(img);
    }
}

async function uploadFiles() {
    let fileElem = document.getElementById('fileElem');
    let files = fileElem.files;
    if (files.length === 0) {
        responseDiv.innerText = "Please select some files first!";
        return;
    }

    let formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    progress.innerText = 'Uploading...Please wait.';

    let response = await fetch('/upload/', {
        method: 'POST',
        body: formData
    });

    let result = await response.json();

    progress.innerText = 'Upload complete.';
    let links = result.file_urls.map(url => `<a href="${url}" target="_blank">${url}</a>`).join('<br>');
    responseDiv.innerHTML = links;
}