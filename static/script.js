let dropArea = document.getElementById('drop-area');
let progress = document.getElementById('progress');
let responseDiv = document.getElementById('response');

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false)
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
    dropArea.addEventListener(eventName, () => dropArea.classList.add('highlight'), false)
});

['dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, () => dropArea.classList.remove('highlight'), false)
});

dropArea.addEventListener('drop', handleDrop, false);

function handleDrop(e) {
    let dt = e.dataTransfer;
    let files = dt.files;

    handleFiles(files);
}

function handleFiles(files) {
    files = [...files];
    files.forEach(previewFile);
    document.getElementById('file-form').files = files;
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
    let form = document.getElementById('file-form');
    let formData = new FormData(form);
    progress.innerText = 'Uploading... Please wait.';

    let response = await fetch('/upload/', {
        method: 'POST',
        body: formData
    });

    let result = await response.json();

    progress.innerText = 'Upload complete.';
    let links = result.file_urls.map(url => `<a href="${url}" target="_blank">${url}</a>`).join('<br>');
    responseDiv.innerHTML = links;
}