document.addEventListener('DOMContentLoaded', function() {
    fetchFiles();
});

function fetchFiles() {
    fetch('/get-files')
        .then(response => response.json())
        .then(data => displayFiles(data))
        .catch(error => console.error('Error loading the files:', error));
}

function displayFiles(files) {
    const filesList = document.getElementById('files-list');
    filesList.innerHTML = ''; // Clear current files list

    files.forEach(file => {
        const listItem = document.createElement('li');
        listItem.textContent = file.name;
        filesList.appendChild(listItem);
    });
}
