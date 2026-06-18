const API_BASE = '/api/admin';
const SYNC_BASE = '/api/sync';
const LEARNING_BASE = '/api/learning';

const API_ENDPOINTS = {
    USERS: '/usuarios',
    STATS: '/stats',
    SOLICITUDES: '/solicitudes',
    PRODUCTOS: '/productos',
};

let editingUserId = null;
let editingSolicitudId = null;

function validateToken() {
    const token = localStorage.getItem('authToken');
    if (!token || token.trim() === '') return null;
    if (token.split('.').length !== 3) return null;
    return token;
}

function handleAuthError() {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    window.location.href = '/';
}

async function authenticatedFetch(url, options = {}) {
    const token = validateToken();
    if (!token) {
        handleAuthError();
        return null;
    }

    const response = await fetch(url, {
        ...options,
        headers: {
            'Authorization': `Bearer ${token}`,
            ...options.headers,
        },
    });

    if (response.status === 401 || response.status === 403) {
        showMessage('Sesión inválida o sin permisos de administrador.', 'error');
        setTimeout(handleAuthError, 1500);
        return null;
    }

    return response;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatDate(value) {
    if (!value) return '-';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString();
}

function showMessage(message, type = 'success') {
    const messageDiv = document.getElementById('message');
    if (!messageDiv) return;
    messageDiv.textContent = message;
    messageDiv.className = type;
    setTimeout(() => {
        messageDiv.textContent = '';
        messageDiv.className = '';
    }, 5000);
}

document.addEventListener('DOMContentLoaded', function () {
    checkAuth();
    loadStats();
    loadUsers();
    loadSolicitudes();
});

function checkAuth() {
    const token = validateToken();
    if (!token) {
        handleAuthError();
        return;
    }

    const userData = localStorage.getItem('user');
    if (!userData) {
        handleAuthError();
        return;
    }

    try {
        const user = JSON.parse(userData);
        if (!user.rol || !['admin', 'administrador', 'dueño'].includes(user.rol)) {
            alert('Acceso denegado. Solo administradores pueden acceder a este panel.');
            window.location.href = '/';
        }
    } catch (error) {
        handleAuthError();
    }
}

async function loadStats() {
    try {
        const response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.STATS}`);
        if (!response || !response.ok) return;

        const stats = await response.json();
        document.getElementById('statsGrid').innerHTML = `
            <div class="stat-card"><div class="stat-number">${stats.total_usuarios}</div><div class="stat-label">Total usuarios</div></div>
            <div class="stat-card"><div class="stat-number">${stats.usuarios_activos}</div><div class="stat-label">Activos</div></div>
            <div class="stat-card"><div class="stat-number">${stats.usuarios_inactivos}</div><div class="stat-label">Inactivos</div></div>
            <div class="stat-card"><div class="stat-number">${stats.empleados}</div><div class="stat-label">Empleados</div></div>
            <div class="stat-card"><div class="stat-number">${stats.administradores}</div><div class="stat-label">Administradores</div></div>
        `;
    } catch (error) {
        console.error(error);
        showMessage('Error al cargar estadísticas', 'error');
    }
}

async function loadUsers() {
    try {
        const response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.USERS}`);
        if (!response || !response.ok) return;

        const users = await response.json();
        const tbody = document.getElementById('usersTableBody');
        tbody.innerHTML = users.length
            ? users.map(createUserRow).join('')
            : '<tr><td colspan="7" class="empty-state">No hay usuarios registrados</td></tr>';
    } catch (error) {
        console.error(error);
        showMessage('Error al cargar usuarios', 'error');
    }
}

async function loadSolicitudes() {
    try {
        const response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.SOLICITUDES}`);
        if (!response || !response.ok) return;

        const solicitudes = await response.json();
        const tbody = document.getElementById('solicitudesTableBody');
        tbody.innerHTML = solicitudes.length
            ? solicitudes.map(createSolicitudRow).join('')
            : '<tr><td colspan="8" class="empty-state">No hay solicitudes pendientes</td></tr>';
    } catch (error) {
        console.error(error);
        showMessage('Error al cargar solicitudes', 'error');
    }
}

async function loadProductos() {
    try {
        const response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.PRODUCTOS}`);
        if (!response || !response.ok) return;

        const productos = await response.json();
        const tbody = document.getElementById('productosTableBody');
        const count = document.getElementById('productosCount');
        if (count) count.textContent = `${productos.length} producto(s) en catálogo`;

        tbody.innerHTML = productos.length
            ? productos.map((producto) => `
                <tr>
                    <td>${producto.id}</td>
                    <td>${escapeHtml(producto.nombre)}</td>
                    <td>${escapeHtml(producto.descripcion || '-')}</td>
                    <td>$${Number(producto.precio).toFixed(2)}</td>
                    <td>${producto.stock}</td>
                </tr>
            `).join('')
            : '<tr><td colspan="5" class="empty-state">No hay productos en la base de datos</td></tr>';
    } catch (error) {
        console.error(error);
        showMessage('Error al cargar productos', 'error');
    }
}

async function loadSyncPanel() {
    try {
        const [syncResponse, indexResponse] = await Promise.all([
            authenticatedFetch(`${SYNC_BASE}/status`),
            fetch('/sync/status'),
        ]);

        if (syncResponse && syncResponse.ok) {
            const sync = await syncResponse.json();
            document.getElementById('syncInfo').innerHTML = `
                <div class="info-item"><strong>En ejecución</strong>${sync.running ? 'Sí' : 'No'}</div>
                <div class="info-item"><strong>Auto-sync</strong>${sync.auto_sync_enabled ? 'Activo' : 'Detenido'}</div>
                <div class="info-item"><strong>Última sync</strong>${sync.last_sync || 'Nunca'}</div>
                <div class="info-item"><strong>Total syncs</strong>${sync.total_syncs ?? 0}</div>
                <div class="info-item"><strong>Último error</strong>${escapeHtml(sync.last_error || 'Ninguno')}</div>
            `;
        }

        if (indexResponse.ok) {
            const indexData = await indexResponse.json();
            const details = indexData.data || {};
            document.getElementById('syncIndexInfo').innerHTML = `
                <div class="info-item"><strong>Productos en BD</strong>${details.productos_db ?? '—'}</div>
                <div class="info-item"><strong>Productos indexados</strong>${details.productos_indexados ?? '—'}</div>
                <div class="info-item"><strong>Sincronizados</strong>${details.sincronizados ? 'Sí' : 'No'}</div>
                <div class="info-item"><strong>Faltantes</strong>${details.detalles?.productos_faltantes ?? 0}</div>
                <div class="info-item"><strong>Extra</strong>${details.detalles?.productos_extra ?? 0}</div>
                <div class="info-item"><strong>Actualizados</strong>${details.detalles?.productos_actualizados ?? 0}</div>
            `;
        }
    } catch (error) {
        console.error(error);
        showMessage('Error al cargar sincronización', 'error');
    }
}

async function loadSyncLogs() {
    try {
        const response = await authenticatedFetch(`${SYNC_BASE}/logs?lines=80`);
        if (!response || !response.ok) return;
        const data = await response.json();
        const logsBox = document.getElementById('syncLogs');
        logsBox.style.display = 'block';
        logsBox.textContent = data.logs?.join('\n') || data.message || JSON.stringify(data, null, 2);
    } catch (error) {
        console.error(error);
        showMessage('No se pudieron cargar los logs', 'error');
    }
}

async function runSyncNow() {
    try {
        const response = await authenticatedFetch(`${SYNC_BASE}/sync-now`, { method: 'POST' });
        if (!response) return;
        const data = await response.json();
        showMessage(data.message || 'Sincronización ejecutada', data.status === 'success' ? 'success' : 'error');
        loadSyncPanel();
        loadProductos();
    } catch (error) {
        showMessage('Error al sincronizar', 'error');
    }
}

async function startAutoSync() {
    const response = await authenticatedFetch(`${SYNC_BASE}/start`, { method: 'POST' });
    if (!response) return;
    const data = await response.json();
    showMessage(data.message, data.status === 'error' ? 'error' : 'success');
    loadSyncPanel();
}

async function stopAutoSync() {
    const response = await authenticatedFetch(`${SYNC_BASE}/stop`, { method: 'POST' });
    if (!response) return;
    const data = await response.json();
    showMessage(data.message, data.status === 'error' ? 'error' : 'success');
    loadSyncPanel();
}

async function loadLearning() {
    try {
        const response = await authenticatedFetch(`${LEARNING_BASE}/insights`);
        if (!response || !response.ok) return;
        const payload = await response.json();
        const stats = payload.data || {};
        document.getElementById('learningInfo').innerHTML = `
            <div class="info-item"><strong>Interacciones</strong>${stats.total_interactions ?? 0}</div>
            <div class="info-item"><strong>Tasa de éxito</strong>${stats.success_rate ?? 0}</div>
            <div class="info-item"><strong>Confianza media</strong>${stats.avg_confidence ?? 0}</div>
            <div class="info-item"><strong>Tiempo respuesta</strong>${stats.avg_response_time ?? 0}</div>
            <div class="info-item"><strong>Patrones aprendidos</strong>${stats.learned_patterns ?? 0}</div>
            <div class="info-item"><strong>Entradas FAQ</strong>${stats.faq_entries ?? 0}</div>
        `;
        document.getElementById('learningDetails').textContent = JSON.stringify(payload, null, 2);
    } catch (error) {
        console.error(error);
        showMessage('Error al cargar aprendizaje', 'error');
    }
}

function createUserRow(user) {
    const statusClass = user.activo ? 'active' : 'inactive';
    const statusText = user.activo ? 'Activo' : 'Inactivo';
    const canDelete = user.rol !== 'dueño';

    return `
        <tr>
            <td>${user.id}</td>
            <td>${escapeHtml(user.nombre)}</td>
            <td>${escapeHtml(user.email)}</td>
            <td><span class="role-badge">${escapeHtml(user.rol)}</span></td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>${formatDate(user.fecha_registro)}</td>
            <td>
                <div class="user-actions">
                    <button class="btn btn-small btn-outline" type="button" onclick="editUser(${user.id})" title="Editar">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-small btn-outline" type="button" onclick="toggleUserStatus(${user.id}, ${user.activo})" title="Activar/Desactivar">
                        <i class="fas fa-${user.activo ? 'ban' : 'check'}"></i>
                    </button>
                    ${canDelete ? `<button class="btn btn-small btn-outline" type="button" onclick="deleteUser(${user.id})" title="Eliminar"><i class="fas fa-trash"></i></button>` : ''}
                </div>
            </td>
        </tr>
    `;
}

function createSolicitudRow(solicitud) {
    const botonesHtml = solicitud.estado === 'pendiente'
        ? `
            <button class="btn-approve" type="button" onclick="procesarSolicitud(${solicitud.id}, 'aprobada')">Aprobar</button>
            <button class="btn-reject" type="button" onclick="procesarSolicitud(${solicitud.id}, 'rechazada')">Rechazar</button>
            <button class="btn-delete" type="button" onclick="eliminarSolicitud(${solicitud.id})">Eliminar</button>
        `
        : '<span class="text-muted">Procesada</span>';

    return `
        <tr>
            <td>${solicitud.id}</td>
            <td>${escapeHtml(solicitud.nombre)}</td>
            <td>${escapeHtml(solicitud.email)}</td>
            <td><span class="status-badge ${solicitud.estado}">${escapeHtml(solicitud.estado)}</span></td>
            <td>${formatDate(solicitud.fecha_solicitud)}</td>
            <td>${escapeHtml(solicitud.rol_asignado || '-')}</td>
            <td>${escapeHtml(solicitud.comentarios || '-')}</td>
            <td><div class="solicitud-actions">${botonesHtml}</div></td>
        </tr>
    `;
}

function showTab(tabName, buttonEl) {
    document.querySelectorAll('.tab-content').forEach((tab) => tab.classList.remove('active'));
    document.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
    document.getElementById(tabName).classList.add('active');
    if (buttonEl) buttonEl.classList.add('active');

    if (tabName === 'usuarios') {
        loadStats();
        loadUsers();
    } else if (tabName === 'solicitudes') {
        loadSolicitudes();
    } else if (tabName === 'productos') {
        loadProductos();
    } else if (tabName === 'sincronizacion') {
        loadSyncPanel();
    } else if (tabName === 'aprendizaje') {
        loadLearning();
    }
}

async function eliminarSolicitud(solicitudId) {
    if (!confirm('¿Eliminar esta solicitud?')) return;

    try {
        const response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.SOLICITUDES}/${solicitudId}`, {
            method: 'DELETE',
        });
        if (!response || !response.ok) throw new Error('No se pudo eliminar la solicitud');
        const result = await response.json();
        showMessage(result.message || 'Solicitud eliminada', 'success');
        loadSolicitudes();
    } catch (error) {
        showMessage(error.message, 'error');
    }
}

function procesarSolicitud(solicitudId, estado) {
    editingSolicitudId = solicitudId;
    document.getElementById('solicitudEstado').value = estado;
    document.getElementById('solicitudModalTitle').textContent = estado === 'aprobada' ? 'Aprobar solicitud' : 'Rechazar solicitud';
    document.getElementById('solicitudResumen').textContent = `Solicitud #${solicitudId} será marcada como ${estado}.`;
    toggleRolField();
    document.getElementById('solicitudModal').classList.add('show');
}

function toggleRolField() {
    const estado = document.getElementById('solicitudEstado').value;
    const rolGroup = document.getElementById('rolGroup');
    const rolInput = document.getElementById('solicitudRol');
    if (estado === 'aprobada') {
        rolGroup.style.display = 'block';
        rolInput.required = true;
    } else {
        rolGroup.style.display = 'none';
        rolInput.required = false;
    }
}

function closeSolicitudModal() {
    document.getElementById('solicitudModal').classList.remove('show');
    document.getElementById('solicitudForm').reset();
    editingSolicitudId = null;
}

document.getElementById('solicitudForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const formData = {
        estado: document.getElementById('solicitudEstado').value,
        rol_asignado: document.getElementById('solicitudRol').value,
        comentarios: document.getElementById('solicitudComentarios').value,
    };

    try {
        const response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.SOLICITUDES}/${editingSolicitudId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData),
        });
        if (!response || !response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al procesar solicitud');
        }
        showMessage(formData.estado === 'aprobada' ? 'Solicitud aprobada' : 'Solicitud rechazada', 'success');
        closeSolicitudModal();
        loadSolicitudes();
        loadStats();
        loadUsers();
    } catch (error) {
        showMessage(error.message, 'error');
    }
});

function openCreateUserModal() {
    editingUserId = null;
    document.getElementById('modalTitle').textContent = 'Crear Usuario';
    document.getElementById('userForm').reset();
    document.getElementById('userPassword').required = true;
    document.getElementById('userPassword').placeholder = '';
    document.getElementById('userModal').classList.add('show');
}

async function editUser(userId) {
    try {
        const response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.USERS}/${userId}`);
        if (!response || !response.ok) return;
        const user = await response.json();
        editingUserId = userId;
        document.getElementById('modalTitle').textContent = 'Editar Usuario';
        document.getElementById('userName').value = user.nombre;
        document.getElementById('userEmail').value = user.email;
        document.getElementById('userRole').value = user.rol;
        document.getElementById('userActive').checked = user.activo;
        document.getElementById('userSpecial').checked = user.permisos_especiales;
        document.getElementById('userPassword').required = false;
        document.getElementById('userPassword').value = '';
        document.getElementById('userPassword').placeholder = 'Dejar vacío para no cambiar';
        document.getElementById('userModal').classList.add('show');
    } catch (error) {
        showMessage('Error al cargar usuario', 'error');
    }
}

function closeUserModal() {
    document.getElementById('userModal').classList.remove('show');
    editingUserId = null;
}

document.getElementById('userForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const formData = {
        nombre: document.getElementById('userName').value,
        email: document.getElementById('userEmail').value,
        password: document.getElementById('userPassword').value,
        rol: document.getElementById('userRole').value,
        activo: document.getElementById('userActive').checked,
        permisos_especiales: document.getElementById('userSpecial').checked,
    };

    try {
        let response;
        if (editingUserId) {
            const updateData = { ...formData };
            if (!updateData.password) delete updateData.password;
            response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.USERS}/${editingUserId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updateData),
            });
        } else {
            response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.USERS}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData),
            });
        }

        if (!response || !response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al guardar usuario');
        }

        showMessage(editingUserId ? 'Usuario actualizado' : 'Usuario creado', 'success');
        closeUserModal();
        loadUsers();
        loadStats();
    } catch (error) {
        showMessage(error.message, 'error');
    }
});

async function toggleUserStatus(userId, currentStatus) {
    try {
        const response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.USERS}/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ activo: !currentStatus }),
        });
        if (!response || !response.ok) throw new Error('No se pudo cambiar el estado');
        showMessage(currentStatus ? 'Usuario desactivado' : 'Usuario activado', 'success');
        loadUsers();
        loadStats();
    } catch (error) {
        showMessage(error.message, 'error');
    }
}

async function deleteUser(userId) {
    if (!confirm('¿Eliminar este usuario?')) return;
    try {
        const response = await authenticatedFetch(`${API_BASE}${API_ENDPOINTS.USERS}/${userId}`, {
            method: 'DELETE',
        });
        if (!response || !response.ok) throw new Error('No se pudo eliminar el usuario');
        showMessage('Usuario eliminado', 'success');
        loadUsers();
        loadStats();
    } catch (error) {
        showMessage(error.message, 'error');
    }
}

document.getElementById('userModal').addEventListener('click', function (e) {
    if (e.target === this) closeUserModal();
});

document.getElementById('solicitudModal').addEventListener('click', function (e) {
    if (e.target === this) closeSolicitudModal();
});
