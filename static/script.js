document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileNameDisplay = document.getElementById('file-name');
    const transcribeBtn = document.getElementById('transcribe-btn');
    const btnText = transcribeBtn.querySelector('.btn-text');
    const loader = transcribeBtn.querySelector('.loader');
    const resultSection = document.getElementById('result-section');
    const resultContent = document.getElementById('result-content');
    const errorMessage = document.getElementById('error-message');
    const copyBtn = document.getElementById('copy-btn');
    const languageSelect = document.getElementById('language');
    const modelSelect = document.getElementById('model-size');

    let currentFile = null;

    // Handle click to select file
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle file selection
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Handle drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            // Simple validation for audio files
            if (file.type.startsWith('audio/') || file.name.match(/\.(m4a|ogg|wav|mp3)$/i)) {
                handleFile(file);
                fileInput.files = e.dataTransfer.files; // Sync input
            } else {
                showError('Proszę wybrać poprawny plik audio.');
            }
        }
    });

    function handleFile(file) {
        currentFile = file;
        fileNameDisplay.textContent = file.name;
        fileNameDisplay.style.color = '#fff';
        transcribeBtn.disabled = false;
        hideError();
        // Hide previous result if new file is selected
        resultSection.classList.add('hidden');
    }

    // Handle transcription start
    transcribeBtn.addEventListener('click', async () => {
        if (!currentFile) return;

        // UI state: Loading
        transcribeBtn.disabled = true;
        btnText.textContent = 'Wysyłanie pliku...';
        loader.classList.remove('hidden');
        resultSection.classList.add('hidden');
        hideError();

        const formData = new FormData();
        formData.append('file', currentFile);
        formData.append('language', languageSelect.value);
        formData.append('model_size', modelSelect.value);

        try {
            const response = await fetch('/transcribe', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Błąd serwera: ${response.status}`);
            }

            const data = await response.json();

            if (data.success && data.task_id) {
                btnText.textContent = 'Przetwarzanie (to może potrwać)...';
                pollStatus(data.task_id);
            } else {
                throw new Error(data.error || 'Wystąpił błąd podczas odbierania zadania.');
            }
        } catch (error) {
            showError(error.message);
            resetUI();
        }
    });

    // Poll status from server
    async function pollStatus(taskId) {
        try {
            const res = await fetch(`/status/${taskId}`);
            const data = await res.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Nieznany błąd podczas pobierania statusu.');
            }

            if (data.status === 'completed') {
                resultContent.textContent = data.text;
                resultSection.classList.remove('hidden');
                resetUI();
            } else if (data.status === 'error') {
                throw new Error(data.error || 'Wystąpił błąd podczas analizy dźwięku na serwerze.');
            } else {
                // status 'pending' or 'processing'
                setTimeout(() => pollStatus(taskId), 3000);
            }
        } catch (error) {
            showError(error.message);
            resetUI();
        }
    }

    function resetUI() {
        transcribeBtn.disabled = false;
        btnText.textContent = 'Transkrybuj';
        loader.classList.add('hidden');
    }

    // Copy to clipboard functionality
    copyBtn.addEventListener('click', async () => {
        const textToCopy = resultContent.textContent;
        if (!textToCopy) return;

        try {
            await navigator.clipboard.writeText(textToCopy);
            
            // Visual feedback
            const originalHTML = copyBtn.innerHTML;
            copyBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
            
            setTimeout(() => {
                copyBtn.innerHTML = originalHTML;
            }, 2000);
        } catch (err) {
            showError('Nie udało się skopiować tekstu.');
        }
    });

    function showError(msg) {
        errorMessage.textContent = msg;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }
});
