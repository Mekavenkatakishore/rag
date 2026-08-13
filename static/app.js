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
                alert(`Error: ${data.detail || 'Failed to delete file.'}`);
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
            alert('Network error while deleting file.');
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
                    errorMsg = JSON.parse(xhr.responseText).detail || errorMsg;
                } catch(e) {}
                addMessage('bot', `❌ Error: ${errorMsg}`);
                updateServerStatus();
            }
        };

        xhr.onerror = () => {
            uploadProgressContainer.style.display = 'none';
            addMessage('bot', `❌ Network error occurred while uploading.`);
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
                if (statusEl) statusEl.textContent = `Error: ${data.detail || 'Upload failed'}`;
            }
        } catch (err) {
            console.error("Batch resume upload error:", err);
            if (statusEl) statusEl.textContent = `Batch upload failed: ${err.message || err}`;
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
                if (statusEl) statusEl.textContent = `Error: ${data.detail || 'Upload failed'}`;
            }
        } catch (err) {
            console.error("JD upload error:", err);
            if (statusEl) statusEl.textContent = `Upload failed: ${err.message || err}`;
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
            } else {
                alert(`Evaluation failed: ${data.detail || 'Error'}`);
            }
        } catch (err) {
            alert("Evaluation request failed.");
        } finally {
            if (btn) btn.disabled = false;
        }
    };

    async function fetchHRLeaderboard() {
        try {
            const res = await authFetch(`${API_BASE}/hr/jobs/${activeJobId}/leaderboard`);
            const data = await res.json();
            if (res.ok) {
                renderLeaderboard(data.candidates || []);
            }
        } catch (err) {
            console.error("Error fetching leaderboard:", err);
        }
    }

    function renderLeaderboard(candidates) {
        const tbody = document.getElementById('leaderboard-body');
        const countBadge = document.getElementById('candidates-count');

        if (countBadge) countBadge.textContent = `${candidates.length} Candidates Scored`;
        if (!tbody) return;

        tbody.innerHTML = '';
        if (candidates.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="empty-table-msg">
                        Upload a Job Description and candidate resumes above, then click <strong>Run AI Matching</strong>.
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
            const missingSkills = (profile.missing_required_skills || []).map(s => `<span class="skill-chip missing">${s}</span>`).join(' ');

            tr.innerHTML = `
                <td><strong>#${cand.rank || 1}</strong></td>
                <td>${cand.name || cand.filename}</td>
                <td><strong>${cand.score}%</strong></td>
                <td><span class="fit-badge ${fitClass}">${cand.fit || 'Pending'}</span></td>
                <td><div class="skills-chip-box">${matchedSkills || 'None'}</div></td>
                <td><div class="skills-chip-box">${missingSkills || 'None'}</div></td>
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

    window.showCandidateDetails = async function(candidateId) {
        try {
            const res = await authFetch(`${API_BASE}/hr/jobs/${activeJobId}/candidates/${candidateId}`);
            const data = await res.json();
            if (!res.ok) return;

            document.getElementById('modal-candidate-name').textContent = data.profile.candidate_name || candidateId;
            document.getElementById('modal-final-score').textContent = `${data.score}%`;
            
            const fitBadge = document.getElementById('modal-fit-badge');
            fitBadge.textContent = data.fit;
            fitBadge.className = `fit-badge ${data.fit === 'Strong Fit' ? 'strong-fit' : (data.fit === 'Moderate Fit' ? 'moderate-fit' : 'weak-fit')}`;

            const metricsBox = document.getElementById('modal-breakdown-metrics');
            const sb = data.score_breakdown || {};
            metricsBox.innerHTML = `
                <p><strong>Required Skills Fit:</strong> ${sb.required_skills_score || 0}%</p>
                <p><strong>Experience Score:</strong> ${sb.experience_score || 0}%</p>
                <p><strong>Project Relevance:</strong> ${sb.project_score || 0}%</p>
                <p><strong>Preferred Skills Fit:</strong> ${sb.preferred_skills_score || 0}%</p>
            `;

            const evidenceBox = document.getElementById('modal-evidence-list');
            evidenceBox.innerHTML = '';
            (data.evidence || []).forEach(ev => {
                const div = document.createElement('div');
                div.className = 'evidence-quote-box';
                div.innerHTML = `
                    <strong>Skill: ${ev.skill}</strong> (${ev.matched ? '✓ Matched' : '❌ Missing'})<br>
                    <em>"${ev.evidence_quote || 'Evidence extracted from resume'}"</em><br>
                    <small style="color: var(--text-secondary)">Source: ${ev.document || 'Resume'}, Page ${ev.page || 1}</small>
                `;
                evidenceBox.appendChild(div);
            });

            document.getElementById('candidate-modal').classList.remove('hidden');
        } catch (err) {
            console.error("Error fetching candidate details:", err);
        }
    };

    window.closeCandidateModal = function() {
        document.getElementById('candidate-modal').classList.add('hidden');
    };

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
                alert("HR screening session and candidate data cleared successfully.");
            } else {
                alert(`Clear failed: ${data.detail || 'Error'}`);
            }
        } catch (err) {
            console.error("Error clearing HR session:", err);
            alert("Failed to clear session.");
        }
    };

    // ─── Boot ─────────────────────────────────────────────────────────────
    checkAuthState();
});
