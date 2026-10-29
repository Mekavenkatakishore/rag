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
     * SPA Router & View Manager
     * Routes:
     *   /home      workspace chooser
     *   /chat      General RAG chatbot (Knowledge Assistant)
     *   /matcher   HR Candidate Matcher
     *   /approval  Approval Review
     */
    function getCurrentRoute() {
        const hash = (window.location.hash || '').replace(/^#\/?/, '').trim().toLowerCase();
        if (['home', 'chat', 'matcher', 'approval'].includes(hash)) {
            return hash;
        }
        const path = (window.location.pathname || '').replace(/^\//, '').split('/')[0].trim().toLowerCase();
        if (['home', 'chat', 'matcher', 'approval'].includes(path)) {
            return path;
        }
        return 'home';
    }

    function checkAuthState() {
        if (accessToken && currentUsername) {
            showApp();
        } else {
            showAuthModal();
        }
    }

    function showAuthModal() {
        authOverlay.classList.remove('hidden');
        const viewHome = document.getElementById('view-home');
        const appContainer = document.getElementById('app-container');
        if (viewHome) viewHome.classList.add('hidden');
        if (appContainer) appContainer.classList.add('hidden');
    }

    window.handleLogout = function() {
        accessToken = null;
        currentUsername = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        chatHistory = [];
        showAuthModal();
    };

    window.navigateTo = function(route, updateUrl = true) {
        const validRoutes = ['home', 'chat', 'matcher', 'approval'];
        if (!validRoutes.includes(route)) {
            route = 'home';
        }

        // Auth guard: if not authenticated, redirect to login modal
        if (!accessToken || !currentUsername) {
            showAuthModal();
            return;
        }

        if (updateUrl) {
            window.location.hash = '#/' + route;
            if (window.history && window.history.pushState) {
                try {
                    window.history.pushState(null, '', '/' + route);
                } catch (e) {
                    // Fallback to hash only if pushState restricted
                }
            }
        }

        const viewHome = document.getElementById('view-home');
        const appContainer = document.getElementById('app-container');
        const clearChatBtn = document.getElementById('clear-chat');

        // Views
        const viewRag = document.getElementById('view-rag-chat');
        const viewHr = document.getElementById('view-hr-matcher');
        const viewCandidateDetail = document.getElementById('view-candidate-detail');
        const viewApproval = document.getElementById('view-approval-review');
        const viewApprovalReview = document.getElementById('view-approval-candidate-review');

        // Title and Subtitle
        const title = document.getElementById('view-title');
        const subtitle = document.getElementById('view-subtitle');

        // Workspace Tabs
        const tabChat = document.getElementById('ws-tab-chat');
        const tabMatcher = document.getElementById('ws-tab-matcher');
        const tabApproval = document.getElementById('ws-tab-approval');

        [tabChat, tabMatcher, tabApproval].forEach(tab => {
            if (tab) tab.classList.remove('active');
        });

        if (route === 'home') {
            if (viewHome) viewHome.classList.remove('hidden');
            if (appContainer) appContainer.classList.add('hidden');
            fetchApprovalCandidates();
        } else {
            if (viewHome) viewHome.classList.add('hidden');
            if (appContainer) {
                appContainer.classList.remove('hidden');
                appContainer.classList.remove('workspace-chat', 'workspace-matcher', 'workspace-approval');
                appContainer.classList.add('workspace-' + route);
            }

            // Reset child views
            [viewRag, viewHr, viewCandidateDetail, viewApproval, viewApprovalReview].forEach(v => {
                if (v) v.classList.add('hidden');
            });

            if (route === 'chat') {
                if (tabChat) tabChat.classList.add('active');
                if (viewRag) viewRag.classList.remove('hidden');
                if (title) title.textContent = "Knowledge Assistant";
                if (subtitle) subtitle.textContent = "Grounded in your uploaded playbooks and documentation";
                if (clearChatBtn) clearChatBtn.style.display = 'flex';
                updateServerStatus();
            } else if (route === 'matcher') {
                if (tabMatcher) tabMatcher.classList.add('active');
                if (viewHr) viewHr.classList.remove('hidden');
                if (title) title.textContent = "AI HR Candidate Matcher";
                if (subtitle) subtitle.textContent = "Upload Job Description & candidate resumes for AI match ranking";
                if (clearChatBtn) clearChatBtn.style.display = 'none';
                fetchHRLeaderboard();
            } else if (route === 'approval') {
                if (tabApproval) tabApproval.classList.add('active');
                if (viewApproval) viewApproval.classList.remove('hidden');
                if (title) title.textContent = "Candidate Approval Review";
                if (subtitle) subtitle.textContent = "Review screened candidates against JD requirements and authorize shortlist email dispatch";
                if (clearChatBtn) clearChatBtn.style.display = 'none';
                fetchApprovalCandidates();
            }
        }

        if (window.lucide) {
            lucide.createIcons();
        }
    };

    window.addEventListener('popstate', () => {
        if (accessToken && currentUsername) {
            navigateTo(getCurrentRoute(), false);
        }
    });

    window.addEventListener('hashchange', () => {
        if (accessToken && currentUsername) {
            navigateTo(getCurrentRoute(), false);
        }
    });

    function showApp() {
        authOverlay.classList.add('hidden');
        ['user-name-display', 'home-user-name', 'top-user-name'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = currentUsername;
        });
        lucide.createIcons();
        fetchApprovalCandidates();
        updateServerStatus();

        const initialRoute = getCurrentRoute();
        navigateTo(initialRoute, false);
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
            navigateTo('home');

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
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            window.handleLogout();
        });
    }

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
        if (typeof addMessage === 'function') {
            addMessage('bot', '⚠️ Your session has expired. Please log in again.');
        }
        showToast('Your session has expired. Please log in again.', 'warning');
        window.handleLogout();
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
        if (mode === 'rag') {
            window.navigateTo('chat');
        } else if (mode === 'hr') {
            window.navigateTo('matcher');
        } else if (mode === 'approval') {
            window.navigateTo('approval');
        } else {
            window.navigateTo(mode);
        }
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

            const candEmail = cand.email || profile.email || '';
            const emailHtml = candEmail
                ? `<div style="font-size:0.75rem; color:var(--text-secondary); margin-top:2px; cursor:pointer;" onclick="quickEditCandidateEmail('${cand.candidate_id}', '${candEmail}', event)" title="Click to edit email"><i data-lucide="mail" style="width:11px; height:11px; display:inline;"></i> ${candEmail} <span style="opacity:0.6; font-size:0.7rem;">✎</span></div>`
                : `<div style="font-size:0.72rem; color:#f59e0b; margin-top:2px; cursor:pointer;" onclick="quickEditCandidateEmail('${cand.candidate_id}', '', event)" title="Click to add email"><i data-lucide="plus-circle" style="width:11px; height:11px; display:inline;"></i> Add email</div>`;

            tr.innerHTML = `
                <td><strong>#${cand.rank || 1}</strong></td>
                <td>
                    <div style="font-weight:600;">${cand.name || cand.filename}</div>
                    ${emailHtml}
                </td>
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

            const cdEmailInput = document.getElementById('cd-spec-email-input');
            if (cdEmailInput) {
                cdEmailInput.value = data.email || profile.email || '';
            }

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

    // ═══════════════════════════════════════════════════════════════════════
    //  HUMAN APPROVAL WORKFLOW FRONTEND CONTROLLER (PHASE 1)
    // ═══════════════════════════════════════════════════════════════════════

    let approvalCandidatesList = [];
    let activeApprovalStatusFilter = "Pending Approval";
    let activeApprovalSort = "score_desc";
    let activeApprovalMinScore = 0;
    let activeApprovalSearch = "";
    let currentReviewCandidateId = null;
    let currentReviewCandidateData = null;

    async function fetchApprovalCandidates() {
        try {
            const tbody = document.getElementById('approval-table-body');
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="8" class="empty-table-msg">Loading candidates for review...</td></tr>`;
            }

            const res = await authFetch(`${API_BASE}/shortlisted?status=all`);
            const data = await res.json();
            if (!res.ok) {
                showErrorToast(extractErrorMessage(data, 'Failed to fetch candidate approval list.'));
                return;
            }

            approvalCandidatesList = data.candidates || [];
            updateApprovalKPIs();
            renderApprovalTable();
        } catch (err) {
            console.error("Error fetching approval candidates:", err);
            showErrorToast('Failed to load candidate approval list: server unreachable.');
        }
    }

    function updateApprovalKPIs() {
        const pendingCount = approvalCandidatesList.filter(c => 
            c.status === 'Pending Approval' || c.status === 'Shortlisted (Pending Approval)' || c.status === 'Shortlisted'
        ).length;
        const approvedCount = approvalCandidatesList.filter(c => 
            c.status === 'Approved' || (c.status && (c.status.includes('Email Sent') || c.status.includes('Email Queued') || c.status.includes('Email Failed')))
        ).length;
        const holdCount = approvalCandidatesList.filter(c => c.status === 'On Hold').length;
        const rejectedCount = approvalCandidatesList.filter(c => c.status === 'Rejected').length;
        const allCount = approvalCandidatesList.length;

        // KPI Badges
        const kpiPend = document.getElementById('kpi-pending-count');
        const kpiAppr = document.getElementById('kpi-approved-count');
        const kpiHold = document.getElementById('kpi-hold-count');
        if (kpiPend) kpiPend.textContent = pendingCount;
        if (kpiAppr) kpiAppr.textContent = approvedCount;
        if (kpiHold) kpiHold.textContent = holdCount;

        // Filter tab counts
        const countPend = document.getElementById('appr-count-pending');
        const countAppr = document.getElementById('appr-count-approved');
        const countHold = document.getElementById('appr-count-hold');
        const countRej = document.getElementById('appr-count-rejected');
        const countAll = document.getElementById('appr-count-all');
        if (countPend) countPend.textContent = `(${pendingCount})`;
        if (countAppr) countAppr.textContent = `(${approvedCount})`;
        if (countHold) countHold.textContent = `(${holdCount})`;
        if (countRej) countRej.textContent = `(${rejectedCount})`;
        if (countAll) countAll.textContent = `(${allCount})`;

        // Home Chooser Card Badge
        const homeBadge = document.getElementById('home-approval-badge');
        if (homeBadge) {
            if (pendingCount > 0) {
                homeBadge.textContent = pendingCount;
                homeBadge.style.display = 'inline-flex';
            } else {
                homeBadge.style.display = 'none';
            }
        }

        // Top Workspace Switcher Badge
        const wsBadge = document.getElementById('ws-pending-badge');
        if (wsBadge) {
            if (pendingCount > 0) {
                wsBadge.textContent = pendingCount;
                wsBadge.style.display = 'inline-flex';
            } else {
                wsBadge.style.display = 'none';
            }
        }

        // Legacy / Fallback Navigation Badge
        const navBadge = document.getElementById('nav-pending-badge');
        if (navBadge) {
            if (pendingCount > 0) {
                navBadge.textContent = pendingCount;
                navBadge.style.display = 'inline-block';
            } else {
                navBadge.style.display = 'none';
            }
        }
    }

    window.setApprovalStatusFilter = function(status) {
        activeApprovalStatusFilter = status;
        document.querySelectorAll('.approval-filter-tabs .appr-tab-btn').forEach(btn => btn.classList.remove('active'));
        
        let targetId = 'appr-filter-all';
        if (status === 'Pending Approval') targetId = 'appr-filter-pending';
        else if (status === 'Approved') targetId = 'appr-filter-approved';
        else if (status === 'On Hold') targetId = 'appr-filter-hold';
        else if (status === 'Rejected') targetId = 'appr-filter-rejected';

        const activeBtn = document.getElementById(targetId);
        if (activeBtn) activeBtn.classList.add('active');

        renderApprovalTable();
    };

    window.handleApprovalSortChange = function(val) {
        activeApprovalSort = val;
        renderApprovalTable();
    };

    window.handleApprovalMinScoreChange = function(val) {
        activeApprovalMinScore = parseFloat(val) || 0;
        renderApprovalTable();
    };

    window.handleApprovalSearch = function(val) {
        activeApprovalSearch = (val || "").toLowerCase().trim();
        renderApprovalTable();
    };

    function renderApprovalTable() {
        const tbody = document.getElementById('approval-table-body');
        if (!tbody) return;

        let filtered = [...approvalCandidatesList];

        // 1. Status Filter
        if (activeApprovalStatusFilter !== 'all') {
            if (activeApprovalStatusFilter === 'Pending Approval') {
                filtered = filtered.filter(c => 
                    c.status === 'Pending Approval' || c.status === 'Shortlisted (Pending Approval)' || c.status === 'Shortlisted'
                );
            } else if (activeApprovalStatusFilter === 'Approved') {
                filtered = filtered.filter(c => 
                    c.status === 'Approved' || (c.status && (c.status.includes('Email Sent') || c.status.includes('Email Queued') || c.status.includes('Email Failed')))
                );
            } else {
                filtered = filtered.filter(c => c.status === activeApprovalStatusFilter);
            }
        }

        // 2. Min Score Filter
        if (activeApprovalMinScore > 0) {
            filtered = filtered.filter(c => (c.score || 0) >= activeApprovalMinScore);
        }

        // 3. Search Filter
        if (activeApprovalSearch) {
            filtered = filtered.filter(c => 
                (c.name || "").toLowerCase().includes(activeApprovalSearch) ||
                (c.role || "").toLowerCase().includes(activeApprovalSearch) ||
                (c.job_title || "").toLowerCase().includes(activeApprovalSearch)
            );
        }

        // 4. Sort
        if (activeApprovalSort === 'score_desc') {
            filtered.sort((a, b) => (b.score || 0) - (a.score || 0));
        } else if (activeApprovalSort === 'score_asc') {
            filtered.sort((a, b) => (a.score || 0) - (b.score || 0));
        } else if (activeApprovalSort === 'date_desc') {
            filtered.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
        } else if (activeApprovalSort === 'name_asc') {
            filtered.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
        }

        tbody.innerHTML = '';
        if (filtered.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="empty-table-msg">
                        No candidates found for status filter <strong>${activeApprovalStatusFilter}</strong>.
                    </td>
                </tr>
            `;
            return;
        }

        filtered.forEach((cand, idx) => {
            const tr = document.createElement('tr');
            
            let statusBadgeClass = 'pending-approval';
            let statusLabel = cand.status || 'Pending Approval';
            if (statusLabel === 'Approved') {
                statusBadgeClass = 'approved';
            } else if (statusLabel.includes('Email Sent')) {
                statusBadgeClass = 'email-sent';
                statusLabel = 'Approved & Sent';
            } else if (statusLabel.includes('Email Failed')) {
                statusBadgeClass = 'email-failed';
                statusLabel = 'Email Failed';
            } else if (statusLabel.includes('Email Queued')) {
                statusBadgeClass = 'queued';
                statusLabel = 'Email Queued';
            } else if (statusLabel === 'On Hold') {
                statusBadgeClass = 'on-hold';
            } else if (statusLabel === 'Rejected') {
                statusBadgeClass = 'rejected';
            } else if (statusLabel.includes('Pending') || statusLabel.includes('Shortlisted')) {
                statusBadgeClass = 'pending-approval';
                statusLabel = 'Pending Approval';
            }

            const topSkillsChips = (cand.top_matched_skills || []).map(s => 
                `<span class="skill-chip matched" style="font-size: 0.72rem; padding: 2px 7px;">${s}</span>`
            ).join(' ') || '<span style="color:var(--text-secondary); font-size:0.75rem;">None</span>';

            const formattedDate = cand.date ? cand.date.substring(0, 10) : 'Recent';

            const apprEmailDisplay = cand.email 
                ? `<div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px; cursor: pointer;" onclick="quickEditCandidateEmail('${cand.candidate_id}', '${cand.email}', event)" title="Click to edit email"><i data-lucide="mail" style="width:11px; height:11px; display:inline;"></i> ${cand.email} <span style="opacity:0.6; font-size:0.7rem;">✎</span></div>`
                : `<div style="font-size: 0.72rem; color: #f59e0b; margin-top: 2px; cursor: pointer;" onclick="quickEditCandidateEmail('${cand.candidate_id}', '', event)" title="Click to add email"><i data-lucide="plus-circle" style="width:11px; height:11px; display:inline;"></i> Add email</div>`;

            tr.innerHTML = `
                <td><strong>#${idx + 1}</strong></td>
                <td>
                    <div style="font-weight: 600; color: #f1f5f9;">${cand.name}</div>
                    ${apprEmailDisplay}
                </td>
                <td>
                    <div style="font-size: 0.82rem; color: #cbd5e1;">${cand.role || cand.job_title}</div>
                    <div style="font-size: 0.72rem; color: var(--text-secondary);">${cand.job_title}</div>
                </td>
                <td>
                    <div style="font-size: 0.95rem; font-weight: 700; color: #00f2fe;">${cand.score}%</div>
                    <span class="fit-badge ${cand.fit_category === 'Strong Fit' ? 'strong-fit' : (cand.fit_category === 'Moderate Fit' ? 'moderate-fit' : 'weak-fit')}" style="font-size:0.7rem; padding: 1px 6px;">
                        ${cand.fit_category || 'Fit'}
                    </span>
                </td>
                <td>
                    <span class="hr-status-badge ${statusBadgeClass}">
                        ${statusLabel}
                    </span>
                </td>
                <td>
                    <div style="display:flex; flex-wrap:wrap; gap:4px; max-width: 240px;">
                        ${topSkillsChips}
                    </div>
                </td>
                <td style="font-size: 0.78rem; color: var(--text-secondary);">${formattedDate}</td>
                <td>
                    <button class="action-btn-primary" style="padding: 5px 12px; font-size: 0.78rem; display: flex; align-items: center; gap: 4px;" onclick="openApprovalCandidateReview('${cand.candidate_id}')">
                        <i data-lucide="file-search" style="width:14px; height:14px;"></i>
                        <span>Review Candidate</span>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        lucide.createIcons();
    }

    // ─── Candidate Review Deep Dive Screen ──────────────────────────────────

    window.openApprovalCandidateReview = async function(candidateId) {
        currentReviewCandidateId = candidateId;
        const viewList = document.getElementById('view-approval-review');
        const viewReview = document.getElementById('view-approval-candidate-review');

        if (viewList) viewList.classList.add('hidden');
        if (viewReview) viewReview.classList.remove('hidden');

        try {
            const res = await authFetch(`${API_BASE}/candidates/${candidateId}/match-details`);
            const data = await res.json();
            if (!res.ok) {
                showErrorToast(extractErrorMessage(data, 'Could not load match details.'));
                return;
            }

            currentReviewCandidateData = data;
            renderCandidateReviewScreen(data);
        } catch (err) {
            console.error("Error loading candidate review screen:", err);
            showErrorToast('Failed to load candidate review data: server unreachable.');
        }
    };

    window.hideApprovalCandidateReview = function() {
        const viewList = document.getElementById('view-approval-review');
        const viewReview = document.getElementById('view-approval-candidate-review');

        if (viewReview) viewReview.classList.add('hidden');
        if (viewList) viewList.classList.remove('hidden');

        fetchApprovalCandidates();
    };

    function renderCandidateReviewScreen(d) {
        // 1. Header & Status
        const nameEl = document.getElementById('ar-cand-header-name');
        const roleEl = document.getElementById('ar-cand-header-role');
        const scoreValEl = document.querySelector('#ar-cand-header-score .score-val');
        const statusBadge = document.getElementById('ar-current-status-badge');
        const notesInput = document.getElementById('ar-hr-notes-input');

        if (nameEl) nameEl.textContent = d.name || "Candidate";
        if (roleEl) roleEl.textContent = `${d.role || 'Software Engineer'} • Target JD: ${d.jd_requirements?.title || d.job_id}`;
        if (scoreValEl) scoreValEl.textContent = `${d.overall_score}%`;
        
        if (statusBadge) {
            let statusLabel = d.candidate_status || 'Pending Approval';
            let badgeClass = 'pending-approval';
            if (statusLabel === 'Approved') badgeClass = 'approved';
            else if (statusLabel.includes('Email Sent')) {
                badgeClass = 'email-sent';
                statusLabel = 'Approved & Sent';
            } else if (statusLabel.includes('Email Failed')) {
                badgeClass = 'email-failed';
                statusLabel = 'Email Failed';
            } else if (statusLabel.includes('Email Queued')) {
                badgeClass = 'queued';
                statusLabel = 'Email Queued';
            } else if (statusLabel === 'On Hold') badgeClass = 'on-hold';
            else if (statusLabel === 'Rejected') badgeClass = 'rejected';
            else badgeClass = 'pending-approval';

            statusBadge.className = `hr-status-badge ${badgeClass}`;
            statusBadge.textContent = statusLabel;
        }

        // Show/Hide Retry button and update Approve button state
        const retryBtn = document.getElementById('ar-btn-retry-email');
        const approveBtn = document.getElementById('btn-action-approve-primary');
        if (retryBtn) {
            if ((d.candidate_status || '').includes('Email Failed')) {
                retryBtn.classList.remove('hidden');
            } else {
                retryBtn.classList.add('hidden');
            }
        }
        if (approveBtn) {
            if ((d.candidate_status || '').includes('Email Sent')) {
                approveBtn.disabled = true;
                approveBtn.title = 'Shortlist email already delivered';
                approveBtn.style.opacity = '0.6';
            } else {
                approveBtn.disabled = false;
                approveBtn.title = 'Approve and Authorize Shortlist Email';
                approveBtn.style.opacity = '1';
            }
        }

        if (notesInput) {
            notesInput.value = d.hr_notes || "";
        }

        const candEmailInput = document.getElementById('ar-cand-email-input');
        if (candEmailInput) {
            candEmailInput.value = (d.email && d.email !== 'Not Specified') ? d.email : '';
        }

        // 2. Summary & Red Flags
        const summaryText = document.getElementById('ar-summary-text');
        if (summaryText) summaryText.textContent = d.summary || "Candidate evaluated deterministically against job description.";

        const flagsList = document.getElementById('ar-red-flags-list');
        if (flagsList) {
            flagsList.innerHTML = '';
            const redFlags = d.red_flags || [];
            if (redFlags.length === 0) {
                flagsList.innerHTML = `<li style="color:#34d399;">No red flags detected. Candidate cleanly meets mandatory criteria.</li>`;
            } else {
                redFlags.forEach(rf => {
                    const li = document.createElement('li');
                    li.textContent = rf;
                    flagsList.appendChild(li);
                });
            }
        }

        // 3. Criteria Pass/Fail Matrix
        const criteriaTbody = document.getElementById('ar-criteria-table-body');
        if (criteriaTbody) {
            criteriaTbody.innerHTML = '';
            (d.criteria_results || []).forEach(cr => {
                const tr = document.createElement('tr');
                const pillHtml = cr.passed 
                    ? `<span class="criteria-pass-pill">✓ PASS</span>`
                    : `<span class="criteria-fail-pill">✗ FAIL</span>`;

                tr.innerHTML = `
                    <td><strong>${cr.rule}</strong></td>
                    <td style="color:var(--text-secondary);">${cr.requirement}</td>
                    <td>${cr.actual}</td>
                    <td>${pillHtml}</td>
                `;
                criteriaTbody.appendChild(tr);
            });
        }

        // 4. Side-by-Side: JD vs Candidate Evidence
        const jdCol = document.getElementById('ar-sbs-jd-content');
        const resumeCol = document.getElementById('ar-sbs-resume-content');
        const jdReq = d.jd_requirements || {};

        if (jdCol) {
            jdCol.innerHTML = `
                <div class="sbs-item">
                    <span class="sbs-label">Role Title</span>
                    <div>${jdReq.title || 'Role'}</div>
                </div>
                <div class="sbs-item">
                    <span class="sbs-label">Required Skills (${(jdReq.required_skills || []).length})</span>
                    <div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:4px;">
                        ${(jdReq.required_skills || []).map(s => `<span class="skill-chip" style="font-size:0.75rem;">${s}</span>`).join(' ') || 'None specified'}
                    </div>
                </div>
                <div class="sbs-item">
                    <span class="sbs-label">Preferred Skills (${(jdReq.preferred_skills || []).length})</span>
                    <div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:4px;">
                        ${(jdReq.preferred_skills || []).map(s => `<span class="skill-chip" style="font-size:0.75rem; border-color:rgba(255,255,255,0.1);">${s}</span>`).join(' ') || 'None specified'}
                    </div>
                </div>
                <div class="sbs-item">
                    <span class="sbs-label">Minimum Experience</span>
                    <div>${jdReq.min_experience_years || 0} Years</div>
                </div>
                <div class="sbs-item">
                    <span class="sbs-label">Education</span>
                    <div>${jdReq.education || 'Bachelor\'s degree in related technical field'}</div>
                </div>
            `;
        }

        if (resumeCol) {
            resumeCol.innerHTML = '';
            const matchedSkills = d.matched_skills || [];
            if (matchedSkills.length === 0) {
                resumeCol.innerHTML = `<div style="color:var(--text-secondary); font-size:0.8rem;">No explicit evidence snippets extracted.</div>`;
            } else {
                matchedSkills.forEach(ms => {
                    const block = document.createElement('div');
                    block.className = 'sbs-item';
                    block.innerHTML = `
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span class="skill-chip matched" style="font-size:0.75rem;">✓ ${ms.skill}</span>
                            <span style="font-size:0.7rem; color:var(--text-secondary);"><i data-lucide="file-text" style="width:11px; height:11px; display:inline;"></i> Page ${ms.page || 1}</span>
                        </div>
                        <div class="sbs-citation-quote">"${ms.evidence}"</div>
                    `;
                    resumeCol.appendChild(block);
                });
            }
        }

        // 5. Score Breakdown Bars
        const gaugeEl = document.getElementById('ar-big-score-gauge');
        const fitLabel = document.getElementById('ar-fit-category-label');
        if (gaugeEl) gaugeEl.textContent = `${d.overall_score}%`;
        if (fitLabel) {
            fitLabel.textContent = d.fit_category || "Fit";
            fitLabel.className = `fit-label ${d.fit_category === 'Strong Fit' ? 'strong-fit' : (d.fit_category === 'Moderate Fit' ? 'moderate-fit' : 'weak-fit')}`;
        }

        const barsList = document.getElementById('ar-component-bars');
        if (barsList) {
            barsList.innerHTML = '';
            const sb = d.score_breakdown || {};
            const components = [
                { name: "Required Skills Fit (35%)", val: sb.required_skills_score ?? 0 },
                { name: "Relevant Experience (20%)", val: sb.experience_score ?? 0 },
                { name: "Semantic JD Relevance (15%)", val: sb.semantic_relevance_score ?? 0 },
                { name: "Project Relevance (10%)", val: sb.project_score ?? 0 },
                { name: "Preferred Skills (10%)", val: sb.preferred_skills_score ?? 0 },
                { name: "Education Fit (5%)", val: sb.education_score ?? 0 },
                { name: "Domain Fit (5%)", val: sb.domain_score ?? 0 }
            ];

            components.forEach(c => {
                const item = document.createElement('div');
                item.className = 'comp-bar-item';
                item.innerHTML = `
                    <div class="comp-bar-header">
                        <span>${c.name}</span>
                        <strong>${c.val}%</strong>
                    </div>
                    <div class="comp-bar-track">
                        <div class="comp-bar-fill" style="width: ${Math.min(100, Math.max(0, c.val))}%;"></div>
                    </div>
                `;
                barsList.appendChild(item);
            });
        }

        // 6. Skills Classification (Matched, Missing, Bonus)
        const matchedBox = document.getElementById('ar-chips-matched');
        const missingBox = document.getElementById('ar-chips-missing');
        const bonusBox = document.getElementById('ar-chips-bonus');

        if (matchedBox) {
            matchedBox.innerHTML = (d.matched_skills || []).map(s => 
                `<span class="skill-chip matched" title="Verified in candidate resume">✓ ${s.skill}</span>`
            ).join(' ') || '<span style="color:var(--text-secondary); font-size:0.75rem;">None</span>';
        }

        if (missingBox) {
            missingBox.innerHTML = (d.missing_skills || []).map(s => 
                `<span class="skill-chip" style="border-color: rgba(239,68,68,0.4); color:#f87171; background: rgba(239,68,68,0.08);">✗ ${s}</span>`
            ).join(' ') || '<span style="color:#34d399; font-size:0.75rem;">None missing!</span>';
        }

        if (bonusBox) {
            bonusBox.innerHTML = (d.bonus_skills || []).map(s => 
                `<span class="skill-chip bonus">+ ${s}</span>`
            ).join(' ') || '<span style="color:var(--text-secondary); font-size:0.75rem;">No additional bonus skills</span>';
        }

        // 7. Experience Match
        const expBox = document.getElementById('ar-exp-match-content');
        if (expBox) {
            const exp = d.experience_match || {};
            expBox.innerHTML = `
                <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <div><strong>Required:</strong> ${exp.required_years || 0} Years</div>
                    <div><strong>Demonstrated:</strong> ${exp.actual_years || 0} Years</div>
                </div>
                <div style="font-size:0.8rem; color:${exp.meets ? '#34d399' : '#f87171'};">
                    ${exp.meets ? '✓ Meets minimum experience threshold' : `⚠ Below requirement by ${Math.abs(exp.difference_years || 0)} years`}
                </div>
            `;
        }

        // 8. Resume Document Preview Text
        const previewBox = document.getElementById('ar-resume-preview-text');
        const filenameTag = document.getElementById('ar-resume-preview-filename');
        if (filenameTag) filenameTag.textContent = d.filename || "resume.pdf";
        if (previewBox) previewBox.textContent = d.resume_preview_text || "Resume text verified.";

        // 9. Audit Trail
        fetchCandidateAuditLogs(d.candidate_id);

        lucide.createIcons();
    }

    async function fetchCandidateAuditLogs(candidateId) {
        const auditBox = document.getElementById('ar-audit-trail-list');
        if (!auditBox) return;

        try {
            const res = await authFetch(`${API_BASE}/candidates/${candidateId}/audit-logs`);
            const data = await res.json();
            if (res.ok && data.logs && data.logs.length > 0) {
                auditBox.innerHTML = '';
                data.logs.forEach(log => {
                    const item = document.createElement('div');
                    item.className = 'audit-item';
                    item.innerHTML = `
                        <div style="display:flex; justify-content:space-between;">
                            <strong>${log.action}</strong>
                            <span class="audit-meta">${(log.created_at || '').substring(0, 19).replace('T', ' ')}</span>
                        </div>
                        <div style="font-size:0.75rem; color:#cbd5e1; margin-top:2px;">
                            By: <strong>${log.performed_by}</strong> ${log.hr_notes ? `— "${log.hr_notes}"` : ''}
                        </div>
                    `;
                    auditBox.appendChild(item);
                });
            } else {
                auditBox.innerHTML = `<div class="audit-empty" style="color:var(--text-secondary); font-size:0.75rem;">No previous approval actions recorded.</div>`;
            }
        } catch (e) {
            console.error("Error fetching audit logs:", e);
        }
    }

    // ─── Candidate Email Management Handlers ───────────────────────────────

    let currentQuickEmailCandidateId = null;

    window.saveCandidateEmailDirectly = async function() {
        if (!currentReviewCandidateId) return;
        const input = document.getElementById('ar-cand-email-input');
        const email = input ? input.value.trim() : "";
        if (!email) {
            showErrorToast("Please enter a valid candidate email address.");
            if (input) input.focus();
            return;
        }

        const btn = document.getElementById('btn-save-review-email');
        if (btn) btn.disabled = true;

        try {
            const res = await authFetch(`${API_BASE}/candidates/${currentReviewCandidateId}/email`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email })
            });
            const data = await res.json();
            if (res.ok) {
                showSuccessToast(`Candidate email saved as ${email}`);
                if (currentReviewCandidateData) {
                    currentReviewCandidateData.email = email;
                }
                const modalEmail = document.getElementById('modal-approve-cand-email');
                if (modalEmail) modalEmail.value = email;
                fetchCandidateAuditLogs(currentReviewCandidateId);
                fetchApprovalCandidates();
            } else {
                showErrorToast(extractErrorMessage(data, 'Failed to save email.'));
            }
        } catch (err) {
            console.error("Error saving candidate email:", err);
            showErrorToast('Failed to save email: server unreachable.');
        } finally {
            if (btn) btn.disabled = false;
        }
    };

    window.saveCandidateEmailFromDeepDive = async function() {
        if (!currentActiveCandidateId) return;
        const input = document.getElementById('cd-spec-email-input');
        const email = input ? input.value.trim() : "";
        if (!email) {
            showErrorToast("Please enter a valid email address.");
            if (input) input.focus();
            return;
        }

        try {
            const res = await authFetch(`${API_BASE}/candidates/${currentActiveCandidateId}/email`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email })
            });
            const data = await res.json();
            if (res.ok) {
                showSuccessToast(`Candidate email saved as ${email}`);
                if (window.allLoadedCandidates) {
                    const match = window.allLoadedCandidates.find(c => c.candidate_id === currentActiveCandidateId);
                    if (match) match.email = email;
                    renderFilteredLeaderboardRows(window.allLoadedCandidates);
                }
            } else {
                showErrorToast(extractErrorMessage(data, 'Failed to save email.'));
            }
        } catch (err) {
            console.error("Error saving candidate email from deep dive:", err);
            showErrorToast('Failed to save email: server unreachable.');
        }
    };

    window.quickEditCandidateEmail = function(candidateId, currentEmail, e) {
        if (e) {
            e.stopPropagation();
            e.preventDefault();
        }
        currentQuickEmailCandidateId = candidateId;

        let candName = candidateId;
        const fromAll = (window.allLoadedCandidates || []).find(c => c.candidate_id === candidateId);
        if (fromAll && fromAll.name) candName = fromAll.name;
        const fromApproval = (window.allApprovalCandidates || []).find(c => c.candidate_id === candidateId);
        if (fromApproval && fromApproval.name) candName = fromApproval.name;

        const nameEl = document.getElementById('quick-email-cand-name');
        if (nameEl) nameEl.textContent = candName;

        const inp = document.getElementById('quick-email-input');
        if (inp) {
            inp.value = (currentEmail && currentEmail !== 'Not Specified') ? currentEmail : '';
            setTimeout(() => { inp.focus(); inp.select(); }, 80);
        }

        const modal = document.getElementById('quick-email-modal');
        if (modal) modal.classList.remove('hidden');
        lucide.createIcons();
    };

    window.closeQuickEmailModal = function() {
        const modal = document.getElementById('quick-email-modal');
        if (modal) modal.classList.add('hidden');
        currentQuickEmailCandidateId = null;
    };

    window.submitQuickEmailModal = async function() {
        if (!currentQuickEmailCandidateId) return;
        const inp = document.getElementById('quick-email-input');
        const email = inp ? inp.value.trim() : '';
        if (!email) {
            showErrorToast("Please enter a valid email address.");
            if (inp) inp.focus();
            return;
        }

        const btn = document.getElementById('btn-save-quick-email');
        if (btn) btn.disabled = true;

        try {
            const res = await authFetch(`${API_BASE}/candidates/${currentQuickEmailCandidateId}/email`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email })
            });
            const data = await res.json();
            if (res.ok) {
                closeQuickEmailModal();
                showSuccessToast(`Email updated to ${email}`);
                if (window.allApprovalCandidates) {
                    const match = window.allApprovalCandidates.find(c => c.candidate_id === currentQuickEmailCandidateId);
                    if (match) match.email = email;
                    renderApprovalTable();
                }
                if (window.allLoadedCandidates) {
                    const m2 = window.allLoadedCandidates.find(c => c.candidate_id === currentQuickEmailCandidateId);
                    if (m2) m2.email = email;
                    renderFilteredLeaderboardRows(window.allLoadedCandidates);
                }
                if (currentReviewCandidateId === currentQuickEmailCandidateId) {
                    const reviewInp = document.getElementById('ar-cand-email-input');
                    if (reviewInp) reviewInp.value = email;
                    if (currentReviewCandidateData) currentReviewCandidateData.email = email;
                }
            } else {
                showErrorToast(extractErrorMessage(data, 'Failed to update email.'));
            }
        } catch (err) {
            console.error("Error saving email via quick modal:", err);
            showErrorToast('Failed to save email: server unreachable.');
        } finally {
            if (btn) btn.disabled = false;
        }
    };

    // ─── Approval / Rejection / Hold Handlers & Modals ─────────────────────

    window.openApproveConfirmationModal = function() {
        if (!currentReviewCandidateData) return;
        const modalName = document.getElementById('modal-approve-cand-name');
        if (modalName) modalName.textContent = currentReviewCandidateData.name || "Candidate";

        const emailInput = document.getElementById('modal-approve-cand-email');
        if (emailInput) {
            const headerEmail = document.getElementById('ar-cand-email-input')?.value?.trim();
            const existingEmail = headerEmail || (currentReviewCandidateData.email && currentReviewCandidateData.email !== "Not Specified" 
                ? currentReviewCandidateData.email 
                : "");
            emailInput.value = existingEmail;
            setTimeout(() => {
                emailInput.focus();
                emailInput.select();
            }, 80);
        }

        const modal = document.getElementById('approve-confirm-modal');
        if (modal) modal.classList.remove('hidden');
        lucide.createIcons();
    };

    window.closeApproveConfirmationModal = function() {
        const modal = document.getElementById('approve-confirm-modal');
        if (modal) modal.classList.add('hidden');
    };

    window.confirmApproveCandidate = async function() {
        if (!currentReviewCandidateId) return;

        const emailInput = document.getElementById('modal-approve-cand-email');
        const headerEmailInput = document.getElementById('ar-cand-email-input');
        const candidateEmail = (emailInput ? emailInput.value.trim() : "") || (headerEmailInput ? headerEmailInput.value.trim() : "");
        if (!candidateEmail) {
            showErrorToast("Please enter a recipient email address to send the shortlist mail.");
            if (emailInput) emailInput.focus();
            else if (headerEmailInput) headerEmailInput.focus();
            return;
        }

        const btn = document.getElementById('btn-modal-confirm-approve');
        if (btn) btn.disabled = true;

        const hrNotes = document.getElementById('ar-hr-notes-input')?.value || "";

        try {
            // STEP 1: Pre-save candidate email to database directly so it is permanently stored
            try {
                await authFetch(`${API_BASE}/candidates/${currentReviewCandidateId}/email`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: candidateEmail })
                });
            } catch (saveErr) {
                console.warn("Pre-saving email note:", saveErr);
            }

            // STEP 2: Call approve with query param AND body for guaranteed delivery
            const approveUrl = `${API_BASE}/candidates/${currentReviewCandidateId}/approve?candidate_email=${encodeURIComponent(candidateEmail)}`;
            const res = await authFetch(approveUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    hr_notes: hrNotes,
                    candidate_email: candidateEmail,
                    email: candidateEmail
                })
            });
            const data = await res.json();

            if (res.ok) {
                closeApproveConfirmationModal();
                showSuccessToast(`Shortlist Approved! Email dispatch queued for ${candidateEmail}.`);

                if (currentReviewCandidateData) {
                    currentReviewCandidateData.email = candidateEmail;
                }
                const headerEmail = document.getElementById('ar-cand-email-input');
                if (headerEmail) headerEmail.value = candidateEmail;

                // Update UI status badge
                const statusBadge = document.getElementById('ar-current-status-badge');
                if (statusBadge) {
                    statusBadge.className = "hr-status-badge queued";
                    statusBadge.textContent = "Email Queued";
                }
                const approveBtn = document.getElementById('btn-action-approve-primary');
                if (approveBtn) {
                    approveBtn.disabled = true;
                    approveBtn.style.opacity = '0.6';
                }
                fetchCandidateAuditLogs(currentReviewCandidateId);
                updateApprovalKPIs();
                fetchApprovalCandidates();
            } else {
                showErrorToast(extractErrorMessage(data, 'Shortlist approval failed.'));
            }
        } catch (err) {
            console.error("Error approving candidate:", err);
            showErrorToast('Approval action failed: server unreachable.');
        } finally {
            if (btn) btn.disabled = false;
        }
    };

    window.handleRetryEmail = async function() {
        if (!currentReviewCandidateId) return;
        const btn = document.getElementById('ar-btn-retry-email');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<i data-lucide="loader" class="spinner"></i> <span>Retrying...</span>`;
        }

        try {
            const res = await authFetch(`${API_BASE}/candidates/${currentReviewCandidateId}/retry-email`, {
                method: 'POST'
            });
            const data = await res.json();
            if (res.ok) {
                showSuccessToast('Shortlist email retry successfully queued!');
                const statusBadge = document.getElementById('ar-current-status-badge');
                if (statusBadge) {
                    statusBadge.className = "hr-status-badge queued";
                    statusBadge.textContent = "Email Queued";
                }
                if (btn) btn.classList.add('hidden');
                fetchCandidateAuditLogs(currentReviewCandidateId);
                fetchApprovalCandidates();
            } else {
                showErrorToast(extractErrorMessage(data, 'Retry failed.'));
            }
        } catch (err) {
            console.error("Error retrying email:", err);
            showErrorToast('Failed to trigger email retry: server unreachable.');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i data-lucide="refresh-cw"></i> <span>Retry Email Send</span>`;
            }
            lucide.createIcons();
        }
    };

    window.openRejectConfirmationModal = function() {
        if (!currentReviewCandidateData) return;
        const modalName = document.getElementById('modal-reject-cand-name');
        if (modalName) modalName.textContent = currentReviewCandidateData.name || "Candidate";

        const modal = document.getElementById('reject-confirm-modal');
        if (modal) modal.classList.remove('hidden');
        lucide.createIcons();
    };

    window.closeRejectConfirmationModal = function() {
        const modal = document.getElementById('reject-confirm-modal');
        if (modal) modal.classList.add('hidden');
    };

    window.confirmRejectCandidate = async function() {
        if (!currentReviewCandidateId) return;
        const btn = document.getElementById('btn-modal-confirm-reject');
        if (btn) btn.disabled = true;

        const reasonSelect = document.getElementById('modal-reject-reason-select');
        const reason = reasonSelect?.value || "Qualifications do not match role requirements";
        const hrNotes = document.getElementById('ar-hr-notes-input')?.value || "";

        try {
            const res = await authFetch(`${API_BASE}/candidates/${currentReviewCandidateId}/reject`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hr_notes: hrNotes, rejection_reason: reason })
            });
            const data = await res.json();

            if (res.ok) {
                closeRejectConfirmationModal();
                showSuccessToast(`Candidate marked as Rejected.`);

                const statusBadge = document.getElementById('ar-current-status-badge');
                if (statusBadge) {
                    statusBadge.className = "hr-status-badge rejected";
                    statusBadge.textContent = "Rejected";
                }
                fetchCandidateAuditLogs(currentReviewCandidateId);
                updateApprovalKPIs();
            } else {
                showErrorToast(extractErrorMessage(data, 'Rejection action failed.'));
            }
        } catch (err) {
            console.error("Error rejecting candidate:", err);
            showErrorToast('Rejection action failed: server unreachable.');
        } finally {
            if (btn) btn.disabled = false;
        }
    };

    window.handleCandidateHold = async function() {
        if (!currentReviewCandidateId) return;
        const hrNotes = document.getElementById('ar-hr-notes-input')?.value || "";

        try {
            const res = await authFetch(`${API_BASE}/candidates/${currentReviewCandidateId}/hold`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hr_notes: hrNotes })
            });
            const data = await res.json();

            if (res.ok) {
                showSuccessToast(`Candidate placed On Hold.`);
                const statusBadge = document.getElementById('ar-current-status-badge');
                if (statusBadge) {
                    statusBadge.className = "hr-status-badge on-hold";
                    statusBadge.textContent = "On Hold";
                }
                fetchCandidateAuditLogs(currentReviewCandidateId);
                updateApprovalKPIs();
            } else {
                showErrorToast(extractErrorMessage(data, 'Hold action failed.'));
            }
        } catch (err) {
            console.error("Error putting candidate on hold:", err);
            showErrorToast('Hold action failed: server unreachable.');
        }
    };

    // ─── Email Preview Modal Handlers ─────────────────────────────────────

    window.openEmailPreviewModal = async function() {
        if (!currentReviewCandidateId) return;
        const modal = document.getElementById('email-preview-modal');
        if (!modal) return;

        try {
            const res = await authFetch(`${API_BASE}/candidates/${currentReviewCandidateId}/email-preview`);
            const data = await res.json();
            if (!res.ok) {
                showErrorToast(extractErrorMessage(data, 'Could not generate email preview.'));
                return;
            }

            document.getElementById('ep-to-email').textContent = data.to_email || "candidate@example.com";
            document.getElementById('ep-subject').textContent = data.subject || "Shortlist Invitation";
            document.getElementById('ep-sender').textContent = data.hr_name || "HR Talent Team";
            document.getElementById('ep-html-view').innerHTML = data.html_body || "<p>Email template preview</p>";
            document.getElementById('ep-text-view').textContent = data.plain_text_body || "";

            switchEmailTab('html');
            modal.classList.remove('hidden');
            lucide.createIcons();
        } catch (err) {
            console.error("Error generating email preview:", err);
            showErrorToast('Could not load email preview: server unreachable.');
        }
    };

    window.closeEmailPreviewModal = function() {
        const modal = document.getElementById('email-preview-modal');
        if (modal) modal.classList.add('hidden');
    };

    window.switchEmailTab = function(tab) {
        const btnHtml = document.getElementById('btn-email-tab-html');
        const btnText = document.getElementById('btn-email-tab-text');
        const viewHtml = document.getElementById('ep-html-view');
        const viewText = document.getElementById('ep-text-view');

        if (tab === 'text') {
            btnHtml.classList.remove('active');
            btnText.classList.add('active');
            viewHtml.classList.add('hidden');
            viewText.classList.remove('hidden');
        } else {
            btnText.classList.remove('active');
            btnHtml.classList.add('active');
            viewText.classList.add('hidden');
            viewHtml.classList.remove('hidden');
        }
    };


    // ─── Email Inputs Keydown Listeners (Enter key support) ───────────────
    document.getElementById('ar-cand-email-input')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            window.saveCandidateEmailDirectly();
        }
    });

    document.getElementById('quick-email-input')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            window.submitQuickEmailModal();
        }
    });

    document.getElementById('cd-spec-email-input')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            window.saveCandidateEmailFromDeepDive();
        }
    });

    document.getElementById('modal-approve-cand-email')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            window.confirmApproveCandidate();
        }
    });

    // ─── Boot ─────────────────────────────────────────────────────────────
    checkAuthState();
});
