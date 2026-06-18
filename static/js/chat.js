document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const chatMessages = document.getElementById('chatMessages');
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const suggestionsContainer = document.getElementById('suggestions');
    const loginBtn = document.getElementById('loginBtn');
    const registerBtn = document.getElementById('registerBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const shortAnswerBtn = document.getElementById('shortAnswerBtn');
    const longAnswerBtn = document.getElementById('longAnswerBtn');
    const clearChatBtns = document.querySelectorAll('.clear-chat-btn');
    const clearInputBtn = document.getElementById('clearInputBtn');

    // Estado de estilo de respuesta
    let currentAnswerStyle = 'largo';
    const loginModal = document.getElementById('loginModal');
    const registerModal = document.getElementById('registerModal');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const forgotPasswordLink = document.getElementById('forgotPasswordLink');
    const toggleSidebarBtn = document.querySelector('.toggle-sidebar');
    const sidebar = document.querySelector('.sidebar');
    
    // Variables globales
    let isOnline = true;
    let lastHealthCheck = 0;
    let healthCheckInterval = null;
    const HEALTH_CHECK_INTERVAL = 60000; // 60 segundos entre checks (aumentado de 30)

    // Historial de conversación
    let conversationHistory = [];

   // Función para limpiar el chat
    function clearChat() {
        if (!chatMessages) return;
        
        if (confirm('¿Estás seguro de que quieres limpiar el historial del chat?')) {
            chatMessages.innerHTML = '';
            // Limpiar historial de conversación
            conversationHistory = [];
            console.log("Clear chat button clicked"); // Debugging line
        }
    }

    // Event Listeners
    function attachClearChatListeners() {
        document.querySelectorAll('.clear-chat-btn').forEach(btn => {
            btn.addEventListener('click', clearChat);
        });
    }

    attachClearChatListeners();

    if (clearInputBtn) {
        clearInputBtn.addEventListener('click', () => {
            messageInput.value = '';
        });
    }

    // Event listeners para botones de estilo de respuesta
    shortAnswerBtn.addEventListener('click', () => {
        currentAnswerStyle = 'corto';
        shortAnswerBtn.classList.add('active');
        longAnswerBtn.classList.remove('active');
    });

    longAnswerBtn.addEventListener('click', () => {
        currentAnswerStyle = 'largo';
        longAnswerBtn.classList.add('active');
        shortAnswerBtn.classList.remove('active');
    });
    const connectionStatus = document.querySelector('.status-indicator');

    function updateConnectionStatus() {
        if (isOnline) {
            connectionStatus.style.backgroundColor = 'var(--success-color)';
            connectionStatus.nextElementSibling.textContent = 'Asistente en línea';
        } else {
            connectionStatus.style.backgroundColor = 'var(--accent-color)';
            connectionStatus.nextElementSibling.textContent = 'Sin conexión';
        }
    }

    // Detectar cambios en la conexión
    window.addEventListener('online', () => {
        isOnline = true;
        updateConnectionStatus();
    });

    window.addEventListener('offline', () => {
        isOnline = false;
        updateConnectionStatus();
    });

    // Verificar si el servidor está accesible
    async function checkServerConnection() {
        const now = Date.now();
        
        // Evitar hacer demasiadas peticiones
        if (now - lastHealthCheck < HEALTH_CHECK_INTERVAL) {
            return;
        }
        
        lastHealthCheck = now;
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 segundos timeout
            
            const response = await fetch(`${API_CONFIG.BASE_URL}/health`, { 
                method: 'GET',
                cache: 'no-cache',
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (response.ok) {
                isOnline = true;
            } else {
                isOnline = false;
            }
        } catch (e) {
            isOnline = false;
        }
        
        updateConnectionStatus();
    }

    // Función para iniciar el monitoreo de conexión de manera controlada
    function startConnectionMonitoring() {
        // Limpiar intervalo existente si hay uno
        if (healthCheckInterval) {
            clearInterval(healthCheckInterval);
        }
        
        // Hacer un check inicial
        checkServerConnection();
        
        // Configurar intervalo para checks periódicos
        healthCheckInterval = setInterval(checkServerConnection, HEALTH_CHECK_INTERVAL);
    }

    // Función para detener el monitoreo
    function stopConnectionMonitoring() {
        if (healthCheckInterval) {
            clearInterval(healthCheckInterval);
            healthCheckInterval = null;
        }
    }

    // Configuración de API
    const API_CONFIG = {
        BASE_URL: window.location.origin,
        ENDPOINTS: {
            CHAT: '/api/chatbot/preguntar',
            SUGGESTIONS: '/api/chatbot/sugerencias',
            LOGIN: '/api/auth/login',
            REGISTER: '/api/auth/registrar',
            PROFILE: '/api/auth/perfil',
            RESET_REQUEST: '/api/auth/reset-password-request',
            RESET_PASSWORD: '/api/auth/reset-password'
        },
        HEADERS: {
            JSON: { 'Content-Type': 'application/json' }
        }
    };

    // Función para construir URLs de API
    function getApiUrl(endpoint) {
        return `${API_CONFIG.BASE_URL}${endpoint}`;
    }

    // Función para obtener headers con autorización si existe
    function getHeaders(includeAuth = true) {
        const headers = { ...API_CONFIG.HEADERS.JSON };
        
        if (includeAuth) {
            const token = localStorage.getItem('authToken');
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
        }
        
        return headers;
    }

    // Función para realizar peticiones a la API
    async function apiRequest(endpoint, options = {}) {
        try {
            const url = getApiUrl(endpoint);
            const response = await fetch(url, options);
            
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.detail || 'Error en la petición');
            }
            
            return await response.json().catch(() => ({}));
        } catch (error) {
            console.error('Error en la petición API:', error);
            throw error;
        }
    }

    // Funciones de API
    async function sendChatMessage(message) {
        const options = {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({
                pregunta: message,
                estilo: currentAnswerStyle
            })
        };
        
        return apiRequest(API_CONFIG.ENDPOINTS.CHAT, options);
    }

    async function getSuggestions() {
        return apiRequest(API_CONFIG.ENDPOINTS.SUGGESTIONS);
    }

    async function performLogin(email, password) {
        const options = {
            method: 'POST',
            headers: API_CONFIG.HEADERS.JSON,
            body: JSON.stringify({ email, password })
        };
        
        return apiRequest(API_CONFIG.ENDPOINTS.LOGIN, options);
    }

    // API URL
    const API_URL = window.location.origin;

    // Estado
    let token = localStorage.getItem('authToken');
    let userName = 'Usuario';
    
    // Intentar obtener el nombre de usuario del localStorage
   try {
        const userData = localStorage.getItem('user');
        if (userData && typeof userData === 'string' && userData.trim() !== "") {
            const user = JSON.parse(userData);
            userName = user.nombre || 'Usuario';
        }
    } catch (error) {
        console.error('Error al obtener datos de usuario:', error);
    }
    
    let isLoading = false;

    // Comprobar estado de autenticación
    // La verificación de autenticación se maneja en auth.js
    loadSuggestions();
    setupAccessibility();
    checkForResetToken();
    startConnectionMonitoring();
    
    console.log('🔧 Chatbot inicializado correctamente');
    console.log('📝 Para diagnosticar problemas, ejecuta en la consola:');
    console.log('  - checkChatbotInput()');
    console.log('  - verifyToken()');
    console.log('  - clearAuth()');

    // Event Listeners
    if (messageInput) {
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    if (toggleSidebarBtn) {
        toggleSidebarBtn.addEventListener('click', () => {
            sidebar.classList.toggle('show');
            console.log('Sidebar toggled, clases actuales:', sidebar.className);
        });
    }

    if (loginBtn) {
        loginBtn.addEventListener('click', () => {
            openModal('loginModal');
        });
    }

    if (registerBtn) {
        registerBtn.addEventListener('click', () => {
            openModal('registerModal');
        });
    }

    // El botón de logout se maneja en auth.js

    if (forgotPasswordLink) {
        forgotPasswordLink.addEventListener('click', (e) => {
            e.preventDefault();
            closeModal('loginModal');
            openModal('forgotPasswordModal');
        });
    }

    // Cerrar modales al hacer clic en el botón de cierre o fuera
    document.querySelectorAll('.close-modal').forEach(button => {
        button.addEventListener('click', () => {
            const modalId = button.getAttribute('data-close-modal');
            closeModal(modalId);
        });
    });

    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                closeModal(overlay.id);
            }
        });
    });

    // Envío de formularios
    // Los formularios de autenticación se manejan en auth.js

    // Verificar si hay un token de restablecimiento en la URL
    checkForResetToken();

    // Funciones
    // Las funciones de autenticación se manejan en auth.js

    async function loadSuggestions() {
        if (!suggestionsContainer) {
            console.error('Contenedor de sugerencias no encontrado');
            return;
        }
        
        console.log('Cargando sugerencias...');
        
        try {
            const response = await fetch(`${API_URL}/api/chatbot/sugerencias`);
            console.log('Respuesta de la API:', response.status);
            
            if (response.ok) {
                const data = await response.json();
                console.log('Datos recibidos:', data);
                
                if (data && data.sugerencias && Array.isArray(data.sugerencias)) {
                    suggestionsContainer.innerHTML = '';
                    data.sugerencias.forEach(suggestion => {
                        const div = document.createElement('div');
                        div.className = 'suggestion';
                        div.setAttribute('tabindex', '0');
                        div.setAttribute('role', 'button');
                        div.textContent = suggestion;
                        div.addEventListener('click', () => {
                            messageInput.value = suggestion;
                            sendMessage();
                        });
                        div.addEventListener('keydown', (e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault();
                                messageInput.value = suggestion;
                                sendMessage();
                            }
                        });
                        suggestionsContainer.appendChild(div);
                    });
                    console.log('✅ Sugerencias cargadas correctamente:', data.sugerencias.length, 'sugerencias');
                } else {
                    throw new Error('Formato de sugerencias inválido');
                }
            } else {
                throw new Error(`Error HTTP: ${response.status}`);
            }
        } catch (error) {
            console.error('Error al cargar sugerencias:', error);
            // Sugerencias alternativas si la API falla
            const fallbackSuggestions = [
                "¿Cuántos monitores hay en stock?",
                "¿Cuál es el producto más caro?",
                "¿Hay esferos disponibles?",
                "¿Cuánto cuesta un teclado?",
                "¿Qué productos están por acabarse?",
                "¿Tienen cuadernos disponibles?",
                "¿Cuál es el producto más barato?",
                "Listar todos los productos"
            ];
            
            suggestionsContainer.innerHTML = '';
            fallbackSuggestions.forEach(suggestion => {
                const div = document.createElement('div');
                div.className = 'suggestion';
                div.setAttribute('tabindex', '0');
                div.setAttribute('role', 'button');
                div.textContent = suggestion;
                div.addEventListener('click', () => {
                    messageInput.value = suggestion;
                    sendMessage();
                });
                div.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        messageInput.value = suggestion;
                        sendMessage();
                    }
                });
                suggestionsContainer.appendChild(div);
            });
            console.log('✅ Sugerencias de respaldo cargadas:', fallbackSuggestions.length, 'sugerencias');
        }
    }

    function addMessage(text, sender, time = formatTimeNow()) {
        if (!chatMessages) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message fade-in`;
        messageDiv.textContent = text;
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = time;
        
        messageDiv.appendChild(timeDiv);
        chatMessages.appendChild(messageDiv);
        
        // Scroll al fondo
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function formatTimeNow() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function showLoadingIndicator() {
        if (!chatMessages) return;

        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'typing-indicator';
        loadingDiv.id = 'typingIndicator';
        loadingDiv.setAttribute('aria-label', 'El asistente está escribiendo');
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('div');
            dot.className = 'typing-dot';
            loadingDiv.appendChild(dot);
        }
        
        chatMessages.appendChild(loadingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function hideLoadingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }

    async function sendMessage() {
        if (!messageInput || !chatMessages) return;

        const message = messageInput.value.trim();
        if (!message || isLoading) return;
        
        // Limpiar input
        messageInput.value = '';
        
        // Añadir mensaje al chat
        addMessage(message, 'user');
        
        // Mostrar indicador de carga
        isLoading = true;
        showLoadingIndicator();
        
        try {
            // Construir cuerpo de la petición
            const requestBody = {
                pregunta: message,
                estilo: currentAnswerStyle
            };
            
            // Verificar autenticación
            const token = localStorage.getItem('authToken');
            let endpoint = '/api/chatbot/preguntar-publico';
            let headers = { 'Content-Type': 'application/json' };
            
            if (token) {
                // Usar endpoint autenticado si hay token
                endpoint = '/api/chatbot/preguntar';
                headers['Authorization'] = `Bearer ${token}`;
            }
            
            // Realizar la petición al servidor
            const response = await fetch(`${API_URL}${endpoint}`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(requestBody)
            });
            
            if (response.status === 401 && token) {
                // Token expirado o inválido
                localStorage.removeItem('authToken');
                localStorage.removeItem('user');
                addMessage('Tu sesión ha expirado. Por favor, inicia sesión nuevamente.', 'bot');
                openModal('loginModal');
                return;
            }
            
            const data = await response.json().catch(() => ({}));
            
            // Ocultar indicador de carga
            hideLoadingIndicator();
            isLoading = false;
            
            // Añadir respuesta del bot
            if (data && data.respuesta) {
                addMessage(data.respuesta, 'bot');
            } else {
                addMessage('Lo siento, no pude procesar tu solicitud en este momento.', 'bot');
            }
        } catch (error) {
            console.error('Error al enviar mensaje:', error);
            hideLoadingIndicator();
            isLoading = false;
            addMessage('Lo siento, ocurrió un error al procesar tu mensaje. Por favor, intenta nuevamente.', 'bot');
        }
    }

    // Las funciones de autenticación se manejan en auth.js

    // Las funciones openModal y closeModal se manejan en auth.js

    function setupAccessibility() {
        // Asegurar que los elementos interactivos sean accesibles por teclado
        document.querySelectorAll('button, [role="button"]').forEach(element => {
            if (!element.getAttribute('tabindex')) {
                element.setAttribute('tabindex', '0');
            }
        });
    }

    function checkForResetToken() {
        // Verificar si hay un token de restablecimiento en la URL
        const urlParams = new URLSearchParams(window.location.search);
        const resetToken = urlParams.get('token');
        
        if (resetToken) {
            // Estamos en la página de restablecimiento de contraseña
            const resetTokenInput = document.getElementById('resetToken');
            if (resetTokenInput) {
                resetTokenInput.value = resetToken;
            }
            
            // Abrir modal de restablecimiento si existe
            const resetModal = document.getElementById('resetPasswordModal');
            if (resetModal) {
                openModal('resetPasswordModal');
            }
        }
    }
    
    // Verificar la conexión al iniciar
    if (typeof checkServerConnection === 'function') {
        startConnectionMonitoring();
    }
    
    // Función global para recargar sugerencias
    window.reloadSuggestions = function() {
        console.log('Recargando sugerencias...');
        loadSuggestions();
    };
    
    // Función global para mostrar/ocultar sidebar
    window.toggleSidebar = function() {
        if (sidebar) {
            sidebar.classList.toggle('show');
            console.log('Sidebar toggled manualmente, clases actuales:', sidebar.className);
        }
    };
    
    // Función global para forzar apertura del sidebar
    window.showSidebar = function() {
        if (sidebar) {
            sidebar.classList.add('show');
            console.log('Sidebar abierto manualmente');
        }
    };
    
    // Función global para cerrar el sidebar
    window.hideSidebar = function() {
        if (sidebar) {
            sidebar.classList.remove('show');
            console.log('Sidebar cerrado manualmente');
        }
    };
    
    // Event listeners para el chat
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
    
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }
    
    // Cargar sugerencias al iniciar
    if (typeof loadSuggestions === 'function') {
        loadSuggestions();
    }
    
    // Configurar accesibilidad
    setupAccessibility();
    
    // Verificar token de reset
    checkForResetToken();
});
