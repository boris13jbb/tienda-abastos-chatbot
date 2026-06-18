/**
 * Utilidades UI compartidas entre páginas del frontend.
 */
(function () {
    function openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.add('show');
        setTimeout(() => {
            const firstInput = modal.querySelector('input:not([type="hidden"])');
            if (firstInput) firstInput.focus();
        }, 100);
    }

    function closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.remove('show');
    }

    window.openModal = openModal;
    window.closeModal = closeModal;

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.close-modal[data-close-modal]').forEach((button) => {
            button.addEventListener('click', function () {
                const modalId = button.getAttribute('data-close-modal');
                if (modalId) closeModal(modalId);
            });
        });

        document.querySelectorAll('.modal-overlay').forEach((overlay) => {
            overlay.addEventListener('click', function (event) {
                if (event.target === overlay) {
                    closeModal(overlay.id);
                }
            });
        });
    });
})();
