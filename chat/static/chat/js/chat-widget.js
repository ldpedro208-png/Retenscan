// chat/static/chat/js/chat-widget.js

(function() {
    'use strict';

    // ============================================
    // CONFIGURACIÓN
    // ============================================
    const API_URLS = {
        conversations: '/api/chat/messages/conversations/',
        unread_count: '/api/chat/messages/unread_count/',
        my_subjects: '/api/chat/messages/my_subjects/',
        conversation: function(userId) {
            return `/api/chat/messages/conversation/${userId}/`;
        },
        search_users: function(query) {
            return `/api/chat/users/?search=${encodeURIComponent(query)}`;
        }
    };

    const WS_URL = `ws://${window.location.host}/ws/chat/`;
    const WS_SUBJECT_URL = `ws://${window.location.host}/ws/subject-chat/`;

    console.log('========== CHAT WIDGET CONFIG ==========');
    console.log('API_URLS:', API_URLS);
    console.log('WS_URL:', WS_URL);
    console.log('WS_SUBJECT_URL:', WS_SUBJECT_URL);
    console.log('=========================================');

    // ============================================
    // ESTADO
    // ============================================
    const state = {
        ws: null,
        currentUser: window.USER_DATA || { id: null, username: null, rol: null, isAdmin: false },
        currentConversation: null,
        currentSubjectChannel: null,
        conversations: [],
        subjects: [],
        isTyping: false,
        typingTimeout: null,
        typingHideTimeout: null,
        isConnected: false,
        reconnectAttempts: 0,
        keepAliveInterval: null,
        isInSubjectsPanel: false,
        isSubjectsLoaded: false,
        isSwitching: false,   // ✅ NUEVO: evita reconexión al cambiar de canal
    };

    console.log('👤 Usuario actual:', state.currentUser);

    // ============================================
    // DOM REFERENCES
    // ============================================
    function getElement(id) {
        const el = document.getElementById(id);
        if (!el) {
            console.warn(`Elemento no encontrado: #${id}`);
        }
        return el;
    }

    const dom = {
        get widget() { return getElement('chat-widget'); },
        get toggle() { return getElement('chat-toggle'); },
        get window() { return getElement('chat-window'); },
        get close() { return getElement('chat-close'); },
        get messages() { return getElement('chat-messages'); },
        get input() { return getElement('chat-input'); },
        get send() { return getElement('chat-send'); },
        get typingIndicator() { return getElement('typing-indicator'); },
        get typingText() { return getElement('typing-text'); },
        get statusText() { return getElement('status-text'); },
        get statusDot() { return getElement('status-dot'); },
        get unreadCount() { return getElement('unread-count'); },
        get conversationList() { return getElement('conversation-list'); },
        get conversationsContainer() { return getElement('chat-conversations'); },
        get messagesContainer() { return getElement('chat-messages-container'); },
        get backButton() { return getElement('back-to-conversations'); },
        get chatWithUser() { return getElement('chat-with-user'); },
        get searchUsers() { return getElement('search-users'); },
        // ✅ Materias
        get subjectsToggle() { return getElement('subjects-toggle'); },
        get subjectsCount() { return getElement('subjects-count'); },
        get subjectsPanel() { return getElement('subjects-panel'); },
        get subjectsBack() { return getElement('subjects-back'); },
        get subjectsTotal() { return getElement('subjects-total'); },
        get subjectsSearchInput() { return getElement('subjects-search-input'); },
        get subjectsListWidget() { return getElement('subjects-list-widget'); },
    };

    // ============================================
    // UTILIDADES
    // ============================================
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;

        if (diff < 60000) return 'Ahora';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h`;
        if (diff < 172800000) return 'Ayer';
        return date.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function scrollToBottom() {
        if (dom.messages) {
            dom.messages.scrollTop = dom.messages.scrollHeight;
        }
    }

    function updateStatus(text, status) {
        if (dom.statusText) dom.statusText.textContent = text;
        if (dom.statusDot) dom.statusDot.className = `status-dot ${status || ''}`;
    }

    function hideTypingIndicator() {
        if (dom.typingIndicator) {
            dom.typingIndicator.style.display = 'none';
        }
        if (state.typingHideTimeout) {
            clearTimeout(state.typingHideTimeout);
            state.typingHideTimeout = null;
        }
    }

    function clearKeepAlive() {
        if (state.keepAliveInterval) {
            clearInterval(state.keepAliveInterval);
            state.keepAliveInterval = null;
        }
    }

    function startKeepAlive() {
        clearKeepAlive();
        state.keepAliveInterval = setInterval(() => {
            if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                state.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 20000);
    }

    // ============================================
    // API FUNCTIONS
    // ============================================
    async function fetchConversations() {
        try {
            const response = await fetch(API_URLS.conversations, {
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                credentials: 'same-origin',
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('❌ Error fetching conversations:', error);
            return [];
        }
    }

    async function fetchMessages(userId) {
        try {
            const response = await fetch(API_URLS.conversation(userId), {
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                credentials: 'same-origin',
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('❌ Error fetching messages:', error);
            return { messages: [], user: null };
        }
    }

    async function fetchUnreadCount() {
        try {
            const response = await fetch(API_URLS.unread_count, {
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                credentials: 'same-origin',
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            updateUnreadBadge(data.unread_count);
            return data.unread_count;
        } catch (error) {
            console.error('❌ Error fetching unread count:', error);
            return 0;
        }
    }

    async function fetchMySubjects() {
        try {
            const response = await fetch(API_URLS.my_subjects, {
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                credentials: 'same-origin',
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            console.log('📚 Materias cargadas:', data.count);
            return data;
        } catch (error) {
            console.error('❌ Error fetching subjects:', error);
            return { count: 0, subjects: [] };
        }
    }

    async function searchUsers(query) {
        try {
            const response = await fetch(API_URLS.search_users(query), {
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                credentials: 'same-origin',
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('❌ Error searching users:', error);
            return [];
        }
    }

    // ============================================
    // WEB SOCKET - CHAT PRIVADO
    // ============================================
    function connectWebSocket(userId = null) {
        const wsUrl = userId ? `${WS_URL}${userId}/` : WS_URL;
        console.log('🔌 WebSocket URL:', wsUrl);

        // ✅ Marcar cambio de canal para evitar reconexión automática
        state.isSwitching = true;

        if (state.ws) {
            try { state.ws.close(1000, 'switching'); } catch (e) {}
        }

        try {
            state.ws = new WebSocket(wsUrl);

            state.ws.onopen = function() {
                console.log('✅ WebSocket CONNECTED');
                state.isConnected = true;
                state.reconnectAttempts = 0;
                state.isSwitching = false;   // ✅ Desmarcar al conectar
                updateStatus('Conectado', 'connected');
                hideTypingIndicator();
                startKeepAlive();
            };

            state.ws.onmessage = function(e) {
                try {
                    const data = JSON.parse(e.data);
                    if (data.type === 'pong') return;
                    handleWebSocketMessage(data);
                } catch (error) {
                    console.error('❌ Error parsing WebSocket message:', error);
                }
            };

            state.ws.onclose = function(e) {
                console.log(`⚠️ WebSocket DISCONNECTED - Code: ${e.code}`);

                // ✅ Si es cambio de canal, no reconectar
                if (state.isSwitching) {
                    console.log('🔄 Cambio de canal intencional, no se reconecta.');
                    return;
                }

                state.isConnected = false;
                updateStatus('Desconectado', 'disconnected');
                hideTypingIndicator();
                clearKeepAlive();

                const delays = [3000, 6000, 12000, 24000, 30000];
                if (state.reconnectAttempts < delays.length) {
                    const delay = delays[state.reconnectAttempts];
                    state.reconnectAttempts++;
                    console.log(`🔄 Reconnecting in ${delay/1000}s...`);
                    setTimeout(() => {
                        if (state.currentSubjectChannel) {
                            connectSubjectWebSocket(state.currentSubjectChannel);
                        } else {
                            connectWebSocket(state.currentConversation);
                        }
                    }, delay);
                }
            };

            state.ws.onerror = function(e) {
                console.error('❌ WebSocket error:', e);
            };
        } catch (error) {
            console.error('❌ Error connecting WebSocket:', error);
            state.isSwitching = false;
        }
    }

    // ============================================
    // WEB SOCKET - CHAT POR MATERIA
    // ============================================
    function connectSubjectWebSocket(subjectId) {
        const wsUrl = `${WS_SUBJECT_URL}${subjectId}/`;
        console.log('🔌 WebSocket MATERIA URL:', wsUrl);

        // ✅ Marcar cambio de canal
        state.isSwitching = true;

        if (state.ws) {
            try { state.ws.close(1000, 'switching'); } catch (e) {}
        }

        try {
            state.ws = new WebSocket(wsUrl);

            state.ws.onopen = function() {
                console.log('✅ WebSocket MATERIA CONNECTED');
                state.isConnected = true;
                state.reconnectAttempts = 0;
                state.isSwitching = false;   // ✅ Desmarcar al conectar
                updateStatus('Conectado', 'connected');
                hideTypingIndicator();
                startKeepAlive();
            };

            state.ws.onmessage = function(e) {
                try {
                    const data = JSON.parse(e.data);
                    if (data.type === 'pong') return;
                    handleSubjectWebSocketMessage(data);
                } catch (error) {
                    console.error('❌ Error parsing WebSocket message:', error);
                }
            };

            state.ws.onclose = function(e) {
                console.log(`⚠️ WebSocket MATERIA DISCONNECTED - Code: ${e.code}`);

                // ✅ Si es cambio de canal, no reconectar
                if (state.isSwitching) {
                    console.log('🔄 Cambio de canal intencional, no se reconecta.');
                    return;
                }

                state.isConnected = false;
                updateStatus('Desconectado', 'disconnected');
                hideTypingIndicator();
                clearKeepAlive();

                const delays = [3000, 6000, 12000, 24000, 30000];
                if (state.reconnectAttempts < delays.length) {
                    const delay = delays[state.reconnectAttempts];
                    state.reconnectAttempts++;
                    console.log(`🔄 Reconnecting MATERIA in ${delay/1000}s...`);
                    setTimeout(() => {
                        if (state.currentSubjectChannel) {
                            connectSubjectWebSocket(state.currentSubjectChannel);
                        } else {
                            connectWebSocket(state.currentConversation);
                        }
                    }, delay);
                }
            };

            state.ws.onerror = function(e) {
                console.error('❌ WebSocket MATERIA error:', e);
            };
        } catch (error) {
            console.error('❌ Error connecting subject WebSocket:', error);
            state.isSwitching = false;
        }
    }

    function sendWebSocketMessage(data) {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify(data));
            return true;
        }
        console.warn('⚠️ WebSocket not connected');
        return false;
    }

    // ============================================
    // MANEJADORES - CHAT PRIVADO
    // ============================================
    function handleWebSocketMessage(data) {
        switch (data.type) {
            case 'message':
                handleNewMessage(data);
                break;
            case 'history':
                handleHistoryMessages(data.messages);
                break;
            case 'typing':
                handleTypingIndicator(data);
                break;
            default:
                console.log('📨 Unknown message type:', data.type);
        }
    }

    function handleNewMessage(data) {
        console.log('💬 New message from:', data.sender);

        if (data.sender_id === state.currentConversation) {
            hideTypingIndicator();
        }

        const isForCurrent = state.currentConversation && (
            (data.sender_id === state.currentConversation && data.receiver_id === state.currentUser.id) ||
            (data.sender_id === state.currentUser.id && data.receiver_id === state.currentConversation)
        );

        if (isForCurrent) {
            if (!isMessageInDom(data)) {
                appendMessage(data);
            }
        }

        loadConversations();
        fetchUnreadCount();
    }

    function handleHistoryMessages(messages) {
        if (dom.messages) {
            dom.messages.innerHTML = '';
            if (messages && messages.length > 0) {
                messages.forEach(msg => appendMessage(msg));
            } else {
                dom.messages.innerHTML = '<div class="no-messages">No hay mensajes aún</div>';
            }
            scrollToBottom();
        }
    }

    function handleTypingIndicator(data) {
        if (data.sender_id === state.currentUser.id) return;
        if (data.sender_id !== state.currentConversation) return;

        if (dom.typingIndicator) {
            if (data.is_typing) {
                if (dom.typingText) {
                    dom.typingText.textContent = `${escapeHtml(data.sender)} está escribiendo`;
                }
                dom.typingIndicator.style.display = 'flex';
                if (state.typingHideTimeout) clearTimeout(state.typingHideTimeout);
                state.typingHideTimeout = setTimeout(hideTypingIndicator, 3000);
            } else {
                hideTypingIndicator();
            }
        }
    }

    // ============================================
    // MANEJADORES - CHAT POR MATERIA
    // ============================================
    function handleSubjectWebSocketMessage(data) {
        switch (data.type) {
            case 'message':
                handleNewSubjectMessage(data);
                break;
            case 'history':
                handleSubjectHistory(data.messages, data.pinned_messages);
                break;
            case 'typing':
                handleSubjectTyping(data);
                break;
            case 'pin_update':
                handlePinUpdate(data);
                break;
            default:
                console.log('📨 Unknown subject message type:', data.type);
        }
    }

    function handleNewSubjectMessage(data) {
        console.log('💬 New subject message from:', data.sender);

        if (data.sender_id !== state.currentUser.id) {
            hideTypingIndicator();
        }

        if (!isMessageInDom(data)) {
            appendSubjectMessage(data);
        }
    }

    function handleSubjectHistory(messages, pinnedMessages) {
        if (dom.messages) {
            dom.messages.innerHTML = '';

            if (pinnedMessages && pinnedMessages.length > 0) {
                const pinnedSection = document.createElement('div');
                pinnedSection.className = 'pinned-messages-section';
                pinnedSection.innerHTML = `<div class="pinned-header">📌 Mensajes Fijados</div>`;
                pinnedMessages.forEach(msg => {
                    pinnedSection.appendChild(createSubjectMessageElement(msg));
                });
                dom.messages.appendChild(pinnedSection);
            }

            if (messages && messages.length > 0) {
                messages.forEach(msg => {
                    dom.messages.appendChild(createSubjectMessageElement(msg));
                });
            } else {
                dom.messages.innerHTML = '<div class="no-messages">No hay mensajes aún</div>';
            }
            scrollToBottom();
        }
    }

    function handleSubjectTyping(data) {
        if (data.sender_id === state.currentUser.id) return;

        if (dom.typingIndicator) {
            if (data.is_typing) {
                if (dom.typingText) {
                    dom.typingText.textContent = `${escapeHtml(data.sender)} está escribiendo`;
                }
                dom.typingIndicator.style.display = 'flex';
                if (state.typingHideTimeout) clearTimeout(state.typingHideTimeout);
                state.typingHideTimeout = setTimeout(hideTypingIndicator, 3000);
            } else {
                hideTypingIndicator();
            }
        }
    }

    function handlePinUpdate(data) {
        const msgElement = document.querySelector(`.message[data-message-id="${data.message_id}"]`);
        if (!msgElement) return;
        const pinnedBadge = msgElement.querySelector('.pinned-badge');
        if (data.action === 'pin' && !pinnedBadge) {
            const badge = document.createElement('span');
            badge.className = 'pinned-badge';
            badge.textContent = '📌 Fijado';
            msgElement.querySelector('.message-content')?.prepend(badge);
        } else if (data.action === 'unpin' && pinnedBadge) {
            pinnedBadge.remove();
        }
    }

    // ============================================
    // DETECCIÓN DE DUPLICADOS
    // ============================================
    function isMessageInDom(data) {
        if (!dom.messages) return false;
        const existing = dom.messages.querySelectorAll('.message');
        const messageId = data.message_id || data.id;
        for (let i = existing.length - 1; i >= 0; i--) {
            const el = existing[i];
            if (messageId && el.dataset.messageId === String(messageId)) {
                return true;
            }
            const content = el.querySelector('.message-content');
            if (content && content.textContent === data.message) {
                const isOwn = el.classList.contains('own');
                const senderMatch = (isOwn && data.sender_id === state.currentUser.id) ||
                                    (!isOwn && data.sender_id !== state.currentUser.id);
                if (senderMatch) return true;
            }
        }
        return false;
    }

    // ============================================
    // RENDER - CHAT PRIVADO
    // ============================================
    function appendMessage(data) {
        if (!dom.messages) return;

        const noMsg = dom.messages.querySelector('.no-messages');
        if (noMsg) noMsg.remove();

        const isOwn = data.sender_id === state.currentUser.id;
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${isOwn ? 'own' : 'other'}`;
        msgDiv.dataset.messageId = data.id || data.message_id;

        const senderInfo = isOwn ? '' : `<div class="message-sender">${escapeHtml(data.sender)}</div>`;
        const time = formatDate(data.timestamp);

        msgDiv.innerHTML = `
            ${senderInfo}
            <div class="message-content">${escapeHtml(data.message)}</div>
            <div class="message-time">${time}</div>
        `;

        dom.messages.appendChild(msgDiv);
        scrollToBottom();
    }

    // ============================================
    // RENDER - CHAT POR MATERIA
    // ============================================
    function appendSubjectMessage(data) {
        if (!dom.messages) return;

        const noMsg = dom.messages.querySelector('.no-messages');
        if (noMsg) noMsg.remove();

        const msgDiv = createSubjectMessageElement(data);
        dom.messages.appendChild(msgDiv);
        scrollToBottom();
    }

    function createSubjectMessageElement(data) {
        const isOwn = data.sender_id === state.currentUser.id;
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${isOwn ? 'own' : 'other'}`;
        msgDiv.dataset.messageId = data.message_id || data.id;

        let badges = '';
        if (data.is_announcement) badges += '<span class="announcement-badge">📢 Anuncio</span>';
        if (data.is_pinned) badges += '<span class="pinned-badge">📌 Fijado</span>';
        if (data.sender_role === 'teacher' && !isOwn) badges += '<span class="teacher-badge">👨‍🏫</span>';

        const senderInfo = isOwn ? '' : `<div class="message-sender">${escapeHtml(data.sender)} ${badges}</div>`;
        const time = formatDate(data.timestamp);

        msgDiv.innerHTML = `
            ${senderInfo}
            <div class="message-content">${escapeHtml(data.message)}</div>
            <div class="message-time">${time}</div>
        `;

        return msgDiv;
    }

    function renderConversationList(conversations) {
        if (!dom.conversationList) return;

        dom.conversationList.innerHTML = '';

        if (!conversations || conversations.length === 0) {
            dom.conversationList.innerHTML = '<div class="no-conversations">No hay conversaciones</div>';
            return;
        }

        conversations.forEach(conv => {
            const div = document.createElement('div');
            div.className = 'conversation-item';
            div.dataset.userId = conv.user.id;

            const unreadBadge = conv.unread_count > 0
                ? `<span class="unread-badge">${conv.unread_count}</span>`
                : '';

            const lastMessage = conv.last_message && conv.last_message.message ? conv.last_message.message : 'Sin mensajes';
            const lastTime = conv.last_message && conv.last_message.timestamp ? formatDate(conv.last_message.timestamp) : '';

            div.innerHTML = `
                <div class="conversation-avatar">
                    <span class="avatar-letter">${conv.user.username.charAt(0).toUpperCase()}</span>
                </div>
                <div class="conversation-info">
                    <div class="conversation-name">${escapeHtml(conv.user.username)}</div>
                    <div class="conversation-last-message">${escapeHtml(lastMessage)}</div>
                </div>
                <div class="conversation-meta">
                    <div class="conversation-time">${lastTime}</div>
                    ${unreadBadge}
                </div>
            `;

            div.addEventListener('click', () => openConversation(conv.user.id));
            dom.conversationList.appendChild(div);
        });
    }

    function renderMessages(data) {
        if (!dom.messages) return;

        dom.messages.innerHTML = '';
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => appendMessage(msg));
        } else {
            dom.messages.innerHTML = '<div class="no-messages">No hay mensajes aún</div>';
        }

        if (data.user && dom.chatWithUser) {
            dom.chatWithUser.textContent = `Chat con: ${data.user.username}`;
        }

        scrollToBottom();
    }

    function updateUnreadBadge(count) {
        if (dom.unreadCount) {
            if (count > 0) {
                dom.unreadCount.textContent = count > 99 ? '99+' : count;
                dom.unreadCount.style.display = 'inline';
            } else {
                dom.unreadCount.style.display = 'none';
            }
        }
    }

    // ============================================
    // RENDER - MATERIAS
    // ============================================
    function updateSubjectsCount(count) {
        if (dom.subjectsCount) {
            dom.subjectsCount.textContent = count > 99 ? '99+' : count;
        }
        if (dom.subjectsTotal) {
            dom.subjectsTotal.textContent = count;
        }
    }

    function renderSubjectsPanel(subjects) {
        if (!dom.subjectsListWidget) return;

        dom.subjectsListWidget.innerHTML = '';

        if (!subjects || subjects.length === 0) {
            dom.subjectsListWidget.innerHTML = `
                <div class="subjects-empty">
                    <div class="subjects-empty-icon">📚</div>
                    <p>No tienes materias asignadas</p>
                    <p class="subjects-empty-hint">Contacta con tu coordinador para más información</p>
                </div>
            `;
            return;
        }

        subjects.forEach(subject => {
            const div = document.createElement('div');
            div.className = 'subject-item-widget';
            div.dataset.subjectId = subject.id;

            const unreadBadge = subject.unread_count > 0
                ? `<span class="unread-badge">${subject.unread_count}</span>`
                : '';

            const chatBadge = subject.chat_exists
                ? ''
                : '<span class="no-chat-badge">Sin chat</span>';

            div.innerHTML = `
                <div class="subject-icon">💬</div>
                <div class="subject-info">
                    <div class="subject-name">${escapeHtml(subject.nombre)}</div>
                    <div class="subject-code">${escapeHtml(subject.codigo || '')} · ${escapeHtml(subject.carrera || '')}</div>
                </div>
                <div class="subject-meta">
                    ${chatBadge}
                    ${unreadBadge}
                </div>
            `;

            div.addEventListener('click', () => openSubjectChannel(subject.id, subject.nombre));
            dom.subjectsListWidget.appendChild(div);
        });
    }

    // ============================================
    // UI NAVIGATION
    // ============================================
    function showConversationList() {
        // Notificar typing: false si aplica
        if (state.currentConversation && state.isTyping) {
            state.isTyping = false;
            clearTimeout(state.typingTimeout);
            sendWebSocketMessage({
                type: 'typing',
                is_typing: false,
                receiver_id: state.currentConversation,
            });
        }

        state.isInSubjectsPanel = false;
        state.currentSubjectChannel = null;
        state.currentConversation = null;

        if (dom.subjectsPanel) dom.subjectsPanel.style.display = 'none';
        if (dom.conversationsContainer) dom.conversationsContainer.style.display = 'block';
        if (dom.messagesContainer) dom.messagesContainer.style.display = 'none';
        if (dom.messages) dom.messages.innerHTML = '<div class="no-messages">Selecciona una conversación</div>';

        hideTypingIndicator();
        loadConversations();
    }

    function showMessagesContainer() {
        if (dom.conversationsContainer) dom.conversationsContainer.style.display = 'none';
        if (dom.subjectsPanel) dom.subjectsPanel.style.display = 'none';
        if (dom.messagesContainer) {
            dom.messagesContainer.style.display = 'flex';
            dom.messagesContainer.style.flexDirection = 'column';
        }
    }

    function openConversation(userId) {
        console.log('💬 Opening conversation with user:', userId);

        // Notificar a la conversación anterior
        if (state.currentConversation && state.currentConversation !== userId && state.isTyping) {
            state.isTyping = false;
            clearTimeout(state.typingTimeout);
            sendWebSocketMessage({
                type: 'typing',
                is_typing: false,
                receiver_id: state.currentConversation,
            });
        }

        state.currentSubjectChannel = null;
        state.currentConversation = userId;
        state.reconnectAttempts = 0;
        hideTypingIndicator();
        showMessagesContainer();
        loadMessages(userId);

        connectWebSocket(userId);
    }

    function openSubjectChannel(subjectId, subjectName) {
        console.log('📚 Opening subject channel:', subjectId, subjectName);

        state.currentConversation = null;
        state.currentSubjectChannel = subjectId;
        state.reconnectAttempts = 0;

        showMessagesContainer();

        if (dom.chatWithUser) {
            dom.chatWithUser.textContent = `📚 ${subjectName}`;
        }

        if (dom.messages) {
            dom.messages.innerHTML = '<div class="no-messages">Cargando mensajes...</div>';
        }

        connectSubjectWebSocket(subjectId);
    }

    async function toggleSubjectsPanel() {
        state.isInSubjectsPanel = !state.isInSubjectsPanel;

        if (state.isInSubjectsPanel) {
            if (dom.subjectsPanel) dom.subjectsPanel.style.display = 'flex';
            if (dom.conversationsContainer) dom.conversationsContainer.style.display = 'none';
            if (dom.messagesContainer) dom.messagesContainer.style.display = 'none';

            if (!state.isSubjectsLoaded) {
                const data = await fetchMySubjects();
                state.subjects = data.subjects || [];
                updateSubjectsCount(data.count);
                renderSubjectsPanel(state.subjects);
                state.isSubjectsLoaded = true;
            }
        } else {
            if (dom.subjectsPanel) dom.subjectsPanel.style.display = 'none';
            showConversationList();
        }
    }

    // ============================================
    // LOAD FUNCTIONS
    // ============================================
    async function loadConversations() {
        const conversations = await fetchConversations();
        state.conversations = conversations;
        renderConversationList(conversations);
    }

    async function loadMessages(userId) {
        const data = await fetchMessages(userId);
        renderMessages(data);
    }

    // ============================================
    // SEND MESSAGE
    // ============================================
    function sendMessage() {
        if (!dom.input) return;

        const message = dom.input.value.trim();
        if (!message) return;
        if (!state.currentConversation && !state.currentSubjectChannel) return;

        // Detener indicador de escritura
        if (state.isTyping) {
            state.isTyping = false;
            clearTimeout(state.typingTimeout);
            const typingData = { type: 'typing', is_typing: false };
            if (state.currentConversation) typingData.receiver_id = state.currentConversation;
            sendWebSocketMessage(typingData);
        }

        const data = { type: 'message', message: message };
        if (state.currentConversation) {
            data.receiver_id = state.currentConversation;
        }

        if (sendWebSocketMessage(data)) {
            dom.input.value = '';
            dom.input.focus();
        }
    }

    function handleTyping(isTyping) {
        if (!state.currentConversation && !state.currentSubjectChannel) return;

        if (isTyping && !state.isTyping) {
            state.isTyping = true;
            const data = { type: 'typing', is_typing: true };
            if (state.currentConversation) data.receiver_id = state.currentConversation;
            sendWebSocketMessage(data);
        }

        clearTimeout(state.typingTimeout);

        if (!isTyping) {
            if (state.isTyping) {
                state.isTyping = false;
                const data = { type: 'typing', is_typing: false };
                if (state.currentConversation) data.receiver_id = state.currentConversation;
                sendWebSocketMessage(data);
            }
            return;
        }

        state.typingTimeout = setTimeout(() => {
            if (state.isTyping) {
                state.isTyping = false;
                const data = { type: 'typing', is_typing: false };
                if (state.currentConversation) data.receiver_id = state.currentConversation;
                sendWebSocketMessage(data);
            }
        }, 1500);
    }

    // ============================================
    // SEARCH USERS
    // ============================================
    async function handleSearchUsers(query) {
        if (!query || query.length < 2) {
            loadConversations();
            return;
        }

        const users = await searchUsers(query);
        if (dom.conversationList) {
            dom.conversationList.innerHTML = '';

            if (users.length > 0) {
                users.forEach(user => {
                    const div = document.createElement('div');
                    div.className = 'conversation-item search-result';
                    div.dataset.userId = user.id;

                    div.innerHTML = `
                        <div class="conversation-avatar">
                            <span class="avatar-letter">${user.username.charAt(0).toUpperCase()}</span>
                        </div>
                        <div class="conversation-info">
                            <div class="conversation-name">${escapeHtml(user.username)}</div>
                            <div class="conversation-last-message">Iniciar conversación</div>
                        </div>
                    `;

                    div.addEventListener('click', () => openConversation(user.id));
                    dom.conversationList.appendChild(div);
                });
            } else {
                dom.conversationList.innerHTML = '<div class="no-conversations">No se encontraron usuarios</div>';
            }
        }
    }

    // ============================================
    // SEARCH SUBJECTS
    // ============================================
    function handleSearchSubjects(query) {
        const items = dom.subjectsListWidget.querySelectorAll('.subject-item-widget');
        const q = (query || '').toLowerCase().trim();

        items.forEach(item => {
            const name = item.querySelector('.subject-name')?.textContent.toLowerCase() || '';
            const code = item.querySelector('.subject-code')?.textContent.toLowerCase() || '';
            const match = !q || name.includes(q) || code.includes(q);
            item.style.display = match ? 'flex' : 'none';
        });
    }

    // ============================================
    // EVENT LISTENERS
    // ============================================
    function initEventListeners() {
        if (dom.toggle) {
            dom.toggle.addEventListener('click', function() {
                const isHidden = dom.window.style.display === 'none' || dom.window.style.display === '';
                dom.window.style.display = isHidden ? 'flex' : 'none';
                dom.window.style.flexDirection = 'column';
                if (isHidden) {
                    showConversationList();
                    fetchUnreadCount();

                    // ✅ Reconectar si no hay conexión activa
                    if (!state.isConnected) {
                        if (state.currentSubjectChannel) {
                            connectSubjectWebSocket(state.currentSubjectChannel);
                        } else {
                            connectWebSocket(state.currentConversation);
                        }
                    }
                }
            });
        }

        if (dom.close) {
            dom.close.addEventListener('click', function() {
                if (state.currentConversation && state.isTyping) {
                    state.isTyping = false;
                    clearTimeout(state.typingTimeout);
                    sendWebSocketMessage({
                        type: 'typing',
                        is_typing: false,
                        receiver_id: state.currentConversation,
                    });
                }

                // ✅ Marcar cambio para que no reconecte
                state.isSwitching = true;
                if (state.ws) {
                    try { state.ws.close(1000, 'close'); } catch (e) {}
                }
                dom.window.style.display = 'none';
            });
        }

        if (dom.send) dom.send.addEventListener('click', sendMessage);

        if (dom.input) {
            dom.input.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    sendMessage();
                }
            });

            dom.input.addEventListener('input', function() {
                const isTyping = this.value.length > 0;
                handleTyping(isTyping);
            });
        }

        if (dom.backButton) dom.backButton.addEventListener('click', showConversationList);

        if (dom.searchUsers) {
            let searchTimeout;
            dom.searchUsers.addEventListener('input', function() {
                clearTimeout(searchTimeout);
                const query = this.value.trim();
                searchTimeout = setTimeout(() => handleSearchUsers(query), 300);
            });
        }

        // ✅ Botón de materias
        if (dom.subjectsToggle) {
            dom.subjectsToggle.addEventListener('click', toggleSubjectsPanel);
        }

        // ✅ Botón volver del panel de materias
        if (dom.subjectsBack) {
            dom.subjectsBack.addEventListener('click', function() {
                state.isInSubjectsPanel = false;
                if (dom.subjectsPanel) dom.subjectsPanel.style.display = 'none';
                showConversationList();
            });
        }

        // ✅ Búsqueda de materias
        if (dom.subjectsSearchInput) {
            dom.subjectsSearchInput.addEventListener('input', function() {
                handleSearchSubjects(this.value);
            });
        }

        // Notificar typing: false al cerrar la ventana
        window.addEventListener('beforeunload', function() {
            if (state.currentConversation && state.isTyping && state.ws && state.ws.readyState === WebSocket.OPEN) {
                state.ws.send(JSON.stringify({
                    type: 'typing',
                    is_typing: false,
                    receiver_id: state.currentConversation,
                }));
            }
        });
    }

    // ============================================
    // INIT
    // ============================================
    async function init() {
        if (!state.currentUser || !state.currentUser.id) {
            console.warn('⚠️ Usuario no autenticado, el chat no se inicializará');
            return;
        }

        console.log('🚀 INITIALIZING Chat Widget');
        console.log('👤 User:', state.currentUser.username, '| Rol:', state.currentUser.rol);

        // Cargar el contador de materias al inicio
        const subjectData = await fetchMySubjects();
        state.subjects = subjectData.subjects || [];
        updateSubjectsCount(subjectData.count);
        state.isSubjectsLoaded = false;

        connectWebSocket();
        loadConversations();
        fetchUnreadCount();
        initEventListeners();

        // Actualizar contador de no leídos cada 30s
        setInterval(() => {
            if (!dom.window.style.display || dom.window.style.display === 'none') {
                fetchUnreadCount();
            }
        }, 30000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();