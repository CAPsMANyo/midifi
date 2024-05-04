document.querySelectorAll('.half-button').forEach(button => {
    button.addEventListener('click', function() {
        let siblings = document.querySelectorAll('.half-button');
        siblings.forEach(sib => sib.classList.remove('active'));
        this.classList.add('active');
    });
});

document.querySelector('.left').addEventListener('click', function() {
    togglePopupContent('textInputContent');
});

document.querySelector('.right').addEventListener('click', function() {
    togglePopupContent('fileUploadContent');
});

function togglePopupContent(contentId) {
    var popup = document.getElementById('popup');
    var content = document.getElementById(contentId);

    if (popup.style.display === 'none' || popup.style.width === '0%') {
        // Expand the popup if it's not already expanded
        popup.style.display = 'block';
        setTimeout(() => {
            popup.style.opacity = 1;
            popup.style.width = '65%'; // Target width for expansion
            popup.style.left = '17.5%'; // Adjust left to keep it centered
            fadeInContent(content); // After the popup has expanded, fade in the content
        }, 10);
    } else {
        // If the popup is already visible, switch the content
        switchContent(contentId);
    }
}

function fadeInContent(content) {
    content.style.display = 'block';
    setTimeout(() => {
        content.style.opacity = 1;
    }, 500); // Delay the fade in to synchronize with the width expansion
}

function switchContent(contentId) {
    var contents = document.querySelectorAll('.popup > div');
    contents.forEach(div => {
        if (div.id !== contentId) {
            div.style.opacity = 0; // Fade out other content
            setTimeout(() => div.style.display = 'none', 500); // Hide after fade out
        }
    });
    var activeContent = document.getElementById(contentId);
    activeContent.style.display = 'block';
    setTimeout(() => {
        activeContent.style.opacity = 1;
    }, 500); // Delay the display and fade in of new content
}

function submitText() {
    var text = document.querySelector('#textInputContent input').value;
    alert('You entered: ' + text);
}

function submitFile() {
    alert('File will be uploaded!');
}
