document.addEventListener('DOMContentLoaded', function() {
    // Elementos del DOM
    const chatToggle = document.getElementById('chat-toggle');
    const chatWindow = document.getElementById('chat-window');
    const chatClose = document.getElementById('chat-close');
    const chatInput = document.getElementById('chat-input');
    const chatSend = document.getElementById('chat-send');
    const messagesContainer = document.getElementById('chat-messages');
    const unreadBadge = document.getElementById('unread-count');
    const typingIndicator = document.getElementById('typing-indicator');
    
    let ws = null;
    let isConnected = false;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    
    // Inicializar WebSocket
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = protocol + window.location.host + '/ws/chat/';
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = function() {
            console.log('WebSocket conectado');
            isConnected = true;
            reconnectAttempts = 0;
            updateStatus(true);
        };
        
        ws.onmessage = function(e) {
            const data = JSON.parse(e.data);
            handleWebSocketMessage(data);
        };
        
        ws.onclose = function() {
            console.log('WebSocket desconectado');
            isConnected = false;
            updateStatus(false);
            
            // Intentar reconectar
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                setTimeout(connectWebSocket, 3000 * reconnectAttempts);
            }
        };
        
        ws.onerror = function(error) {
            console.error('WebSocket error:', error);
        };
    }
    
    // Manejar mensajes del WebSocket
    function handleWebSocketMessage(data) {
        switch(data.type) {
            case 'message':
                addMessage(data.user, data.message, data.timestamp, false);
                updateUnreadCount(1);
                break;
            case 'history':
                data.messages.forEach(msg => {
                    addMessage(msg.user, msg.message, msg.timestamp, true);
                });
                break;
            case 'typing':
                handleTypingIndicator(data.user, data.is_typing);
                break;
            default:
                console.log('Mensaje no reconocido:', data);
        }
    }
    
    // Agregar mensaje al DOM
    function addMessage(user, message, timestamp, isHistory = false) {
        const messageEl = document.createElement('div');
        const currentUser = document.getElementById('chat-widget').dataset.username || '';
        const isUser = user === currentUser;
        
        messageEl.className = `message ${isUser ? 'user' : 'other'}`;
        
        // Formatear timestamp
        const date = new Date(timestamp);
        const timeStr = date.toLocaleTimeString('es-ES', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        messageEl.innerHTML = `
            <div class="message-content">
                <div class="message-user">${user}</div>
                <p class="message-text">${escapeHtml(message)}</p>
                <div class="message-time">${timeStr}</div>
            </div>
        `;
        
        messagesContainer.appendChild(messageEl);
        
        // Scroll al final solo si no es historial
        if (!isHistory) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }
    
    // Escapar HTML para prevenir XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Manejar indicador de escritura
    let typingTimeout = null;
    function handleTypingIndicator(user, isTyping) {
        if (isTyping) {
            typingIndicator.innerHTML = `
                <span style="font-size:12px;color:#666;">${user} está escribiendo...</span>
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
            `;
            typingIndicator.classList.add('active');
            
            clearTimeout(typingTimeout);
            typingTimeout = setTimeout(() => {
                typingIndicator.classList.remove('active');
            }, 3000);
        } else {
            typingIndicator.classList.remove('active');
        }
    }
    
    // Actualizar badge de no leídos
    function updateUnreadCount(increment = 0) {
        const currentCount = parseInt(unreadBadge.textContent) || 0;
        const newCount = currentCount + increment;
        unreadBadge.textContent = newCount;
        unreadBadge.style.display = newCount > 0 ? 'block' : 'none';
    }
    
    // Actualizar estado de conexión
    function updateStatus(connected) {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        
        if (statusDot && statusText) {
            if (connected) {
                statusDot.style.background = '#2ecc71';
                statusText.textContent = 'Conectado';
            } else {
                statusDot.style.background = '#e74c3c';
                statusText.textContent = 'Desconectado';
            }
        }
    }
    
    // Enviar mensaje
    function sendMessage() {
        const message = chatInput.value.trim();
        if (message && isConnected) {
            ws.send(JSON.stringify({
                type: 'message',
                message: message,
                room: 'global'
            }));
            chatInput.value = '';
            chatInput.focus();
        } else if (!isConnected) {
            alert('No hay conexión con el servidor. Intenta recargar la página.');
        }
    }
    
    // Enviar indicador de escritura
    let typingTimer = null;
    chatInput.addEventListener('input', function() {
        if (isConnected) {
            ws.send(JSON.stringify({
                type: 'typing',
                is_typing: true
            }));
            
            clearTimeout(typingTimer);
            typingTimer = setTimeout(() => {
                ws.send(JSON.stringify({
                    type: 'typing',
                    is_typing: false
                }));
            }, 1000);
        }
    });
    
    // Toggle del chat
    chatToggle.addEventListener('click', function() {
        const isVisible = chatWindow.style.display !== 'none';
        chatWindow.style.display = isVisible ? 'none' : 'flex';
        
        if (!isVisible) {
            // Resetear contador de no leídos al abrir
            unreadBadge.textContent = '0';
            unreadBadge.style.display = 'none';
            chatInput.focus();
            
            // Marcar mensajes como leídos
            if (isConnected) {
                ws.send(JSON.stringify({
                    type: 'read',
                    message_ids: [] // Marcar todos como leídos
                }));
            }
        }
    });
    
    // Cerrar chat
    chatClose.addEventListener('click', function() {
        chatWindow.style.display = 'none';
    });
    
    // Enviar con botón o Enter
    chatSend.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Cargar mensajes históricos (API REST)
    async function loadInitialMessages() {
        try {
            const response = await fetch('/api/chat/messages/');
            if (response.ok) {
                const messages = await response.json();
                messages.forEach(msg => {
                    addMessage(msg.user.username, msg.message, msg.timestamp, true);
                });
                
                // Actualizar contador de no leídos
                const unread = messages.filter(msg => !msg.is_read).length;
                if (unread > 0) {
                    unreadBadge.textContent = unread;
                    unreadBadge.style.display = 'block';
                }
            }
        } catch (error) {
            console.error('Error cargando mensajes:', error);
        }
    }
    
    // Inicializar
    connectWebSocket();
    loadInitialMessages();
    
    // Configurar data attribute para el usuario actual
    // Esto debe ser establecido desde Django
    const widget = document.getElementById('chat-widget');
    if (widget && window.USER_DATA) {
        widget.dataset.username = window.USER_DATA.username;
    }
});