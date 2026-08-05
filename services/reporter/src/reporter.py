import os
import logging
import json
import io
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd
from .settings import settings

logger = logging.getLogger(__name__)

async def generate_report(user_id: str, analysis_data: Dict[str, Any]) -> str:
    """
    Генерирует HTML-отчёт и сохраняет его в storage через API.
    Возвращает file_id (или полный URL для доступа).
    """
    # Генерация HTML (как раньше)
    logger.info("Начало генерации отчёта")
    # Извлекаем данные из анализа
    drift_score = analysis_data.get("drift_score", 0.0)
    shifted_topics = analysis_data.get("shifted_topics", [])
    cluster_details = analysis_data.get("cluster_details", {})

    # Строим графики
    logger.info("Строим спидометр")
    fig_drift = create_drift_gauge(drift_score)

    logger.info("Строим кластеры")
    fig_clusters = create_cluster_visualization(cluster_details)

    logger.info("Строим таблицу")
    table_html = create_shifted_topics_table(shifted_topics)

    # Формируем HTML-страницу
    logger.info("Собираем HTML")
    html_content = build_html_page(
        user_id=user_id,
        drift_fig=fig_drift,
        cluster_fig=fig_clusters,
        table_html=table_html,
        shifted_topics=shifted_topics
    )

    # Сохраняем HTML в буфер (без записи на диск)
    html_bytes = html_content.encode('utf-8')
    buf = io.BytesIO(html_bytes)
    buf.seek(0)

    # Формируем имя файла
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"report_{date_str}.html"

    # Отправляем в storage
    async with httpx.AsyncClient(timeout=30.0) as client:
        files = {'file': (filename, buf, 'text/html')}
        data = {
            'user_id': user_id,
            'file_type': 'reports',
            'file_key': filename,
            'metadata': json.dumps({
                "drift_score": drift_score,
                "shifted_topics_count": len(shifted_topics)
            })
        }
        try:
            resp = await client.post(
                f"{settings.STORAGE_URL}/upload",
                files=files,
                data=data
            )
            resp.raise_for_status()
            result = resp.json()
            file_id = result.get('id')
            logger.info(f"Отчёт сохранён в storage: file_id={file_id}")
            return file_id
        except Exception as e:
            logger.error(f"Ошибка сохранения отчёта в storage: {e}")
            # fallback: сохранить локально (если нужно)
            # local_path = save_locally(...)
            raise

def create_drift_gauge(drift_score: float) -> go.Figure:
    """Создаёт спидометр для показателя дрифта."""
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = drift_score * 100,  # переводим в проценты
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Индекс дрифта, %"},
        delta = {'reference': 50},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 30], 'color': "lightgreen"},
                {'range': [30, 70], 'color': "yellow"},
                {'range': [70, 100], 'color': "salmon"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 70
            }
        }
    ))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
    return fig

def create_cluster_visualization(cluster_details: Dict[str, Any]) -> Optional[go.Figure]:
    """
    Создаёт 2D-проекцию кластеров (если есть данные).
    Использует UMAP-координаты из cluster_details (если они там есть).
    В реальности мы их не передаём – это заглушка.
    """
    # В текущей версии analyzer не возвращает координаты точек,
    # поэтому генерируем заглушку – сообщение о том, что данных для визуализации нет.
    # Позже можно доработать, чтобы analyzer возвращал координаты.
    fig = go.Figure()
    fig.add_annotation(
        text="Визуализация кластеров будет доступна после расширения данных",
        x=0.5, y=0.5, showarrow=False, font=dict(size=16)
    )
    fig.update_layout(
        height=400,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=20, r=20, t=20, b=20)
    )
    return fig

def create_shifted_topics_table(shifted_topics: list) -> str:
    """Генерирует HTML-таблицу сместившихся тем."""
    if not shifted_topics:
        return "<p><em>Смещений тем не обнаружено.</em></p>"
    rows = []
    for item in shifted_topics:
        old = ", ".join(item.get("old_terms", [])) or "—"
        new = ", ".join(item.get("new_terms", [])) or "—"
        rows.append(f"<tr><td>{old}</td><td>{new}</td></tr>")
    table = """
    <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
        <thead><tr><th>Было (старые термины)</th><th>Стало (новые термины)</th></tr></thead>
        <tbody>{}</tbody>
    </table>
    """.format("\n".join(rows))
    return table

def build_html_page(user_id: str, drift_fig: go.Figure, cluster_fig: go.Figure, table_html: str, shifted_topics: list) -> str:
    """Собирает полную HTML-страницу."""
    drift_html = drift_fig.to_html(full_html=False, include_plotlyjs='cdn')
    cluster_html = cluster_fig.to_html(full_html=False, include_plotlyjs='cdn')

    summary = ""
    if shifted_topics:
        summary = "<h3>Краткое резюме (заглушка для LLM)</h3><p>Здесь будет текст от YandexGPT.</p>"

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Семантический радар — отчёт</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .row {{ display: flex; flex-wrap: wrap; margin: 20px 0; }}
        .col {{ flex: 1; padding: 10px; min-width: 300px; }}
        h1 {{ color: #2c3e50; }}
        hr {{ margin: 30px 0; }}
    </style>
</head>
<body>
<div class="container">
    <h1>📊 Семантический радар — отчёт</h1>
    <p><strong>Пользователь:</strong> {user_id}</p>
    <p><strong>Дата генерации:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    <hr>

    <div class="row">
        <div class="col">
            <h3>Индекс дрифта</h3>
            {drift_html}
        </div>
        <div class="col">
            <h3>Кластеры тем</h3>
            {cluster_html}
        </div>
    </div>

    <hr>
    <h3>Сместившиеся темы</h3>
    {table_html}

    <hr>
    {summary}

    <hr>
    <p style="color: #888; font-size: 0.9em;">Отчёт сгенерирован автоматически.</p>
</div>
</body>
</html>
    """
    return html

def generate_text_summary(shifted_topics: list, drift_score: float) -> str:
    """
    Заглушка для будущего вызова YandexGPT.
    Возвращает текстовое описание трендов.
    """
    # Здесь будет реальный вызов YandexGPT
    return "Заглушка: текстовое описание трендов будет добавлено позже."