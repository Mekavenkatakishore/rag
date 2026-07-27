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

    /** Handle 401 Unauthorized globally — log the user out and show modal */
    function handleUnauthorized() {
        accessToken = null;
        currentUsername = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        addMessage('bot', '⚠️ Your session has expired. Please log in again.');
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
        // Keep only the first welcome message
        const welcome = chatMessages.querySelector('.welcome-msg');
        chatMessages.innerHTML = '';
        if (welcome) chatMessages.appendChild(welcome);
        chatHistory = []; // Reset conversation memory
    });

    // ─── Boot ─────────────────────────────────────────────────────────────
    // Check auth state immediately on page load
    checkAuthState();
});
