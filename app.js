const SERVICES = {
    ingestor:  { url: '/ingestor', health: '/health' },
    embedder:  { url: '/embedder', health: '/health' },
    analyzer:  { url: '/analyzer', health: '/health' },
    reporter:  { url: '/reporter', health: '/health' },
    storage:   { url: '/storage', health: '/health' },
    traffic_stats: { url: '/traffic_stats', health: '/health' }
};

const BASE_URL = 'https://lithef.twc1.net';

// ---------- DOM-элементы ----------
const statusContainer = document.getElementById('statusContainer');
const lastCheckEl = document.getElementById('lastCheck');
const logArea = document.getElementById('logArea');
const articlesContainer = document.getElementById('articlesContainer');
const vectorsContainer = document.getElementById('vectorsContainer');
const reportsContainer = document.getElementById('reportsContainer');
const runParserBtn = document.getElementById('runParserBtn');
const runAnalysisBtn = document.getElementById('runAnalysisBtn');
const generateReportBtn = document.getElementById('generateReportBtn');
const refreshStatusBtn = document.getElementById('refreshStatusBtn');
const limitInput = document.getElementById('limitInput');
const weeksInput = document.getElementById('weeksInput');
const timeBadge = document.getElementById('timeBadge');

// Новые элементы
const sourcesTextarea = document.getElementById('sourcesTextarea');
const loadSourcesBtn = document.getElementById('loadSourcesBtn');
const saveSourcesBtn = document.getElementById('saveSourcesBtn');
const measureSourcesBtn = document.getElementById('measureSourcesBtn');
const clearSourcesBtn = document.getElementById('clearSourcesBtn');
const sourcesStatus = document.getElementById('sourcesStatus');
const trafficStatsResults = document.getElementById('trafficStatsResults');
const cronInput = document.getElementById('cronInput');
const loadCronBtn = document.getElementById('loadCronBtn');
const saveCronBtn = document.getElementById('saveCronBtn');
const cronStatus = document.getElementById('cronStatus');

// ---------- УТИЛИТЫ ----------
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

// ---------- СТАТУСЫ СЕРВИСОВ ----------
async function checkStatuses() {
    const items = statusContainer.querySelectorAll('.status-item');
    let allOk = true;
    let i = 0;
    for (const [name, cfg] of Object.entries(SERVICES)) {
        const dot = items[i].querySelector('.dot');
        try {
            const resp = await fetch(`${BASE_URL}${cfg.url}${cfg.health}`, { signal: AbortSignal.timeout(3000) });
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

// ---------- ЗАПУСК ПАРСИНГА ----------
async function runParser() {
    const limit = parseInt(limitInput.value) || 3;
    runParserBtn.disabled = true;
    log(`Запуск парсинга (limit=${limit})...`, 'info');

    try {
        const resp = await fetch(`${BASE_URL}/ingestor/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: 'admin', limit: limit })
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
            loadVectors();
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

// ---------- ЗАПУСК АНАЛИЗА ----------
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

// ---------- ГЕНЕРАЦИЯ ОТЧЁТА ----------
async function generateReport(analysisData) {
    generateReportBtn.disabled = true;
    log('Генерация отчёта...', 'info');

    try {
        const resp = await fetch(`${BASE_URL}/reporter/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: 'admin', analysis_result: analysisData })
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

// ---------- ЗАГРУЗКА СТАТЕЙ ----------
async function loadArticles() {
    try {
        const resp = await fetch(`${BASE_URL}/storage/list?user_id=admin&file_type=articles&limit=10`);
        if (!resp.ok) {
            articlesContainer.innerHTML = `<p class="text-muted">⚠️ Storage не отвечает.</p>`;
            return;
        }
        const files = await resp.json();
        if (!files || files.length === 0) {
            articlesContainer.innerHTML = `<p class="text-muted">Нет статей.</p>`;
            return;
        }
        let html = `<div class="table-wrap"><table>
            <thead><tr><th>Заголовок</th><th>Источник</th><th>Дата</th><th>Действие</th></tr></thead><tbody>`;
        for (const file of files) {
            const meta = file.extra_metadata || {};
            html += `<tr>
                <td>${meta.title || file.file_key || '—'}</td>
                <td><span class="tag">${meta.source || '—'}</span></td>
                <td>${file.created_at ? new Date(file.created_at).toLocaleDateString() : '—'}</td>
                <td><a href="${BASE_URL}/storage/download/${file.id}" target="_blank" class="link">🔗 Открыть</a></td>
            </tr>`;
        }
        html += `</tbody></table></div>`;
        articlesContainer.innerHTML = html;
    } catch (e) {
        articlesContainer.innerHTML = `<p class="text-muted">⚠️ Ошибка: ${e.message}</p>`;
    }
}

// ---------- ЗАГРУЗКА ВЕКТОРОВ ----------
async function loadVectors() {
    try {
        const resp = await fetch(`${BASE_URL}/storage/list?user_id=admin&file_type=vectors&limit=10`);
        if (!resp.ok) {
            vectorsContainer.innerHTML = `<p class="text-muted">⚠️ Storage не отвечает.</p>`;
            return;
        }
        const files = await resp.json();
        if (!files || files.length === 0) {
            vectorsContainer.innerHTML = `<p class="text-muted">Нет векторов.</p>`;
            return;
        }
        let html = `<div class="table-wrap"><table>
            <thead><tr><th>Дата</th><th>Чанков</th><th>Источников</th><th>Действие</th></tr></thead><tbody>`;
        for (const file of files) {
            const meta = file.extra_metadata || {};
            html += `<tr>
                <td>${file.created_at ? new Date(file.created_at).toLocaleDateString() : '—'}</td>
                <td>${meta.chunk_count || '—'}</td>
                <td>${meta.source_count || '—'}</td>
                <td><a href="${BASE_URL}/storage/download/${file.id}" target="_blank" class="link">⬇️ Скачать</a></td>
            </tr>`;
        }
        html += `</tbody></table></div>`;
        vectorsContainer.innerHTML = html;
    } catch (e) {
        vectorsContainer.innerHTML = `<p class="text-muted">⚠️ Ошибка: ${e.message}</p>`;
    }
}

// ---------- ЗАГРУЗКА ОТЧЁТОВ ----------
async function loadReports() {
    try {
        const resp = await fetch(`${BASE_URL}/storage/list?user_id=admin&file_type=reports&limit=5`);
        if (!resp.ok) {
            reportsContainer.innerHTML = `<p class="text-muted">Нет отчётов.</p>`;
            return;
        }
        const files = await resp.json();
        if (!files || files.length === 0) {
            reportsContainer.innerHTML = `<p class="text-muted">Нет отчётов.</p>`;
            return;
        }
        let html = `<div class="table-wrap"><table>
            <thead><tr><th>Дата</th><th>Файл</th><th>Ссылка</th></tr></thead><tbody>`;
        for (const file of files) {
            const created = file.created_at ? new Date(file.created_at).toLocaleString() : '—';
            const fileName = file.file_key || 'отчёт';
            html += `<tr>
                <td>${created}</td>
                <td>${fileName}</td>
                <td><a href="${BASE_URL}/reports/${file.id}" target="_blank" class="link">🔗 Открыть</a></td>
            </tr>`;
        }
        html += `</tbody></table></div>`;
        reportsContainer.innerHTML = html;
    } catch (e) {
        reportsContainer.innerHTML = `<p class="text-muted">⚠️ Ошибка: ${e.message}</p>`;
    }
}

// ---------- УПРАВЛЕНИЕ СПИСКОМ САЙТОВ ----------
async function loadSources() {
    sourcesStatus.textContent = '⏳ Загрузка...';
    try {
        const resp = await fetch(`${BASE_URL}/ingestor/admin/settings`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (data.sources && data.sources.length > 0) {
            sourcesTextarea.value = data.sources.join('\n');
            sourcesStatus.textContent = `✅ Загружено ${data.sources.length} сайтов. Cron: ${data.schedule_cron || 'не задан'}`;
        } else {
            sourcesTextarea.value = '';
            sourcesStatus.textContent = 'ℹ️ Ничего не сохранено.';
        }
        if (data.schedule_cron) {
            cronInput.value = data.schedule_cron;
        }
    } catch (e) {
        sourcesStatus.textContent = `❌ Ошибка: ${e.message}`;
        log(`Ошибка загрузки списка: ${e.message}`, 'error');
    }
}

async function saveSources() {
    const sources = sourcesTextarea.value.split('\n').map(s => s.trim()).filter(s => s);
    if (sources.length === 0) {
        sourcesStatus.textContent = '⚠️ Список пуст. Введите хотя бы один сайт.';
        return;
    }
    sourcesStatus.textContent = '⏳ Сохранение...';
    try {
        const resp = await fetch(`${BASE_URL}/ingestor/admin/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sources: sources, schedule_cron: cronInput.value.trim() || '0 5 * * *' })
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        sourcesStatus.textContent = `✅ Сохранено ${sources.length} сайтов.`;
        log(`Список сайтов сохранён (${sources.length})`, 'success');
    } catch (e) {
        sourcesStatus.textContent = `❌ Ошибка: ${e.message}`;
        log(`Ошибка сохранения списка: ${e.message}`, 'error');
    }
}

async function measureSources() {
    const sources = sourcesTextarea.value.split('\n').map(s => s.trim()).filter(s => s);
    if (sources.length === 0) {
        trafficStatsResults.innerHTML = '<p class="text-muted">⚠️ Список сайтов пуст. Введите сайты для измерения.</p>';
        return;
    }
    trafficStatsResults.innerHTML = '<p class="text-muted">⏳ Измерение... (может занять до 30 секунд)</p>';
    try {
        const resp = await fetch(`${BASE_URL}/traffic_stats/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domains: sources })
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (data.results && data.results.length > 0) {
            let html = `<div class="table-wrap"><table>
                <thead><tr><th>Домен</th><th>Ранг</th><th>Open Page Rank</th><th>Ссылающиеся домены</th></tr></thead><tbody>`;
            for (const item of data.results) {
                html += `<tr>
                    <td>${item.domain || '—'}</td>
                    <td>${item.rank || '—'}</td>
                    <td>${item.open_page_rank !== undefined ? item.open_page_rank.toFixed(2) : '—'}</td>
                    <td>${item.referring_domains || '—'}</td>
                </tr>`;
            }
            html += `</tbody></table></div>`;
            trafficStatsResults.innerHTML = html;
            log(`Измерение завершено: ${data.results.length} доменов`, 'success');
        } else {
            trafficStatsResults.innerHTML = '<p class="text-muted">ℹ️ Нет данных для отображения.</p>';
        }
    } catch (e) {
        trafficStatsResults.innerHTML = `<p class="text-muted">❌ Ошибка: ${e.message}</p>`;
        log(`Ошибка измерения: ${e.message}`, 'error');
    }
}

function clearSources() {
    sourcesTextarea.value = '';
    trafficStatsResults.innerHTML = '<p class="text-muted">Окна очищены.</p>';
    sourcesStatus.textContent = '🗑️ Очищено';
    log('Списки очищены', 'info');
}

// ---------- УПРАВЛЕНИЕ CRON ----------
async function loadCron() {
    cronStatus.textContent = '⏳ Загрузка...';
    try {
        const resp = await fetch(`${BASE_URL}/ingestor/admin/settings`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (data.schedule_cron) {
            cronInput.value = data.schedule_cron;
            cronStatus.textContent = `✅ Загружено: ${data.schedule_cron}`;
        } else {
            cronInput.value = '0 5 * * *';
            cronStatus.textContent = 'ℹ️ Cron не задан, используется по умолчанию: 0 5 * * *';
        }
    } catch (e) {
        cronStatus.textContent = `❌ Ошибка: ${e.message}`;
        log(`Ошибка загрузки cron: ${e.message}`, 'error');
    }
}

async function saveCron() {
    const cron = cronInput.value.trim();
    if (!cron) {
        cronStatus.textContent = '⚠️ Введите корректную cron-строку.';
        return;
    }
    cronStatus.textContent = '⏳ Сохранение...';
    try {
        const sources = sourcesTextarea.value.split('\n').map(s => s.trim()).filter(s => s);
        const resp = await fetch(`${BASE_URL}/ingestor/admin/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sources: sources, schedule_cron: cron })
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        cronStatus.textContent = `✅ Сохранено: ${cron}`;
        log(`Cron сохранён: ${cron}`, 'success');
    } catch (e) {
        cronStatus.textContent = `❌ Ошибка: ${e.message}`;
        log(`Ошибка сохранения cron: ${e.message}`, 'error');
    }
}

// ---------- ПРИВЯЗКА СОБЫТИЙ ----------
runParserBtn.addEventListener('click', runParser);
runAnalysisBtn.addEventListener('click', runAnalysis);
generateReportBtn.addEventListener('click', () => {
    log('Запуск генерации отчёта без данных анализа — попробуйте сначала запустить анализ.', 'info');
});

loadSourcesBtn.addEventListener('click', loadSources);
saveSourcesBtn.addEventListener('click', saveSources);
measureSourcesBtn.addEventListener('click', measureSources);
clearSourcesBtn.addEventListener('click', clearSources);

loadCronBtn.addEventListener('click', loadCron);
saveCronBtn.addEventListener('click', saveCron);

// ---------- ИНИЦИАЛИЗАЦИЯ ----------
async function init() {
    log('🚀 Загрузка админ-панели...', 'info');
    await checkStatuses();
    await loadArticles();
    await loadVectors();
    await loadReports();
    await loadSources();
    await loadCron();
    log('✅ Готово', 'success');
}

init();

setInterval(() => {
    checkStatuses();
    loadArticles();
    loadVectors();
    loadReports();
}, 60000);