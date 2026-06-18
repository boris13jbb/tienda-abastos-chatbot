document.addEventListener('DOMContentLoaded', function () {
    // API URL - Asegúrate de que esta sea la URL correcta de tu backend
    const API_URL = window.location.origin; // Usa origen actual para desarrollo y producción

    // Elementos DOM
    const forgotPasswordForm = document.getElementById('forgotPasswordForm');
    const resetPasswordForm = document.getElementById('resetPasswordForm');
    const resetTokenInput = document.getElementById('resetToken');

    // Verificar si hay un token de restablecimiento en la URL
    checkForResetToken();

    // Event Listeners
    if (forgotPasswordForm) {
        forgotPasswordForm.addEventListener('submit', function (e) {
            e.preventDefault();
            requestPasswordReset();
        });
    }

    if (resetPasswordForm) {
        resetPasswordForm.addEventListener('submit', function (e) {
            e.preventDefault();
            resetPassword();
        });
    }

    // Funciones para la recuperación de contraseña
    async function requestPasswordReset() {
        const emailInput = document.getElementById('resetEmail');
        if (!emailInput) return;

        const email = emailInput.value.trim();

        if (!email) {
            alert('Por favor ingresa tu correo electrónico');
            return;
        }

        try {
            const response = await fetch(`${API_URL}/api/auth/reset-password-request`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email
                })
            });

            const data = await response.json();

            if (response.ok) {
                alert('Si el correo electrónico está registrado, recibirás un enlace para restablecer tu contraseña.');
                closeModal('forgotPasswordModal');
            } else {
                alert(data.detail || 'Error al solicitar el restablecimiento de contraseña.');
            }
        } catch (error) {
            console.error('Error al solicitar restablecimiento:', error);
            alert('Error al solicitar el restablecimiento de contraseña. Inténtalo nuevamente.');
        }
    }

    async function resetPassword() {
        const tokenInput = document.getElementById('resetToken');
        const passwordInput = document.getElementById('newPassword');
        const confirmPasswordInput = document.getElementById('confirmPassword');

        if (!tokenInput || !passwordInput) return;

        const token = tokenInput.value;
        const newPassword = passwordInput.value;
        const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : newPassword;

        if (!token || !newPassword) {
            alert('Por favor completa todos los campos');
            return;
        }

        if (newPassword !== confirmPassword) {
            alert('Las contraseñas no coinciden');
            return;
        }

        if (newPassword.length < 6) {
            alert('La contraseña debe tener al menos 6 caracteres');
            return;
        }

        try {
            const response = await fetch(`${API_URL}/api/auth/reset-password`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    token: token,
                    new_password: newPassword
                })
            });

            const data = await response.json();

            if (response.ok) {
                alert('Contraseña restablecida correctamente. Ya puedes iniciar sesión con tu nueva contraseña.');
                closeModal('resetPasswordModal');

                // Redirigir a la página principal
                window.location.href = '/';
            } else {
                alert(data.detail || 'Error al restablecer la contraseña. El token puede haber expirado.');
            }
        } catch (error) {
            console.error('Error al restablecer contraseña:', error);
            alert('Error al restablecer la contraseña. Inténtalo nuevamente.');
        }
    }

    function checkForResetToken() {
        // Verificar si hay un token de restablecimiento en la URL
        const urlParams = new URLSearchParams(window.location.search);
        const resetToken = urlParams.get('token');

        if (resetToken && resetTokenInput) {
            resetTokenInput.value = resetToken;

            // Si estamos en la página de restablecimiento, mostrar automáticamente el formulario
            const resetPasswordModal = document.getElementById('resetPasswordModal');
            if (resetPasswordModal) {
                openModal('resetPasswordModal');
            }
        }
    }

    function openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        modal.classList.add('show');

        // Enfocar el primer campo del formulario
        setTimeout(() => {
            const firstInput = modal.querySelector('input');
            if (firstInput) firstInput.focus();
        }, 100);
    }

    function closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        modal.classList.remove('show');
    }
});
