/**
 * Monitor de Estado del Sistema de Chatbot
 */
const REFRESH_INTERVAL_MS = 30000;

async function fetchJson(url) {
    const response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) {
        throw new Error(`${url} -> HTTP ${response.status}`);
    }
    return response.json();
}

function setBadge(elementId, ok, okText, errorText) {
    const element = document.getElementById(elementId);
    if (!element) return;
    element.textContent = ok ? okText : errorText;
    element.className = ok ? 'badge badge-ok' : 'badge badge-error';
}

function formatHealth(data) {
    const raw = JSON.stringify(data).toLowerCase();
    return raw.includes('"ok"') || raw.includes('healthy') || raw.includes('success');
}

async function updateMetrics() {
    const lastUpdate = document.getElementById('last-update');
    if (lastUpdate) {
        lastUpdate.textContent = new Date().toLocaleString();
    }

    try {
        const [health, db, llm, embedding, syncHealth, syncStatus, systemMetrics] = await Promise.all([
            fetchJson('/health'),
            fetchJson('/health/db'),
            fetchJson('/health/llm'),
            fetchJson('/health/embedding'),
            fetchJson('/health/sync'),
            fetchJson('/sync/status'),
            fetchJson('/api/metrics/system'),
        ]);

        setBadge('health-status', formatHealth(health), 'Operativo', 'Error');
        setBadge('db-status', formatHealth(db), 'Conectada', 'Error');
        setBadge('llm-status', formatHealth(llm), 'Disponible', 'Error');
        setBadge('embedding-status', formatHealth(embedding), 'Activo', 'Error');
        setBadge('sync-health-status', formatHealth(syncHealth), 'OK', 'Error');

        const summary = document.getElementById('status-summary');
        if (summary) {
            summary.textContent = 'Servicios consultados correctamente.';
            summary.className = '';
        }

        const syncData = syncStatus.data || {};
        const productCount = document.getElementById('product-count');
        const syncStatusEl = document.getElementById('sync-status');
        const indexedCount = document.getElementById('indexed-count');

        if (productCount) {
            productCount.textContent = syncData.productos_db ?? systemMetrics.products?.total ?? '—';
        }
        if (indexedCount) {
            indexedCount.textContent = syncData.productos_indexados ?? systemMetrics.products?.indexed ?? '—';
        }
        if (syncStatusEl) {
            const synced = syncData.sincronizados ?? systemMetrics.products?.sync_status;
            syncStatusEl.textContent = synced === true || synced === 'Sincronizado' ? 'Sincronizado' : String(synced ?? 'Desconocido');
            syncStatusEl.className = (synced === true || synced === 'Sincronizado')
                ? 'badge badge-ok'
                : 'badge badge-warning';
        }

        const cpuEl = document.getElementById('cpu-usage');
        const memoryEl = document.getElementById('memory-usage');
        const cacheEl = document.getElementById('llm-cache');
        if (cpuEl) cpuEl.textContent = systemMetrics.system?.cpu_percent ?? 'N/A';
        if (memoryEl) memoryEl.textContent = systemMetrics.system?.memory_percent ?? 'N/A';
        if (cacheEl) cacheEl.textContent = systemMetrics.llm?.cache_size ?? 'N/A';

        const details = document.getElementById('status-details');
        if (details) {
            details.textContent = JSON.stringify({
                health,
                db,
                llm,
                embedding,
                syncHealth,
                syncStatus,
                systemMetrics,
            }, null, 2);
        }
    } catch (error) {
        console.error('Error actualizando métricas:', error);
        const summary = document.getElementById('status-summary');
        if (summary) {
            summary.textContent = `Error al consultar servicios: ${error.message}`;
            summary.className = 'status-error';
        }
    }
}

async function forceSync() {
    const button = document.getElementById('force-sync-btn');
    if (button) {
        button.disabled = true;
        button.textContent = 'Sincronizando...';
    }
    try {
        const response = await fetch('/sync/force', { method: 'POST' });
        const data = await response.json();
        alert(data.message || data.detail || 'Sincronización completada');
        await updateMetrics();
    } catch (error) {
        alert('Error al sincronizar: ' + error.message);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = 'Forzar sincronización';
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    updateMetrics();
    setInterval(updateMetrics, REFRESH_INTERVAL_MS);
    const syncButton = document.getElementById('force-sync-btn');
    if (syncButton) {
        syncButton.addEventListener('click', forceSync);
    }
    const refreshButton = document.getElementById('refresh-btn');
    if (refreshButton) {
        refreshButton.addEventListener('click', updateMetrics);
    }
});

window.updateMetrics = updateMetrics;
