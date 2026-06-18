document.addEventListener('DOMContentLoaded', function () {
    console.log("Auth.js cargado correctamente.");

    // API URL - Asegúrate de que esta sea la URL correcta de tu backend
    const API_URL = window.location.origin;

    // Elementos DOM para autenticación
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const loginBtn = document.getElementById('loginBtn');
    const registerBtn = document.getElementById('registerBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const forgotPasswordLink = document.getElementById('forgotPasswordLink');

    // Limpiar cualquier token corrupto al inicio
    cleanupStorageIfNeeded();

    // Verificar si el usuario está autenticado
    checkAuthentication();

    // Event Listeners para los botones de autenticación
    if (loginBtn) {
        loginBtn.addEventListener('click', function () {
            openModal('loginModal');
        });
    }

    if (registerBtn) {
        registerBtn.addEventListener('click', function () {
            openModal('registerModal');
        });
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    if (forgotPasswordLink) {
        forgotPasswordLink.addEventListener('click', function (e) {
            e.preventDefault();
            closeModal('loginModal');
            openModal('forgotPasswordModal');
        });
    }

    // Event Listeners para los formularios
    if (loginForm) {
        loginForm.addEventListener('submit', function (e) {
            e.preventDefault();
            login();
        });
    }

    if (registerForm) {
        registerForm.addEventListener('submit', function (e) {
            e.preventDefault();
            register();
        });
    }

    // Cerrar modales cuando se hace clic en el botón de cerrar
    document.querySelectorAll('.close-modal').forEach(button => {
        button.addEventListener('click', function () {
            const modalId = button.getAttribute('data-close-modal');
            if (modalId) {
                closeModal(modalId);
            }
        });
    });

    // Funciones para la autenticación
    function cleanupStorageIfNeeded() {
        try {
            const userData = localStorage.getItem('user');
            if (userData === "undefined" || userData === null) {
                console.log('Datos de usuario inválidos detectados, limpiando almacenamiento');
                localStorage.removeItem('authToken');
                localStorage.removeItem('user');
            } else {
                // Intenta parsear para verificar que son válidos
                JSON.parse(userData);
            }
        } catch (e) {
            console.error('Error en datos almacenados, limpiando todo:', e);
            localStorage.removeItem('authToken');
            localStorage.removeItem('user');
        }
    }

    async function login() {
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;

        if (!email || !password) {
            alert('Por favor completa todos los campos');
            return;
        }

        try {
            console.log("Attempting to log in with:", { email, password });
            const response = await fetch(`${API_URL}/api/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            });

            const data = await response.json();

            if (response.ok) {
                // Guardar token y datos del usuario
                localStorage.setItem('authToken', data.access_token);

                // Guardar información completa del usuario incluyendo rol
                const userInfo = data.user_info || {};
                const userName = userInfo.nombre || email.split('@')[0] || "Usuario";
                localStorage.setItem('user', JSON.stringify({
                    email: email,
                    nombre: userName,
                    rol: userInfo.rol || 'empleado',
                    activo: userInfo.activo || true,
                    permisos_especiales: userInfo.permisos_especiales || false
                }));

                // Cerrar modal y actualizar UI
                closeModal('loginModal');
                updateAuthUI(true);

                // Limpiar formulario
                loginForm.reset();

                // Mostrar mensaje de bienvenida
                displayWelcomeMessage(userName);
            } else {
                alert(data.detail || 'Error al iniciar sesión. Verifica tus credenciales.');
            }
        } catch (error) {
            console.error('Error al iniciar sesión:', error);
            alert('Error al conectar con el servidor. Por favor, inténtalo más tarde.');
        }
    }

    async function register() {
        const name = document.getElementById('registerName').value;
        const email = document.getElementById('registerEmail').value;
        const password = document.getElementById('registerPassword').value;

        if (!name || !email || !password) {
            alert('Por favor completa todos los campos');
            return;
        }

        try {
            const response = await fetch(`${API_URL}/api/auth/solicitar-registro`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    nombre: name,
                    email: email,
                    password: password
                })
            });

            const data = await response.json();

            if (response.ok) {
                // Cerrar modal y mostrar mensaje
                closeModal('registerModal');
                alert('Solicitud de registro enviada correctamente. Serás notificado por email cuando sea aprobada.');

                // Limpiar formulario
                registerForm.reset();
            } else {
                // Display detailed error messages from the server
                if (data && data.detail) {
                    alert(data.detail);
                } else {
                    alert('Error al enviar la solicitud. Inténtalo nuevamente.');
                }
            }
        } catch (error) {
            console.error('Error al enviar solicitud:', error);
            alert('Error al enviar la solicitud. Inténtalo nuevamente.');
        }
    }

    function logout() {
        // Eliminar token y datos del usuario
        localStorage.removeItem('authToken');
        localStorage.removeItem('user');

        // Actualizar UI
        updateAuthUI(false);

        // Mensaje de éxito
        alert('Has cerrado sesión correctamente');
    }

    function checkAuthentication() {
        const token = localStorage.getItem('authToken');
        updateAuthUI(!!token);
    }

    function updateAuthUI(isAuthenticated, isFirstLogin = false) {
        if (isAuthenticated) {
            // Usuario autenticado
            if (loginBtn) loginBtn.classList.add('hidden');
            if (registerBtn) registerBtn.classList.add('hidden');
            if (logoutBtn) logoutBtn.classList.remove('hidden');

            // Habilitar campo de entrada del chat
            const messageInput = document.getElementById('messageInput');
            const sendBtn = document.getElementById('sendBtn');
            if (messageInput) {
                messageInput.removeAttribute('disabled');
                messageInput.placeholder = 'Escribe tu pregunta aquí...';
            }
            if (sendBtn) {
                sendBtn.removeAttribute('disabled');
            }

            // Actualizar mensaje de bienvenida
            const welcomeMessage = document.querySelector('.bot-message');
            if (welcomeMessage && welcomeMessage.textContent.includes('inicia sesión')) {
                const userData = localStorage.getItem('user');
                if (userData) {
                    try {
                        const user = JSON.parse(userData);
                        welcomeMessage.textContent = `¡Hola ${user.nombre}! Soy el asistente virtual de la tienda de abastos. ¿En qué puedo ayudarte hoy?`;
                    } catch (e) {
                        console.error('Error al parsear datos de usuario:', e);
                    }
                }
            }

            // Mostrar nombre del usuario
            const userData = localStorage.getItem('user');
            if (userData) {
                try {
                    const user = JSON.parse(userData);

                    // Mostrar botón de administración si es admin
                    const adminBtn = document.getElementById('adminBtn');
                    if (adminBtn && user.rol && ['admin', 'administrador', 'dueño'].includes(user.rol)) {
                        adminBtn.style.display = 'inline-block';
                    }
                } catch (e) {
                    console.error('Error al parsear datos del usuario:', e);
                }
            }
        } else {
            // Usuario no autenticado: chat público habilitado
            if (loginBtn) loginBtn.classList.remove('hidden');
            if (registerBtn) registerBtn.classList.remove('hidden');
            if (logoutBtn) logoutBtn.classList.add('hidden');

            const messageInput = document.getElementById('messageInput');
            const sendBtn = document.getElementById('sendBtn');
            if (messageInput) {
                messageInput.removeAttribute('disabled');
                messageInput.placeholder = 'Escribe tu pregunta aquí... (modo público)';
            }
            if (sendBtn) {
                sendBtn.removeAttribute('disabled');
            }

            const welcomeMessage = document.querySelector('.bot-message');
            if (welcomeMessage && welcomeMessage.textContent.includes('inicia sesión')) {
                welcomeMessage.textContent = '¡Hola! Soy el asistente virtual de la tienda de abastos. Puedes hacer preguntas en modo público o iniciar sesión para funciones completas.';
            }

            const adminBtn = document.getElementById('adminBtn');
            if (adminBtn) adminBtn.style.display = 'none';
        }
    }

    function openModal(modalId) {
        if (typeof window.openModal === 'function') {
            window.openModal(modalId);
            return;
        }
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.add('show');
        setTimeout(() => {
            const firstInput = modal.querySelector('input');
            if (firstInput) firstInput.focus();
        }, 100);
    }

    function closeModal(modalId) {
        if (typeof window.closeModal === 'function') {
            window.closeModal(modalId);
            return;
        }
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.remove('show');
    }

    function displayWelcomeMessage(userName) {
        const welcomeMessage = `¡Bienvenido de vuelta, ${userName}! ¿En qué puedo ayudarte hoy?`;

        // Si existe un contenedor para mensaje de bienvenida, usarlo
        const messageContainer = document.getElementById("welcomeMessage");
        if (messageContainer) {
            messageContainer.textContent = welcomeMessage;
        }

        // Alternativamente, añadir un mensaje al chat si existe
        const chatMessages = document.getElementById('chatMessages');
        if (chatMessages) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message bot-message fade-in';
            messageDiv.textContent = welcomeMessage;

            const timeDiv = document.createElement('div');
            timeDiv.className = 'message-time';
            timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            messageDiv.appendChild(timeDiv);
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    // Función auxiliar para depuración
    function debugAuth() {
        console.log('=== Auth Debugging ===');
        console.log('Login Form Exists:', !!document.getElementById('loginForm'));
        console.log('Login Email Field Exists:', !!document.getElementById('loginEmail'));
        console.log('Login Password Field Exists:', !!document.getElementById('loginPassword'));
        console.log('Auth Token in Storage:', localStorage.getItem('authToken'));
        console.log('User Data in Storage:', localStorage.getItem('user'));
        console.log('API URL:', API_URL);

        // Verificar conexión al servidor
        fetch(`${API_URL}/health`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        })
            .then(response => {
                console.log('Server Health Check Status:', response.status);
                return response.ok ? 'OK' : 'Failed';
            })
            .then(status => console.log('Server Health Check:', status))
            .catch(error => console.log('Server Health Check Failed:', error));
    }

    // Clean up test code

    // Agregar botón para depuración (solo en desarrollo)
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        const debugButton = document.createElement('button');
        debugButton.textContent = 'Debug Auth';
        debugButton.style.position = 'fixed';
        debugButton.style.bottom = '10px';
        debugButton.style.right = '10px';
        debugButton.style.zIndex = '9999';
        debugButton.style.opacity = '0.7';
        debugButton.addEventListener('click', debugAuth);
        document.body.appendChild(debugButton);

        // Ejecutar diagnóstico inicial
        setTimeout(debugAuth, 1000);
    }
});
