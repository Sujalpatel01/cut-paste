document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadContent = document.getElementById('upload-content');
    const originalPreview = document.getElementById('original-preview');
    
    const resultPlaceholder = document.getElementById('result-placeholder');
    const resultPreview = document.getElementById('result-preview');
    const loadingOverlay = document.getElementById('loading-overlay');
    
    const btnRemove = document.getElementById('btn-remove');
    const btnSave = document.getElementById('btn-save');
    const btnClear = document.getElementById('btn-clear');
    const statusText = document.getElementById('status-text');

    let currentFile = null;
    let resultBlobUrl = null;

    // Trigger file input click
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle drag events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drag-over');
        });
    });

    // Handle drop
    dropZone.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files[0];
        handleFile(file);
    });

    // Handle input change
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        handleFile(file);
    });

    function handleFile(file) {
        if (!file) return;
        
        const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/tiff'];
        if (!validTypes.includes(file.type)) {
            alert('Please select a valid image file (JPG, PNG, WebP, etc.)');
            return;
        }

        currentFile = file;
        
        // Show original image
        const reader = new FileReader();
        reader.onload = (e) => {
            originalPreview.src = e.target.result;
            originalPreview.classList.remove('hidden');
            uploadContent.classList.add('hidden');
            
            // Enable/Disable buttons
            btnRemove.disabled = false;
            btnSave.disabled = true;
            btnClear.disabled = false;
            
            // Reset result
            resultPreview.classList.add('hidden');
            resultPlaceholder.classList.remove('hidden');
            if(resultBlobUrl) {
                URL.revokeObjectURL(resultBlobUrl);
                resultBlobUrl = null;
            }

            const mb = (file.size / (1024 * 1024)).toFixed(1);
            statusText.textContent = `Loaded: ${file.name} · ${mb} MB`;
        };
        reader.readAsDataURL(file);
    }

    btnRemove.addEventListener('click', async () => {
        if (!currentFile) return;

        const formData = new FormData();
        formData.append('file', currentFile);

        // UI Feedback
        loadingOverlay.classList.remove('hidden');
        btnRemove.disabled = true;
        btnClear.disabled = true;
        statusText.textContent = '⏳ AI is removing background... this may take a few seconds or a minute.';

        try {
            const response = await fetch('/api/remove-bg', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.statusText}`);
            }

            const blob = await response.blob();
            resultBlobUrl = URL.createObjectURL(blob);
            
            resultPreview.src = resultBlobUrl;
            resultPreview.classList.remove('hidden');
            resultPlaceholder.classList.add('hidden');
            
            btnSave.disabled = false;
            statusText.textContent = '✅ Perfect! Background removed successfully.';

        } catch (error) {
            console.error('Error:', error);
            alert(`Failed to remove background. Ensure the API is running.\nError: ${error.message}`);
            statusText.textContent = '❌ Error processing image. Check server terminal.';
            btnRemove.disabled = false;
        } finally {
            loadingOverlay.classList.add('hidden');
            btnClear.disabled = false;
        }
    });

    btnSave.addEventListener('click', () => {
        if (!resultBlobUrl) return;

        const originalName = currentFile.name.split('.').slice(0, -1).join('.');
        const newName = `${originalName}_no_bg.png`;

        const a = document.createElement('a');
        a.href = resultBlobUrl;
        a.download = newName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        statusText.textContent = `💾 Saved: ${newName}`;
    });

    btnClear.addEventListener('click', () => {
        currentFile = null;
        if(resultBlobUrl) {
            URL.revokeObjectURL(resultBlobUrl);
            resultBlobUrl = null;
        }
        
        originalPreview.src = '';
        originalPreview.classList.add('hidden');
        uploadContent.classList.remove('hidden');
        
        resultPreview.src = '';
        resultPreview.classList.add('hidden');
        resultPlaceholder.classList.remove('hidden');
        
        btnRemove.disabled = true;
        btnSave.disabled = true;
        btnClear.disabled = true;
        
        fileInput.value = '';
        statusText.textContent = 'Upload a photo — 100% perfect background remove';
    });
});
