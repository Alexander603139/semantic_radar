const SERVICES = {
    ingestor:  { url: '/ingestor', health: '/health' },
    embedder:  { url: '/embedder', health: '/health' },
    analyzer:  { url: '/analyzer', health: '/health' },
    reporter:  { url: '/reporter', health: '/health' },
    storage:   { url: '/storage', health: '/health' },
    traffic_stats: { url: '/traffic_stats', health: '/health' }
};

const BASE_URL = '';  // относительные пути

const statusContainer = document.getElementById('statusContainer');
const lastCheckEl = document.getElementById('lastCheck');
const logArea = document.getElementById('logArea');
const articlesContainer = document.getElementById('articlesContainer');
const reportsContainer = document.getElementById('reportsContainer');
const runParserBtn = document.getElementById('runParserBtn');
const runAnalysisBtn = document.getElementById('runAnalysisBtn');
const generateReportBtn = document.getElementById('generateReportBtn');
const refreshStatusBtn = document.getElementById('refreshStatusBtn');
const limitInput = document.getElementById('limitInput');
const weeksInput = document.getElementById('weeksInput');
const timeBadge = document.getElementById('timeBadge');

function log(msg, type = 'info') {
    const color = type === 'error' ? 'error' : type === 'success' ? 'success' : 'info';
    logArea.innerHTML += `<div class="${color}">${new Date().toLocaleTimeString()} — ${msg}</div>`;
    logArea.scrollTop = logArea.scrollHeight;
}

function updateTime() {
    timeBadge.textContent = new Date().toLocaleString();
}
setInterval(updateTime, 10000);
updateTime();

async function checkStatuses() {
    const items = statusContainer.querySelectorAll('.status-item');
    let allOk = true;
    let i = 0;
    for (const [name, cfg] of Object.entries(SERVICES)) {
        const dot = items[i].querySelector('.dot');
        try {
            const resp = await fetch(`${BASE_URL}${cfg.url}${cfg.health}`, {
                signal: AbortSignal.timeout(3000)
            });
            if (resp.ok) {
                dot.className = 'dot green';
            } else {
                dot.className = 'dot red';
                allOk = false;
            }
        } catch (e) {
            dot.className = 'dot red';
            allOk = false;
        }
        i++;
    }
    lastCheckEl.textContent = new Date().toLocaleTimeString();
    return allOk;
}

refreshStatusBtn.addEventListener('click', () => {
    log('Обновление статусов...', 'info');
    checkStatuses().then(ok => {
        log(ok ? 'Все сервисы доступны ✅' : 'Некоторые сервисы недоступны ❌', ok ? 'success' : 'error');
    });
});

async function runParser() {
    const limit = parseInt(limitInput.value) || 3;
    runParserBtn.disabled = true;
    log(`Запуск парсинга (limit=${limit})...`, 'info');

    try {
        const resp = await fetch(`${BASE_URL}/ingestor/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: 'admin',
                sources: [],
                limit: limit
            })
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        log(`✅ Парсинг запущен: task_id=${data.task_id}`, 'success');
        setTimeout(() => checkTaskStatus(data.task_id), 3000);
    } catch (e) {
        log(`❌ Ошибка: ${e.message}`, 'error');
    } finally {
        runParserBtn.disabled = false;
    }
}

async function checkTaskStatus(taskId) {
    try {
        const resp = await fetch(`${BASE_URL}/ingestor/status/${taskId}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (data.status === 'completed') {
            log(`✅ Задача ${taskId} завершена: ${data.result?.total_articles || 0} статей`, 'success');
            loadArticles();
        } else if (data.status === 'failed') {
            log(`❌ Задача ${taskId} упала: ${data.error}`, 'error');
        } else {
            log(`⏳ Задача ${taskId} выполняется (${data.status})...`, 'info');
            setTimeout(() => checkTaskStatus(taskId), 5000);
        }
    } catch (e) {
        log(`❌ Ошибка при проверке статуса: ${e.message}`, 'error');
    }
}

async function runAnalysis() {
    const weeks = parseInt(weeksInput.value) || 2;
    runAnalysisBtn.disabled = true;
    log(`Запуск анализа (weeks=${weeks})...`, 'info');

    try {
        const resp = await fetch(`${BASE_URL}/analyzer/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: 'admin', weeks: weeks })
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        log(`✅ Анализ завершён: drift_score=${data.drift_score?.toFixed(4) || '—'}`, 'success');
        log(`📊 Сместившихся тем: ${data.shifted_topics?.length || 0}`, 'info');
        await generateReport(data);
    } catch (e) {
        log(`❌ Ошибка анализа: ${e.message}`, 'error');
    } finally {
        runAnalysisBtn.disabled = false;
    }
}

async function generateReport(analysisData) {
    generateReportBtn.disabled = true;
    log('Генерация отчёта...', 'info');

    try {
        const resp = await fetch(`${BASE_URL}/reporter/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: 'admin',
                analysis_result: analysisData
            })
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        log(`✅ Отчёт сгенерирован: ${data.report_url}`, 'success');
        loadReports();
        log(`🔗 ${window.location.origin}${data.report_url}`, 'info');
    } catch (e) {
        log(`❌ Ошибка генерации отчёта: ${e.message}`, 'error');
    } finally {
        generateReportBtn.disabled = false;
    }
}

async function loadArticles() {
    try {
        const resp = await fetch(`${BASE_URL}/storage/list?user_id=admin&file_type=articles&limit=10`);
        if (!resp.ok) {
            articlesContainer.innerHTML = `<p class="text-muted">⚠️ Storage не отвечает, попробуйте позже.</p>`;
            return;
        }
        const files = await resp.json();
        if (!files || files.length === 0) {
            articlesContainer.innerHTML = `<p class="text-muted">Нет статей.</p>`;
            return;
        }
        let html = `<div class="table-wrap"><table>
            <thead><tr><th>Заголовок</th><th>Источник</th><th>Дата</th></tr></thead><tbody>`;
        for (const file of files) {
            const meta = file.metadata || {};
            html += `<tr>
                <td>${meta.title || file.file_key || '—'}</td>
                <td><span class="tag">${meta.source || '—'}</span></td>
                <td>${file.created_at ? new Date(file.created_at).toLocaleDateString() : '—'}</td>
            </tr>`;
        }
        html += `</tbody></table></div>`;
        articlesContainer.innerHTML = html;
    } catch (e) {
        articlesContainer.innerHTML = `<p class="text-muted">⚠️ Не удалось загрузить статьи: ${e.message}</p>`;
    }
}

async function loadReports() {
    try {
        const resp = await fetch(`${BASE_URL}/storage/list?user_id=admin&file_type=reports&limit=5`);
        if (!resp.ok) {
            reportsContainer.innerHTML = `<p class="text-muted">Нет отчётов.</p>`;
            return;
        }
        const files = await resp.json();
        if (!files || files.length === 0) {
            reportsContainer.innerHTML = `<p class="text-muted">Нет сгенерированных отчётов.</p>`;
            return;
        }
        let html = `<div class="table-wrap"><table>
            <thead><tr><th>Дата</th><th>Файл</th><th>Ссылка</th></tr></thead><tbody>`;
        for (const file of files) {
            const fileId = file.id;
            const created = file.created_at ? new Date(file.created_at).toLocaleString() : '—';
            const fileName = file.file_key || 'отчёт';
            html += `<tr>
                <td>${created}</td>
                <td>${fileName}</td>
                <td><a href="${window.location.origin}/reports/admin/${fileId}" target="_blank" class="link">🔗 Открыть</a></td>
            </tr>`;
        }
        html += `</tbody></table></div>`;
        reportsContainer.innerHTML = html;
    } catch (e) {
        reportsContainer.innerHTML = `<p class="text-muted">⚠️ Ошибка загрузки отчётов: ${e.message}</p>`;
    }
}

runParserBtn.addEventListener('click', runParser);
runAnalysisBtn.addEventListener('click', runAnalysis);
generateReportBtn.addEventListener('click', () => {
    log('Запуск генерации отчёта без данных анализа — попробуйте сначала запустить анализ.', 'info');
});

async function init() {
    log('🚀 Загрузка админ-панели...', 'info');
    await checkStatuses();
    await loadArticles();
    await loadReports();
    log('✅ Готово', 'success');
}

init();
setInterval(() => {
    checkStatuses();
    loadArticles();
    loadReports();
}, 60000);