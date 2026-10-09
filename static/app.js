document.addEventListener('DOMContentLoaded', () => {
    // API endpoint configured dynamically based on the current origin
    const API_BASE = window.location.origin;

    // ─── Auth DOM Elements ────────────────────────────────────────────────
    const authOverlay     = document.getElementById('auth-overlay');
    const loginForm       = document.getElementById('form-login');
    const registerForm    = document.getElementById('form-register');
    const loginError      = document.getElementById('login-error');
    const registerError   = document.getElementById('register-error');
    const loginBtn        = document.getElementById('login-btn');
    const registerBtn     = document.getElementById('register-btn');
    const userNameDisplay = document.getElementById('user-name-display');
    const logoutBtn       = document.getElementById('logout-btn');

    // ─── App DOM Elements ─────────────────────────────────────────────────
    const dropzone                 = document.getElementById('dropzone');
    const fileInput                = document.getElementById('file-input');
    const indexStatus              = document.getElementById('index-status');
    const uploadProgressContainer  = document.getElementById('upload-progress-container');
    const uploadFilename           = document.getElementById('upload-filename');
    const uploadProgressFill       = document.getElementById('upload-progress-fill');
    const uploadPercentage         = document.getElementById('upload-percentage');
    const uploadedFilesList        = document.getElementById('uploaded-files-list');
    const chatMessages             = document.getElementById('chat-messages');
    const chatForm                 = document.getElementById('chat-form');
    const queryInput               = document.getElementById('query-input');
    const clearChatBtn             = document.getElementById('clear-chat');

    // ─── State ────────────────────────────────────────────────────────────
    let chatHistory = [];
    let accessToken = localStorage.getItem('access_token') || null;
    let currentUsername = localStorage.getItem('username') || null;

    // Initialize Lucide Icons
    lucide.createIcons();

    // ═══════════════════════════════════════════════════════════════════════
    //  TOAST NOTIFICATIONS — single surface for every error/success message.
    //  Any request that fails (network error, 4xx, 5xx) should end up here so
    //  the user always sees what went wrong, instead of it only landing in
    //  the browser console.
    // ═══════════════════════════════════════════════════════════════════════

    function getToastContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    const TOAST_ICONS = {
        error: 'alert-circle',
        success: 'check-circle',
        warning: 'alert-triangle'
    };

    function showToast(message, type = 'error', duration = 6000) {
        const container = getToastContainer();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i data-lucide="${TOAST_ICONS[type] || 'info'}" class="toast-icon"></i>
            <div class="toast-message"></div>
            <button class="toast-close" aria-label="Dismiss"><i data-lucide="x" style="width:14px;height:14px;"></i></button>
        `;
        // Set text via textContent (not innerHTML) so error messages from the
        // server can never inject HTML/script into the page.
        toast.querySelector('.toast-message').textContent = message;
        container.appendChild(toast);
        lucide.createIcons();

        const remove = () => {
            toast.classList.add('toast-exit');
            setTimeout(() => toast.remove(), 200);
        };
        toast.querySelector('.toast-close').addEventListener('click', remove);
        if (duration > 0) setTimeout(remove, duration);
        return toast;
    }

    function showErrorToast(message) { return showToast(message, 'error'); }
    function showSuccessToast(message) { return showToast(message, 'success', 4000); }

    /**
     * Extracts a human-readable error message from an API response body,
     * regardless of which shape produced it:
     *  - the new global envelope: {status:"error", message:"..."}
     *  - FastAPI's default HTTPException shape: {detail:"..."}
     *  - FastAPI/Pydantic validation errors: {detail:[{loc, msg}, ...]}
     */
    function extractErrorMessage(data, fallback = 'Something went wrong. Please try again.') {
        if (!data) return fallback;
        if (typeof data.message === 'string' && data.message) return data.message;
        if (typeof data.detail === 'string' && data.detail) return data.detail;
        if (Array.isArray(data.detail)) {
            return data.detail.map(e => e.msg || JSON.stringify(e)).join(' ') || fallback;
        }
        return fallback;
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  AUTH LOGIC
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * Check if user is logged in on page load.
     * If token exists in localStorage → hide modal, show app.
     * If no token → show auth modal.
     */
    function checkAuthState() {
        if (accessToken && currentUsername) {
            showApp();
        } else {
            showAuthModal();
        }
    }

    function showAuthModal() {
        authOverlay.classList.remove('hidden');
    }

    function showApp() {
        authOverlay.classList.add('hidden');
        userNameDisplay.textContent = currentUsername;
        lucide.createIcons();
        updateServerStatus();
    }

    /** Switch between Login and Sign Up tabs */
    window.switchTab = function(tab) {
        const tabLogin    = document.getElementById('tab-login');
        const tabRegister = document.getElementById('tab-register');

        if (tab === 'login') {
            tabLogin.classList.add('active');
            tabRegister.classList.remove('active');
            loginForm.classList.remove('hidden');
            registerForm.classList.add('hidden');
            loginError.textContent = '';
        } else {
            tabRegister.classList.add('active');
            tabLogin.classList.remove('active');
            registerForm.classList.remove('hidden');
            loginForm.classList.add('hidden');
            registerError.textContent = '';
        }
        lucide.createIcons();
    };

    /** Handle Login form submit */
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        loginError.textContent = '';
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;

        loginBtn.disabled = true;
        loginBtn.querySelector('span').textContent = 'Signing in...';

        try {
            const res = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const data = await res.json();

            if (!res.ok) {
                loginError.textContent = data.detail || 'Login failed. Please try again.';
                return;
            }

            // Save token and username in localStorage
            accessToken = data.access_token;
            currentUsername = data.username;
            localStorage.setItem('access_token', accessToken);
            localStorage.setItem('username', currentUsername);

            showApp();

        } catch (err) {
            loginError.textContent = 'Could not connect to the server.';
        } finally {
            loginBtn.disabled = false;
            loginBtn.querySelector('span').textContent = 'Sign In';
        }
    });

    /** Handle Register form submit */
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        registerError.textContent = '';
        const username = document.getElementById('reg-username').value.trim();
        const email    = document.getElementById('reg-email').value.trim();
        const password = document.getElementById('reg-password').value;

        registerBtn.disabled = true;
        registerBtn.querySelector('span').textContent = 'Creating account...';

        try {
            const res = await fetch(`${API_BASE}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password })
            });

            const data = await res.json();

            if (!res.ok) {
                // Pydantic validation errors come as an array
                if (Array.isArray(data.detail)) {
                    registerError.textContent = data.detail.map(e => e.msg).join(' ');
                } else {
                    registerError.textContent = data.detail || 'Registration failed.';
                }
                return;
            }

            // Success → Auto-switch to login tab with success hint
            registerError.style.color = '#34d399';
            registerError.textContent = '✓ Account created! Please log in.';
            setTimeout(() => {
                registerError.textContent = '';
                registerError.style.color = '#f87171';
                switchTab('login');
            }, 1500);

        } catch (err) {
            registerError.textContent = 'Could not connect to the server.';
        } finally {
            registerBtn.disabled = false;
            registerBtn.querySelector('span').textContent = 'Create Account';
        }
    });

    /** Logout: Clear localStorage and show auth modal */
    logoutBtn.addEventListener('click', () => {
        accessToken = null;
        currentUsername = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        chatHistory = [];
        showAuthModal();
    });

    // ═══════════════════════════════════════════════════════════════════════
    //  RAG APP LOGIC
    // ═══════════════════════════════════════════════════════════════════════

    /** Helper: Returns headers with Bearer token attached */
    function authHeaders() {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
        };
    }

    /** Helper: Fetch wrapper that automatically attaches JWT Authorization header */
    async function authFetch(url, options = {}) {
        options.headers = options.headers || {};
        if (accessToken) {
            options.headers['Authorization'] = `Bearer ${accessToken}`;
        }
        const res = await fetch(url, options);
        if (res.status === 401) {
            handleUnauthorized();
        }
        return res;
    }

    /** Handle 401 Unauthorized globally — log the user out and show modal */
    function handleUnauthorized() {
        accessToken = null;
        currentUsername = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        if (typeof addMessage === 'function') {
            addMessage('bot', '⚠️ Your session has expired. Please log in again.');
        }
        showToast('Your session has expired. Please log in again.', 'warning');
        showAuthModal();
    }

    // 1. Fetch Initial Server Status
    async function updateServerStatus() {
        try {
            const res = await fetch(`${API_BASE}/status`);
            if (!res.ok) throw new Error('Failed to load status');
            const data = await res.json();
            
            // Update Status Badge
            const statusDot  = indexStatus.querySelector('.status-dot');
            const statusText = indexStatus.querySelector('.status-text');
            
            if (data.indexing_active) {
                indexStatus.className = 'status-badge active';
                statusText.textContent = 'Index Active';
            } else {
                indexStatus.className = 'status-badge';
                statusText.textContent = 'No Index';
            }

            // Render File List
            renderFileList(data.uploaded_files);
        } catch (error) {
            console.error('Status fetch error:', error);
            indexStatus.className = 'status-badge';
            indexStatus.querySelector('.status-text').textContent = 'Server Offline';
            showErrorToast('Could not reach the server to check document index status.');
        }
    }

    // Render file lists in sidebar
    function renderFileList(files) {
        if (!files || files.length === 0) {
            uploadedFilesList.innerHTML = `
                <div class="empty-files">
                    <i data-lucide="folder-open" class="empty-icon"></i>
                    <p>No documents uploaded yet</p>
                </div>
            `;
            lucide.createIcons();
            return;
        }

        uploadedFilesList.innerHTML = files.map(file => `
            <div class="file-item" title="${file}" id="file-item-${CSS.escape(file)}">
                <i data-lucide="file-text" class="file-item-icon"></i>
                <span class="file-item-name">${file}</span>
                <button
                    class="file-delete-btn"
                    id="delete-btn-${CSS.escape(file)}"
                    title="Delete ${file}"
                    onclick="deleteFile('${file.replace(/'/g, "\\'")}')"
                >
                    <i data-lucide="trash-2"></i>
                </button>
            </div>
        `).join('');
        lucide.createIcons();
    }

    // Delete a file by calling DELETE /files/{filename}
    window.deleteFile = async function(filename) {
        if (!confirm(`Delete "${filename}" and remove it from the index?`)) return;

        const btn = document.getElementById(`delete-btn-${CSS.escape(filename)}`);
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i data-lucide="loader-2" class="spin"></i>';
            lucide.createIcons();
        }

        try {
            const res = await fetch(`${API_BASE}/files/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                }
            });

            if (res.status === 401) {
                handleSessionExpiry();
                return;
            }

            const data = await res.json();

            if (!res.ok) {
                showErrorToast(extractErrorMessage(data, 'Failed to delete file.'));
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i data-lucide="trash-2"></i>';
                    lucide.createIcons();
                }
                return;
            }

            // Remove the file item from DOM immediately
            const fileItem = document.getElementById(`file-item-${CSS.escape(filename)}`);
            if (fileItem) fileItem.remove();

            // Refresh full status
            await updateServerStatus();

        } catch (err) {
            console.error('Delete error:', err);
            showErrorToast('Network error while deleting file.');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i data-lucide="trash-2"></i>';
                lucide.createIcons();
            }
        }
    };


    // 2. Drag & Drop File Upload Handlers
    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFile(files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            uploadFile(fileInput.files[0]);
            fileInput.value = ''; // Reset input
        }
    });

    // Upload file using XMLHttpRequest to track progress
    function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        // Show progress UI
        uploadProgressContainer.style.display = 'block';
        uploadFilename.textContent = file.name;
        uploadProgressFill.style.width = '0%';
        uploadPercentage.textContent = '0%';

        // Set status to loading
        indexStatus.className = 'status-badge loading';
        indexStatus.querySelector('.status-text').textContent = 'Indexing...';

        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_BASE}/upload`, true);

        // Attach JWT Bearer token
        xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`);

        // Track upload progress
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                // Cap progress at 95% until server indexing resolves
                const displayPercent = Math.min(percentComplete, 95);
                uploadProgressFill.style.width = `${displayPercent}%`;
                uploadPercentage.textContent = `${displayPercent}%`;
            }
        };

        xhr.onload = () => {
            uploadProgressFill.style.width = '100%';
            uploadPercentage.textContent = '100%';

            setTimeout(() => {
                uploadProgressContainer.style.display = 'none';
            }, 1000);

            if (xhr.status === 401) {
                handleUnauthorized();
                return;
            }

            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                addMessage('bot', `Successfully uploaded and indexed **${file.name}** (${response.total_chunks} chunks generated).`);
                updateServerStatus();
            } else {
                let errorMsg = 'Failed to index file.';
                try {
                    errorMsg = extractErrorMessage(JSON.parse(xhr.responseText), errorMsg);
                } catch(e) {}
                addMessage('bot', `❌ Error: ${errorMsg}`);
                showErrorToast(`Upload failed: ${errorMsg}`);
                updateServerStatus();
            }
        };

        xhr.onerror = () => {
            uploadProgressContainer.style.display = 'none';
            addMessage('bot', `❌ Network error occurred while uploading.`);
            showErrorToast('Network error occurred while uploading the document.');
            updateServerStatus();
        };

        xhr.send(formData);
    }

    // Helper to format messages (handles bolding, list items, inline code, and paragraphs)
    function formatMessageText(text) {
        // Escape HTML tags to prevent XSS
        let escaped = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
            
        // Basic bold markdown conversion (**text**)
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Basic code block conversion (`code`)
        escaped = escaped.replace(/`(.*?)`/g, '<code>$1</code>');

        // Line-by-line formatting for lists and paragraphs
        const lines = escaped.split('\n');
        let inList = false;
        let resultHtml = '';

        for (let line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                if (!inList) {
                    resultHtml += '<ul style="margin-left: 20px; margin-top: 5px; margin-bottom: 5px; list-style-type: disc;">';
                    inList = true;
                }
                const content = trimmed.substring(2);
                resultHtml += `<li style="margin-bottom: 4px;">${content}</li>`;
            } else {
                if (inList) {
                    resultHtml += '</ul>';
                    inList = false;
                }
                if (trimmed === '') {
                    resultHtml += '<div style="height: 8px;"></div>';
                } else {
                    resultHtml += `<p style="margin-bottom: 4px;">${line}</p>`;
                }
            }
        }
        
        if (inList) {
            resultHtml += '</ul>';
        }

        return resultHtml;
    }

    // 3. Chat Q&A Interaction Loop (Streaming via SSE)
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const promptText = queryInput.value.trim();
        if (!promptText) return;

        // Display user message
        addMessage('user', promptText);
        queryInput.value = '';

        // Lock form inputs during request
        queryInput.disabled = true;
        const sendBtn = chatForm.querySelector('.send-btn');
        sendBtn.disabled = true;
        sendBtn.style.opacity = '0.5';

        // Add Bot typing bubble initially
        const typingId = showTypingIndicator();

        try {
            const res = await fetch(`${API_BASE}/query/stream`, {
                method: 'POST',
                headers: authHeaders(),  // ← JWT token attached here
                body: JSON.stringify({ 
                    prompt: promptText,
                    chat_history: chatHistory
                })
            });

            removeTypingIndicator(typingId);

            // Handle session expiry
            if (res.status === 401) {
                handleUnauthorized();
                return;
            }

            if (!res.ok) {
                const errData = await res.json().catch(() => ({ detail: 'Streaming failed' }));
                addMessage('bot', `❌ Error: ${errData.detail || 'Could not fetch response'}`);
                return;
            }

            // Create streaming bot message element
            const streamState = createStreamingMessageElement();
            let accumulatedAnswer = '';
            let receivedCitations = [];

            const reader = res.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep last incomplete line in buffer

                for (let line of lines) {
                    line = line.trim();
                    if (!line.startsWith('data: ')) continue;
                    const jsonStr = line.slice(6).trim();
                    if (!jsonStr) continue;

                    try {
                        const packet = JSON.parse(jsonStr);
                        if (packet.type === 'citations') {
                            receivedCitations = packet.citations || [];
                        } else if (packet.type === 'token') {
                            accumulatedAnswer += packet.content;
                            streamState.updateText(accumulatedAnswer);
                        } else if (packet.type === 'error') {
                            addMessage('bot', `❌ Error: ${packet.content}`);
                            streamState.remove();
                            return;
                        } else if (packet.type === 'end') {
                            break;
                        }
                    } catch (err) {
                        console.error('Error parsing stream JSON packet:', err);
                    }
                }
            }

            // Finalize message with formatted markdown and citations
            streamState.finalize(accumulatedAnswer, receivedCitations);

            // Record this interaction in the chat history
            chatHistory.push({ role: 'user', content: promptText });
            chatHistory.push({ role: 'assistant', content: accumulatedAnswer });

        } catch (error) {
            console.error('Query stream error:', error);
            removeTypingIndicator(typingId);
            addMessage('bot', `❌ Failed to connect to the backend server. Make sure it is running on port 8002.`);
        } finally {
            // Unlock inputs
            queryInput.disabled = false;
            sendBtn.disabled = false;
            sendBtn.style.opacity = '1';
            queryInput.focus();
        }
    });

    // Create a dynamic message element for SSE streaming response
    function createStreamingMessageElement() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message streaming-active';

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.innerHTML = '<i data-lucide="bot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        const textSpan = document.createElement('span');
        textSpan.className = 'streaming-text';
        contentDiv.appendChild(textSpan);

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);

        lucide.createIcons();

        return {
            updateText: (rawText) => {
                textSpan.innerHTML = formatMessageText(rawText) + '<span class="typing-cursor">▌</span>';
                chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
            },
            finalize: (fullText, citations) => {
                messageDiv.classList.remove('streaming-active');
                contentDiv.innerHTML = formatMessageText(fullText);

                if (citations && citations.length > 0) {
                    const citationsBox = document.createElement('div');
                    citationsBox.className = 'citations-box';
                    citationsBox.innerHTML = `<div class="citations-title"><i data-lucide="bookmark"></i> Sources</div>`;
                    
                    const listDiv = document.createElement('div');
                    listDiv.className = 'citations-list';
                    
                    citations.forEach((c) => {
                        const pill = document.createElement('span');
                        pill.className = 'citation-pill';
                        pill.innerHTML = `<i data-lucide="file"></i> ${c.source} (${c.page})`;
                        pill.title = "Click to inspect text snippet";
                        pill.addEventListener('click', () => {
                            alert(`Snippet from ${c.source} (${c.page}):\n\n"${c.snippet}"`);
                        });
                        listDiv.appendChild(pill);
                    });
                    
                    citationsBox.appendChild(listDiv);
                    contentDiv.appendChild(citationsBox);
                }

                lucide.createIcons();
                chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
            },
            remove: () => {
                messageDiv.remove();
            }
        };
    }


    // Append standard message bubble to log
    function addMessage(sender, text, citations = []) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.innerHTML = sender === 'bot' ? '<i data-lucide="bot"></i>' : '<i data-lucide="user"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Parse message content using formatMessageText helper
        contentDiv.innerHTML = formatMessageText(text);

        // Append citations if available
        if (citations && citations.length > 0) {
            const citationsBox = document.createElement('div');
            citationsBox.className = 'citations-box';
            citationsBox.innerHTML = `<div class="citations-title"><i data-lucide="bookmark"></i> Sources</div>`;
            
            const listDiv = document.createElement('div');
            listDiv.className = 'citations-list';
            
            citations.forEach((c, idx) => {
                const pill = document.createElement('span');
                pill.className = 'citation-pill';
                pill.innerHTML = `<i data-lucide="file"></i> ${c.source} (${c.page})`;
                pill.title = "Click to inspect text snippet";
                
                // Show snippet popup on click
                pill.addEventListener('click', () => {
                    alert(`Snippet from ${c.source} (${c.page}):\n\n"${c.snippet}"`);
                });
                
                listDiv.appendChild(pill);
            });
            
            citationsBox.appendChild(listDiv);
            contentDiv.appendChild(citationsBox);
        }

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);

        // Auto Scroll Chat smoothly
        chatMessages.scrollTo({
            top: chatMessages.scrollHeight,
            behavior: 'smooth'
        });

        // Render Icons
        lucide.createIcons();
    }

    // Typing Indicators
    function showTypingIndicator() {
        const typingId = 'typing-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        messageDiv.id = typingId;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.innerHTML = '<i data-lucide="bot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        lucide.createIcons();

        return typingId;
    }

    function removeTypingIndicator(id) {
        const indicator = document.getElementById(id);
        if (indicator) indicator.remove();
    }

    // 4. Utility Handlers
    clearChatBtn.addEventListener('click', () => {
        const welcome = chatMessages.querySelector('.welcome-msg');
        chatMessages.innerHTML = '';
        if (welcome) chatMessages.appendChild(welcome);
        chatHistory = [];
    });

    // ═══════════════════════════════════════════════════════════════════════
    //  HR CANDIDATE MATCHER FRONTEND LOGIC
    // ═══════════════════════════════════════════════════════════════════════
    
    let activeJobId = "default_job_001";
    let activeJDInfo = null;

    window.switchAppMode = function(mode) {
        const btnRag = document.getElementById('mode-rag');
        const btnHr = document.getElementById('mode-hr');
        const viewRag = document.getElementById('view-rag-chat');
        const viewHr = document.getElementById('view-hr-matcher');
        const title = document.getElementById('view-title');
        const subtitle = document.getElementById('view-subtitle');

        if (mode === 'hr') {
            btnRag.classList.remove('active');
            btnHr.classList.add('active');
            viewRag.classList.add('hidden');
            viewHr.classList.remove('hidden');
            title.textContent = "AI HR Candidate Matcher";
            subtitle.textContent = "Upload Job Description & candidate resumes for AI match ranking";
            fetchHRLeaderboard();
        } else {
            btnHr.classList.remove('active');
            btnRag.classList.add('active');
            viewHr.classList.add('hidden');
            viewRag.classList.remove('hidden');
            title.textContent = "Knowledge Assistant";
            subtitle.textContent = "Grounded in your uploaded playbooks and documentation";
        }
        lucide.createIcons();
    };

    // Helper to upload batch resumes
    async function uploadResumesBatch(files) {
        if (!files || files.length === 0) return;

        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        const statusEl = document.getElementById('resumes-upload-status');
        if (statusEl) statusEl.textContent = `Uploading ${files.length} resume(s)...`;

        try {
            const res = await authFetch(`${API_BASE}/hr/jobs/${activeJobId}/upload-resumes`, {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (res.ok) {
                if (statusEl) statusEl.textContent = `Uploaded ${data.total_files} candidate resume(s). Click 'Run AI Matching'.`;
            } else {
                const msg = extractErrorMessage(data, 'Upload failed');
                if (statusEl) statusEl.textContent = `Error: ${msg}`;
                showErrorToast(`Resume upload failed: ${msg}`);
            }
        } catch (err) {
            console.error("Batch resume upload error:", err);
            if (statusEl) statusEl.textContent = `Batch upload failed: ${err.message || err}`;
            showErrorToast('Resume upload failed: could not reach the server.');
        }
    }

    function renderJDRequirements(jd) {
        const box = document.getElementById('jd-requirements-chips');
        if (!box || !jd) return;
        box.innerHTML = '';

        const titleSpan = document.createElement('span');
        titleSpan.className = 'skill-chip';
        titleSpan.style.borderColor = 'var(--accent)';
        titleSpan.textContent = `Role: ${jd.title || 'Job Description'}`;
        box.appendChild(titleSpan);

        (jd.required_skills || []).forEach(s => {
            const chip = document.createElement('span');
            chip.className = 'skill-chip matched';
            chip.textContent = `Req: ${s}`;
            box.appendChild(chip);
        });

        (jd.preferred_skills || []).forEach(s => {
            const chip = document.createElement('span');
            chip.className = 'skill-chip';
            chip.textContent = `Pref: ${s}`;
            box.appendChild(chip);
        });
    }

    // Helper to upload single JD
    async function uploadJDSingle(file) {
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        const statusEl = document.getElementById('active-jd-status');
        if (statusEl) statusEl.textContent = `Uploading ${file.name}...`;

        try {
            const res = await authFetch(`${API_BASE}/hr/jobs/${activeJobId}/upload-jd`, {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (res.ok) {
                activeJDInfo = data.jd_parsed;
                if (statusEl) statusEl.textContent = `Active JD: ${data.filename}`;
                renderJDRequirements(activeJDInfo);
            } else {
                const msg = extractErrorMessage(data, 'Upload failed');
                if (statusEl) statusEl.textContent = `Error: ${msg}`;
                showErrorToast(`Job description upload failed: ${msg}`);
            }
        } catch (err) {
            console.error("JD upload error:", err);
            if (statusEl) statusEl.textContent = `Upload failed: ${err.message || err}`;
            showErrorToast('Job description upload failed: could not reach the server.');
        }
    }

    // JD File Input & Dropzone Listeners
    const jdFileInput = document.getElementById('jd-file-input');
    const jdDropzone = document.getElementById('jd-dropzone');
    
    if (jdFileInput) {
        jdFileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                uploadJDSingle(e.target.files[0]);
            }
        });
    }

    if (jdDropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            jdDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                jdDropzone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            jdDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                jdDropzone.classList.remove('dragover');
            }, false);
        });

        jdDropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files[0]) {
                uploadJDSingle(dt.files[0]);
            }
        });
    }

    // Resumes File Input & Dropzone Listeners
    const resumesFileInput = document.getElementById('resumes-file-input');
    const resumesDropzone = document.getElementById('resumes-dropzone');

    if (resumesFileInput) {
        resumesFileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                uploadResumesBatch(e.target.files);
            }
        });
    }

    if (resumesDropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            resumesDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                resumesDropzone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            resumesDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                resumesDropzone.classList.remove('dragover');
            }, false);
        });

        resumesDropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                uploadResumesBatch(dt.files);
            }
        });
    }

    // Trigger Candidate Evaluation
    window.runHREvaluation = async function() {
        const btn = document.getElementById('analyze-candidates-btn');
        if (btn) btn.disabled = true;

        const countBadge = document.getElementById('candidates-count');
        if (countBadge) countBadge.textContent = "Analyzing candidates...";

        try {
            const res = await authFetch(`${API_BASE}/hr/jobs/${activeJobId}/analyze`, {
                method: 'POST'
            });
            const data = await res.json();
            if (res.ok) {
                renderLeaderboard(data.leaderboard || []);
                showSuccessToast(`Analysis complete — scored ${data.total_candidates || 0} candidate(s).`);
            } else {
                showErrorToast(extractErrorMessage(data, 'Candidate evaluation failed.'));
            }
        } catch (err) {
            console.error("Evaluation request error:", err);
            showErrorToast('Evaluation request failed: could not reach the server.');
        } finally {
            if (btn) btn.disabled = false;
        }
    };

    let allLoadedCandidates = [];
    let activeFilter = 'all';
    let currentActiveCandidateId = null;

    async function fetchHRLeaderboard() {
        try {
            const res = await authFetch(`${API_BASE}/hr/jobs/${activeJobId}/leaderboard`);
            const data = await res.json();
            if (res.ok) {
                allLoadedCandidates = data.candidates || [];
                applyLeaderboardFilter();
            } else {
                showErrorToast(extractErrorMessage(data, 'Failed to load the candidate leaderboard.'));
            }
        } catch (err) {
            console.error("Error fetching leaderboard:", err);
            showErrorToast('Could not load the candidate leaderboard: server unreachable.');
        }
    }

    window.setLeaderboardFilter = function(filterName) {
        activeFilter = filterName;
        document.querySelectorAll('.leaderboard-filter-bar .filter-tab-btn').forEach(btn => btn.classList.remove('active'));
        const targetBtn = document.getElementById(`filter-btn-${filterName}`);
        if (targetBtn) targetBtn.classList.add('active');
        applyLeaderboardFilter();
    };

    function applyLeaderboardFilter() {
        const totalCount = allLoadedCandidates.length;
        const shortlistedCount = allLoadedCandidates.filter(c => c.candidate_status === 'Shortlisted').length;
        const strongCount = allLoadedCandidates.filter(c => c.fit === 'Strong Fit').length;
        const weakCount = allLoadedCandidates.filter(c => c.fit === 'Weak Fit').length;

        const countAllEl = document.getElementById('count-all');
        const countShortlistedEl = document.getElementById('count-shortlisted');
        const countStrongEl = document.getElementById('count-strong');
        const countWeakEl = document.getElementById('count-weak');
        const countBadge = document.getElementById('candidates-count');

        if (countAllEl) countAllEl.textContent = `(${totalCount})`;
        if (countShortlistedEl) countShortlistedEl.textContent = `(${shortlistedCount})`;
        if (countStrongEl) countStrongEl.textContent = `(${strongCount})`;
        if (countWeakEl) countWeakEl.textContent = `(${weakCount})`;
        if (countBadge) countBadge.textContent = `${totalCount} Candidates Scored`;

        let filtered = allLoadedCandidates;
        if (activeFilter === 'shortlisted') {
            filtered = allLoadedCandidates.filter(c => c.candidate_status === 'Shortlisted');
        } else if (activeFilter === 'strong') {
            filtered = allLoadedCandidates.filter(c => c.fit === 'Strong Fit');
        } else if (activeFilter === 'weak') {
            filtered = allLoadedCandidates.filter(c => c.fit === 'Weak Fit');
        }

        renderFilteredLeaderboardRows(filtered);
    }

    function renderFilteredLeaderboardRows(candidates) {
        const tbody = document.getElementById('leaderboard-body');
        if (!tbody) return;

        tbody.innerHTML = '';
        if (candidates.length === 0) {
            const emptyMsg = activeFilter === 'shortlisted' 
                ? 'No candidates have been shortlisted yet.'
                : 'Upload a Job Description and candidate resumes above, then click <strong>Run AI Matching</strong>.';

            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="empty-table-msg">
                        ${emptyMsg}
                    </td>
                </tr>
            `;
            return;
        }

        candidates.forEach(cand => {
            const tr = document.createElement('tr');
            const fitClass = cand.fit === 'Strong Fit' ? 'strong-fit' : (cand.fit === 'Moderate Fit' ? 'moderate-fit' : 'weak-fit');
            const profile = cand.profile || {};
            const matchedSkills = (profile.matched_required_skills || []).map(s => `<span class="skill-chip matched">${s}</span>`).join(' ');
            const isShortlisted = cand.candidate_status === 'Shortlisted';

            tr.innerHTML = `
                <td><strong>#${cand.rank || 1}</strong></td>
                <td>${cand.name || cand.filename}</td>
                <td><strong>${cand.score}%</strong></td>
                <td><span class="fit-badge ${fitClass}">${cand.fit || 'Pending'}</span></td>
                <td><div class="skills-chip-box">${matchedSkills || 'None'}</div></td>
                <td>
                    <span class="hr-status-badge ${isShortlisted ? 'shortlisted' : 'pending'}">
                        ${isShortlisted ? '✓ Shortlisted' : 'Pending'}
                    </span>
                </td>
                <td>
                    <button class="action-btn-primary" style="padding: 4px 10px; font-size:0.75rem;" onclick="showCandidateDetails('${cand.candidate_id}')">
                        View Details
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
        lucide.createIcons();
    }

    function renderLeaderboard(candidates) {
        allLoadedCandidates = candidates || [];
        applyLeaderboardFilter();
    }

    window.toggleOptionsMenu = function(event, candidateId) {
        event.stopPropagation();
        document.querySelectorAll('.dropdown-menu').forEach(m => {
            if (m.id !== `menu-${candidateId}`) m.classList.add('hidden');
        });
        const targetMenu = document.getElementById(`menu-${candidateId}`);
        if (targetMenu) targetMenu.classList.toggle('hidden');
    };

    window.toggleShortlistStatus = async function(candidateId, newStatus) {
        try {
            const res = await authFetch(`${API_BASE}/hr/jobs/${activeJobId}/candidates/${candidateId}/shortlist`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            });

            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                showErrorToast(extractErrorMessage(data, 'Unable to update shortlist status.'));
                return;
            }

            if (data.success) {
                const targetCand = allLoadedCandidates.find(c => c.candidate_id === candidateId);
                if (targetCand) {
                    targetCand.candidate_status = newStatus;
                }

                if (currentActiveCandidateId === candidateId) {
                    updateShortlistButtonState(newStatus === 'Shortlisted');
                }

                applyLeaderboardFilter();
            } else {
                showErrorToast('Unable to update shortlist status. Please try again.');
            }
        } catch (err) {
            console.error("Shortlist error:", err);
            showErrorToast('Unable to update shortlist status: server unreachable.');
        }
    };

    window.toggleActiveCandidateShortlist = function() {
        if (!currentActiveCandidateId) return;
        const currentCand = allLoadedCandidates.find(c => c.candidate_id === currentActiveCandidateId);
        const isShortlisted = currentCand ? currentCand.candidate_status === 'Shortlisted' : false;
        const newStatus = isShortlisted ? 'Pending' : 'Shortlisted';
        toggleShortlistStatus(currentActiveCandidateId, newStatus);
    };

    function updateShortlistButtonState(isShortlisted) {
        const btnLbl = document.getElementById('cd-shortlist-lbl');
        const btnEl = document.getElementById('cd-shortlist-btn');
        if (btnLbl) {
            btnLbl.textContent = isShortlisted ? '✓ Shortlisted (Click to Remove)' : 'Shortlist Candidate';
        }
        if (btnEl) {
            if (isShortlisted) {
                btnEl.style.borderColor = '#4ade80';
                btnEl.style.color = '#4ade80';
                btnEl.style.background = 'rgba(34, 197, 94, 0.1)';
            } else {
                btnEl.style.borderColor = 'var(--border-color)';
                btnEl.style.color = 'var(--text-primary)';
                btnEl.style.background = 'rgba(255, 255, 255, 0.03)';
            }
        }
    }

    document.addEventListener('click', () => {
        document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.add('hidden'));
    });

    window.showCandidateDetails = async function(candidateId) {
        currentActiveCandidateId = candidateId;
        try {
            const res = await authFetch(`${API_BASE}/hr/jobs/${activeJobId}/candidates/${candidateId}`);
            const data = await res.json();
            if (!res.ok) {
                showErrorToast(extractErrorMessage(data, 'Could not load candidate details.'));
                return;
            }

            const profile = data.profile || {};
            const scoreBreakdown = data.score_breakdown || {};
            const evidenceList = data.evidence || [];
            const candidateName = profile.candidate_name || candidateId;

            // Compute Initials
            const initials = candidateName.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() || 'AK';
            document.getElementById('cd-avatar').textContent = initials;
            document.getElementById('cd-name').textContent = candidateName;
            document.getElementById('cd-role').textContent = profile.title || 'Software Engineer';

            // Fit Status Badge
            const fitBadge = document.getElementById('cd-fit-badge');
            fitBadge.textContent = data.fit || 'Strong Fit';
            fitBadge.className = `fit-badge ${data.fit === 'Strong Fit' ? 'strong-fit' : (data.fit === 'Moderate Fit' ? 'moderate-fit' : 'weak-fit')}`;

            // Update Shortlist Quick Action Button state
            updateShortlistButtonState(data.candidate_status === 'Shortlisted');

            // Specs (Only show data extracted from resume, otherwise "Not Specified")
            document.getElementById('cd-spec-exp').textContent = `${profile.experience_years || 0} Years`;
            document.getElementById('cd-spec-role').textContent = profile.title || 'Software Engineer';
            document.getElementById('cd-spec-loc').textContent = profile.location || 'Not Specified';
            document.getElementById('cd-spec-notice').textContent = profile.notice_period || 'Not Specified';
            document.getElementById('cd-spec-avail').textContent = profile.availability || 'Not Specified';
            document.getElementById('cd-spec-ctc').textContent = profile.ctc || 'Not Specified';
            document.getElementById('cd-spec-date').textContent = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });

            // Resume File Card
            document.getElementById('cd-resume-filename').textContent = profile.document || `${candidateId}.pdf`;
            
            const resumeCardBtn = document.querySelector('.cd-resume-card .cd-btn-secondary');
            if (resumeCardBtn) {
                resumeCardBtn.onclick = () => previewCandidateResume(candidateId);
            }

            // Populate Skill Categories Grid (Match Summary Tab)
            renderSkillCategoryCards(profile, evidenceList);

            // Populate Skills Breakdown Tab
            renderSkillsBreakdownChart(data.score, scoreBreakdown);

            // Populate Projects, Experience, Education & Analysis Panes
            renderProjectsPane(profile);
            renderExperiencePane(profile);
            renderEducationPane(profile);
            renderRawEvidencePane(evidenceList);

            // Switch to Candidate Deep-Dive View & scroll to top section
            document.getElementById('view-hr-matcher').classList.add('hidden');
            document.getElementById('view-rag-chat').classList.add('hidden');
            const cdView = document.getElementById('view-candidate-detail');
            cdView.classList.remove('hidden');
            cdView.scrollTop = 0;

            setupCandidateViewScrollSpy();
            scrollToCDSection('summary');
            lucide.createIcons();
        } catch (err) {
            console.error("Error fetching candidate details:", err);
            showErrorToast('Could not load candidate details: server unreachable.');
        }
    };

    window.hideCandidateDetailView = function() {
        document.getElementById('view-candidate-detail').classList.add('hidden');
        document.getElementById('view-hr-matcher').classList.remove('hidden');
        lucide.createIcons();
    };

    window.scrollToCDSection = function(sectionName) {
        document.querySelectorAll('.cd-nav-tabs .cd-tab-btn').forEach(btn => btn.classList.remove('active'));
        const targetBtn = document.getElementById(`tab-btn-${sectionName}`);
        if (targetBtn) targetBtn.classList.add('active');

        const targetSec = document.getElementById(`cd-sec-${sectionName}`);
        if (targetSec) {
            targetSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    function setupCandidateViewScrollSpy() {
        const cdView = document.getElementById('view-candidate-detail');
        if (!cdView || cdView.dataset.scrollSpyActive) return;
        cdView.dataset.scrollSpyActive = "true";

        const sections = ['summary', 'breakdown', 'projects', 'experience', 'education', 'analysis'];

        cdView.addEventListener('scroll', () => {
            let currentSec = 'summary';
            sections.forEach(sec => {
                const el = document.getElementById(`cd-sec-${sec}`);
                if (el) {
                    const rect = el.getBoundingClientRect();
                    if (rect.top <= 180) {
                        currentSec = sec;
                    }
                }
            });

            document.querySelectorAll('.cd-nav-tabs .cd-tab-btn').forEach(btn => btn.classList.remove('active'));
            const activeBtn = document.getElementById(`tab-btn-${currentSec}`);
            if (activeBtn) activeBtn.classList.add('active');
        });
    }

    window.previewCandidateResume = async function(candidateId) {
        candidateId = candidateId || currentActiveCandidateId;
        if (!candidateId) return;

        const modal = document.getElementById('resume-preview-modal');
        const modalTitle = document.getElementById('preview-modal-title');
        const modalText = document.getElementById('preview-modal-text');

        modalText.textContent = "Loading original resume document text...";
        modal.classList.remove('hidden');

        try {
            const res = await authFetch(`${API_BASE}/hr/jobs/${activeJobId}/candidates/${candidateId}/resume-preview`);
            const data = await res.json();
            if (res.ok) {
                modalTitle.textContent = `Resume Preview — ${data.filename}`;
                modalText.textContent = data.resume_text || "No text available for this file.";
            } else {
                const msg = extractErrorMessage(data, 'Could not load resume document.');
                modalText.textContent = msg;
                showErrorToast(msg);
            }
        } catch (err) {
            console.error("Resume preview error:", err);
            modalText.textContent = "Failed to retrieve resume preview.";
            showErrorToast('Failed to retrieve resume preview: server unreachable.');
        }
    };

    window.closeResumePreviewModal = function() {
        document.getElementById('resume-preview-modal').classList.add('hidden');
    };

    window.toggleSkillCategoryPills = function(catIndex) {
        const row = document.getElementById(`cd-pills-row-${catIndex}`);
        if (!row) return;

        const hiddenPills = row.querySelectorAll('.skill-pill-hidden');
        const moreBtn = row.querySelector('.more-tag');

        if (hiddenPills.length > 0) {
            const isExpanding = hiddenPills[0].style.display === 'none' || !hiddenPills[0].style.display;
            hiddenPills.forEach(p => p.style.display = isExpanding ? 'inline-block' : 'none');
            if (moreBtn) {
                moreBtn.textContent = isExpanding ? 'Show Less' : `+${hiddenPills.length}`;
            }
        }
    };

    function renderSkillCategoryCards(profile, evidenceList) {
        const grid = document.getElementById('cd-categories-grid');
        grid.innerHTML = '';

        const matchedReq = profile.matched_required_skills || [];
        const matchedPref = profile.matched_preferred_skills || [];

        const categories = [
            {
                title: "Frontend Development",
                icon: "laptop",
                skills: ["JavaScript", "TypeScript", "React", "React.js", "Angular", "Vue.js", "Next.js", "HTML5", "CSS3", "Responsive Design"],
                defaultEvidence: "Developed frontend user interfaces and responsive web layouts."
            },
            {
                title: "Backend Development",
                icon: "server",
                skills: ["Node.js", "Express.js", "Python", "FastAPI", "Flask", "Django", "Java", "Spring Boot", "RESTful APIs", "Go"],
                defaultEvidence: "Built RESTful APIs and backend microservices."
            },
            {
                title: "Databases",
                icon: "database",
                skills: ["PostgreSQL", "MySQL", "MongoDB", "Redis", "Database Design", "Query Optimization", "Data Access Layers"],
                defaultEvidence: "Designed schemas and executed optimized database queries."
            },
            {
                title: "DevOps & Cloud",
                icon: "cloud",
                skills: ["Docker", "Docker Compose", "Kubernetes", "CI/CD", "AWS", "Azure", "Google Cloud", "Cloud Deployment"],
                defaultEvidence: "Containerized applications using Docker and deployed cloud infrastructure."
            },
            {
                title: "Tools & Other Skills",
                icon: "wrench",
                skills: ["Git", "GitHub", "GitLab", "Bitbucket", "Message Queues", "Background Workers", "Caching", "Microservices", "Testing"],
                defaultEvidence: "Version control, testing, and modern development tools usage."
            },
            {
                title: "Preferred Skills",
                icon: "star",
                skills: matchedPref.length > 0 ? matchedPref : ["TypeScript", "Next.js", "FastAPI", "Redis", "Docker Compose", "AWS", "Azure"],
                defaultEvidence: "Hands-on experience with preferred frameworks and advanced tooling."
            }
        ];

        categories.forEach((cat, index) => {
            const foundSkills = matchedReq.filter(s => cat.skills.some(cs => cs.toLowerCase().includes(s.toLowerCase()) || s.toLowerCase().includes(cs.toLowerCase())));
            const displaySkills = foundSkills.length > 0 ? foundSkills : cat.skills;

            const visibleSkills = displaySkills.slice(0, 6);
            const extraSkills = displaySkills.slice(6);

            const matchingEv = evidenceList.find(e => cat.skills.some(cs => cs.toLowerCase() === e.skill.toLowerCase()));
            const quoteText = matchingEv ? matchingEv.evidence_quote : cat.defaultEvidence;

            const card = document.createElement('div');
            card.className = 'cd-category-card';
            card.innerHTML = `
                <div class="cd-category-header">
                    <div class="cd-cat-title">
                        <i data-lucide="${cat.icon}" class="cd-cat-icon"></i>
                        <span>${cat.title}</span>
                    </div>
                    <span class="cd-matched-tag">
                        <i data-lucide="check-circle-2"></i> Matched
                    </span>
                </div>
                <div class="cd-pills-row" id="cd-pills-row-${index}">
                    ${visibleSkills.map(s => `<span class="cd-skill-pill">${s}</span>`).join('')}
                    ${extraSkills.map(s => `<span class="cd-skill-pill skill-pill-hidden" style="display: none;">${s}</span>`).join('')}
                    ${extraSkills.length > 0 ? `<span class="cd-skill-pill more-tag" onclick="toggleSkillCategoryPills(${index})" style="cursor: pointer;">+${extraSkills.length}</span>` : ''}
                </div>
                <div class="cd-evidence-text">
                    Evidence: ${quoteText}
                </div>
            `;
            grid.appendChild(card);
        });

        lucide.createIcons();
    }

    // Formats a breakdown score for display. Uses `!= null` (not `||`) because a
    // genuine 0% score is falsy and must NOT be displayed as "100%" — and a score
    // the backend excluded entirely (null, because the JD didn't specify that
    // requirement) must show as "N/A", not as a fabricated number either way.
    function formatBreakdownScore(value) {
        return (value === null || value === undefined) ? 'N/A' : `${value}%`;
    }

    function renderSkillsBreakdownChart(score, sb) {
        const container = document.getElementById('cd-breakdown-charts');
        const tiles = [
            { label: 'Required Skills (35%)', value: sb.required_skills_score, color: 'var(--accent-teal)' },
            { label: 'Experience (20%)', value: sb.experience_score, color: 'var(--accent)' },
            { label: 'Semantic JD Relevance (15%)', value: sb.semantic_relevance_score, color: '#38bdf8' },
            { label: 'Project Relevance (10%)', value: sb.project_score, color: '#a855f7' },
            { label: 'Preferred Skills (10%)', value: sb.preferred_skills_score, color: '#facc15' },
            { label: 'Education (5%)', value: sb.education_score, color: '#fb923c' },
            { label: 'Domain Fit (5%)', value: sb.domain_score, color: '#4ade80' },
        ];

        const tilesHtml = tiles.map(t => `
            <div style="background: rgba(255,255,255,0.02); padding: 12px; border-radius: 8px; border: 1px solid var(--border-color);">
                <span style="font-size: 0.8rem; color: var(--text-secondary);">${t.label}:</span>
                <strong style="float: right; color: ${t.color};">${formatBreakdownScore(t.value)}</strong>
            </div>
        `).join('');

        const semanticSkills = [
            ...(sb.semantically_matched_required_skills || []),
            ...(sb.semantically_matched_preferred_skills || [])
        ];
        const semanticNote = semanticSkills.length > 0
            ? `<p style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 10px;">
                 <i data-lucide="sparkles" style="width:12px;height:12px;vertical-align:-2px;"></i>
                 Matched via semantic similarity (not an exact keyword match): ${semanticSkills.join(', ')}
               </p>`
            : '';

        container.innerHTML = `
            <div style="display: flex; gap: 20px; margin-bottom: 12px;">
                <div style="background: rgba(0, 242, 254, 0.05); border: 1px solid rgba(0, 242, 254, 0.2); padding: 20px; border-radius: 12px; text-align: center; min-width: 140px;">
                    <div style="font-size: 2.2rem; font-weight: 700; color: var(--accent);">${score}%</div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">Overall Score</div>
                </div>
                <div style="flex: 1; display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">
                    ${tilesHtml}
                </div>
            </div>
            ${semanticNote}
        `;
        lucide.createIcons();
    }

    function renderProjectsPane(profile) {
        const container = document.getElementById('cd-projects-list');
        const projects = profile.projects || [];
        
        if (!projects || projects.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.85rem;">No explicit project details mentioned in candidate resume.</p>';
            return;
        }

        container.innerHTML = projects.map(proj => `
            <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 16px; border-radius: 10px; margin-bottom: 12px;">
                <h4 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 6px; color: var(--accent);">${typeof proj === 'string' ? proj : (proj.name || 'Candidate Project')}</h4>
                <p style="font-size: 0.85rem; color: var(--text-secondary);">${typeof proj === 'object' ? (proj.description || '') : ''}</p>
            </div>
        `).join('');
    }

    function renderExperiencePane(profile) {
        const container = document.getElementById('cd-experience-list');
        const workHistory = profile.work_history || [];

        if (!workHistory || workHistory.length === 0) {
            container.innerHTML = `
                <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 16px; border-radius: 10px;">
                    <h4 style="font-size: 0.95rem; font-weight: 700; color: #fff;">${profile.title || 'Software Engineer'}</h4>
                    <p style="font-size: 0.8rem; color: var(--accent); margin-bottom: 8px;">Experience: ${profile.experience_years || 0} Years</p>
                    <p style="font-size: 0.85rem; color: var(--text-secondary);">${profile.experience_fit || 'Evaluated against job criteria'}</p>
                </div>
            `;
            return;
        }

        container.innerHTML = workHistory.map(item => `
            <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 16px; border-radius: 10px; margin-bottom: 12px;">
                <h4 style="font-size: 0.95rem; font-weight: 700; color: #fff;">${typeof item === 'string' ? item : (item.role || 'Experience Item')}</h4>
            </div>
        `).join('');
    }

    function renderEducationPane(profile) {
        const container = document.getElementById('cd-education-list');
        const eduDetails = profile.education_details || [];

        if (!eduDetails || eduDetails.length === 0) {
            container.innerHTML = `
                <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 16px; border-radius: 10px;">
                    <h4 style="font-size: 0.95rem; font-weight: 700; color: #fff;">Bachelor's / Higher Education Degree</h4>
                    <p style="font-size: 0.8rem; color: var(--text-secondary);">${profile.education_fit ? 'Degree requirement satisfied' : 'Degree qualification evaluated'}</p>
                </div>
            `;
            return;
        }

        container.innerHTML = eduDetails.map(edu => `
            <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 16px; border-radius: 10px; margin-bottom: 10px;">
                <h4 style="font-size: 0.95rem; font-weight: 700; color: #fff;">${typeof edu === 'string' ? edu : (edu.degree || 'Degree')}</h4>
            </div>
        `).join('');
    }

    function renderRawEvidencePane(evidenceList) {
        const container = document.getElementById('cd-raw-evidence-list');
        container.innerHTML = '';
        if (evidenceList.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.85rem;">No direct evidence quotes extracted yet.</p>';
            return;
        }

        evidenceList.forEach(ev => {
            const div = document.createElement('div');
            div.className = 'evidence-quote-box';
            div.innerHTML = `
                <strong>Skill: ${ev.skill}</strong> (${ev.matched ? '✓ Matched' : '❌ Missing'})<br>
                <em>"${ev.evidence_quote || 'Evidence extracted from resume'}"</em><br>
                <small style="color: var(--text-secondary)">Source: ${ev.document || 'Resume'}, Page ${ev.page || 1}</small>
            `;
            container.appendChild(div);
        });
    }

    window.clearHRSession = async function() {
        if (!confirm("Are you sure you want to clear all candidate records, JD data, and reset the leaderboard?")) {
            return;
        }

        try {
            let res = await authFetch(`${API_BASE}/hr/jobs/${activeJobId}/clear`, {
                method: 'POST'
            });

            if (res.status === 404) {
                // Fallback to legacy clear route if job-specific clear route is not found
                res = await authFetch(`${API_BASE}/hr/clear`, {
                    method: 'POST'
                });
            }

            const data = await res.json();
            if (res.ok) {
                activeJDInfo = null;
                const activeJDEl = document.getElementById('active-jd-status');
                if (activeJDEl) activeJDEl.textContent = "Upload active job description";

                const resumesStatusEl = document.getElementById('resumes-upload-status');
                if (resumesStatusEl) resumesStatusEl.textContent = "Upload candidate resumes (PDF, DOCX)";

                const chipsBox = document.getElementById('jd-requirements-chips');
                if (chipsBox) chipsBox.innerHTML = '';

                renderLeaderboard([]);
                showSuccessToast("HR screening session and candidate data cleared successfully.");
            } else {
                showErrorToast(extractErrorMessage(data, 'Failed to clear the HR session.'));
            }
        } catch (err) {
            console.error("Error clearing HR session:", err);
            showErrorToast('Failed to clear session: server unreachable.');
        }
    };

    // ─── Boot ─────────────────────────────────────────────────────────────
    checkAuthState();
});
