// Script de depuración para verificar el estado de autenticación
console.log('🔍 Debug: Verificando estado de autenticación...');

// Verificar localStorage
const authToken = localStorage.getItem('authToken');
const userData = localStorage.getItem('user');

console.log('🔑 Token presente:', !!authToken);
console.log('👤 Datos de usuario presentes:', !!userData);

if (authToken) {
    console.log('📏 Longitud del token:', authToken.length);
    console.log('🔍 Partes del token:', authToken.split('.').length);
    console.log('📄 Token (primeros 50 chars):', authToken.substring(0, 50) + '...');
}

if (userData) {
    try {
        const user = JSON.parse(userData);
        console.log('👤 Usuario:', user);
        console.log('🎭 Rol:', user.rol);
    } catch (e) {
        console.error('❌ Error al parsear datos de usuario:', e);
    }
}

// Verificar estado del input del chatbot
function checkChatbotInput() {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    
    if (messageInput) {
        console.log('📝 Input del chatbot:');
        console.log('  - Elemento presente:', !!messageInput);
        console.log('  - Deshabilitado:', messageInput.disabled);
        console.log('  - Placeholder:', messageInput.placeholder);
        console.log('  - Valor actual:', messageInput.value);
    }
    
    if (sendBtn) {
        console.log('📤 Botón enviar:');
        console.log('  - Elemento presente:', !!sendBtn);
        console.log('  - Deshabilitado:', sendBtn.disabled);
    }
}

// Verificar si estamos en la página principal
if (window.location.pathname === '/' || window.location.pathname === '/index.html') {
    console.log('🏠 En página principal del chatbot');
    checkChatbotInput();
}

// Función para limpiar datos de autenticación
window.clearAuth = function() {
    console.log('🧹 Limpiando datos de autenticación...');
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    console.log('✅ Datos limpiados');
    location.reload(); // Recargar para aplicar cambios
};

// Función para verificar token con el servidor
window.verifyToken = async function() {
    if (!authToken) {
        console.log('❌ No hay token para verificar');
        return;
    }
    
    try {
        const response = await fetch('/api/chatbot/preguntar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                pregunta: 'test',
                estilo: 'corto'
            })
        });
        
        console.log('🔍 Respuesta del servidor:', response.status, response.statusText);
        
        if (response.ok) {
            const data = await response.json();
            console.log('✅ Token válido, respuesta recibida:', data);
        } else {
            console.log('❌ Token inválido o expirado');
        }
    } catch (error) {
        console.error('❌ Error al verificar token:', error);
    }
};

// Función para intentar login automático
window.tryAutoLogin = async function() {
    console.log('🔑 Intentando login automático...');
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: 'boris13jb@gmail.com',
                password: 'tu_contraseña_aqui' // Reemplaza con la contraseña real
            })
        });
        
        console.log('🔍 Respuesta del login:', response.status, response.statusText);
        
        if (response.ok) {
            const data = await response.json();
            console.log('✅ Login exitoso:', data);
            
            // Guardar token y datos de usuario
            localStorage.setItem('authToken', data.access_token);
            localStorage.setItem('user', JSON.stringify(data.user));
            
            console.log('💾 Datos guardados en localStorage');
            location.reload(); // Recargar para aplicar cambios
        } else {
            const error = await response.json();
            console.log('❌ Error en login:', error);
        }
    } catch (error) {
        console.error('❌ Error al intentar login:', error);
    }
};

console.log('🔧 Funciones de debug disponibles:');
console.log('  - clearAuth(): Limpiar datos de autenticación');
console.log('  - verifyToken(): Verificar token con el servidor');
console.log('  - checkChatbotInput(): Verificar estado del input del chatbot');
console.log('  - tryAutoLogin(): Intentar login automático (cambia la contraseña)');

// Ejecutar verificación automática
checkChatbotInput(); 