// Redirect to page function
function redirectToPage(url) {
    window.location.href = url;
}

// Upload file function - properly handles file upload to backend
async function setupFileUpload() {
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('uploadedFile');
    const statusEl = document.getElementById('status');
    const extractedTextEl = document.getElementById('extracted-text');
    const generateBtn = document.getElementById('generate-btn');
    
    if (!uploadForm) return; // Exit if not on upload page
    
    let currentDocumentId = null;
    
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Validate file selection
        if (!fileInput.files || fileInput.files.length === 0) {
            statusEl.textContent = "Please select a file to upload";
            statusEl.style.color = "red";
            return;
        }
        
        const file = fileInput.files[0];
        
        // Create FormData
        const formData = new FormData();
        formData.append('file', file);
        
        // Update status
        statusEl.textContent = "Uploading file...";
        statusEl.style.color = "blue";
        
        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok) {
                // Success
                statusEl.textContent = result.message || "Upload successful!";
                statusEl.style.color = "green";
                
                // Store document ID for later use
                currentDocumentId = result.document_id;
                
                // Display extracted text
                if (result.extracted_text) {
                    extractedTextEl.value = result.extracted_text;
                    generateBtn.disabled = false;
                }
                
            } else {
                // Error from server
                statusEl.textContent = result.message || "Upload failed";
                statusEl.style.color = "red";
                
                // Redirect if needed (e.g., to login)
                if (result.redirect) {
                    setTimeout(() => {
                        window.location.href = result.redirect;
                    }, 2000);
                }
            }
            
        } catch (error) {
            // Network error
            statusEl.textContent = "Network error. Please try again.";
            statusEl.style.color = "red";
            console.error("Upload error:", error);
        }
    });
    
    // Generate video button handler
    if (generateBtn) {
        generateBtn.addEventListener('click', async () => {
            if (!currentDocumentId) {
                alert("Please upload a file first");
                return;
            }
            
            statusEl.textContent = "Generating video... This may take a few minutes.";
            statusEl.style.color = "blue";
            generateBtn.disabled = true;
            
            try {
                const formData = new FormData();
                formData.append('document_id', currentDocumentId);
                
                const response = await fetch('/generate-video', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    statusEl.textContent = "Video generated successfully!";
                    statusEl.style.color = "green";
                    
                    // Update video player
                    const videoEl = document.getElementById('generated-video');
                    const videoSrcEl = document.getElementById('generated-video-src');
                    if (videoEl && videoSrcEl) {
                        videoSrcEl.src = result.video_path || `/download-video/${result.id}`;
                        videoEl.load();
                    }
                    
                    // Enable download button
                    const downloadBtn = document.getElementById('download-btn');
                    if (downloadBtn) {
                        downloadBtn.disabled = false;
                        downloadBtn.onclick = () => {
                            window.location.href = `/download-video/${result.id}`;
                        };
                    }
                } else {
                    statusEl.textContent = result.detail || "Video generation failed";
                    statusEl.style.color = "red";
                }
                
            } catch (error) {
                statusEl.textContent = "Error generating video";
                statusEl.style.color = "red";
                console.error("Generation error:", error);
            } finally {
                generateBtn.disabled = false;
            }
        });
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupFileUpload);
} else {
    setupFileUpload();
}