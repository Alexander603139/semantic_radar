import asyncio
import re
import logging
from datetime import datetime
from urllib.parse import urlparse, urljoin
from typing import List, Optional
import httpx
from playwright.async_api import async_playwright
from trafilatura import extract, extract_metadata
from readability import Document
from lxml import html as lxml_html
from lxml import etree

from .models import Article
from .config import (
    SOURCES,
    OUTPUT_DIR,
    SKIP_EXTENSIONS,
    ARTICLE_URL_PATTERNS,
    MIN_TEXT_LENGTH,
)

# --------------------- Логгер ---------------------
logger = logging.getLogger(__name__)

# --------------------- Конфигурация ---------------------
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
DEFAULT_TIMEOUT = 30.0  # секунд
MAX_RETRIES = 2

NAV_SELECTORS = [
    "header", "footer", "nav", "aside",
    ".menu", ".navigation", ".sidebar", ".ad", ".banner",
    "[role='banner']", "[role='navigation']", "[role='complementary']",
    ".header", ".footer", ".nav", ".side"
]

CONTENT_SELECTORS = [
    "article",
    ".article__block",          # ria.ru
    ".Paragraph_paragraph__",   # tass.ru
    ".article-body",
    ".content",
    ".text",
    "main",
    ".post-content",
    ".entry-content"
]

# --------------------- HTTP и Playwright ---------------------

async def fetch_html_httpx(url: str, client: httpx.AsyncClient) -> Optional[str]:
    try:
        resp = await client.get(
            url,
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={'User-Agent': USER_AGENT}
        )
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.info(f"  httpx ошибка для {url}: {e}")
        return None

async def fetch_html_playwright(url: str) -> Optional[str]:
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-dev-shm-usage', '--no-sandbox']
                )
                context = await browser.new_context(user_agent=USER_AGENT)
                page = await context.new_page()
                await page.goto(url, timeout=DEFAULT_TIMEOUT * 1000, wait_until='domcontentloaded')

                for selector in CONTENT_SELECTORS:
                    try:
                        await page.wait_for_selector(selector, timeout=5000)
                        break
                    except:
                        continue

                for selector in NAV_SELECTORS:
                    elements = await page.query_selector_all(selector)
                    for el in elements:
                        await el.evaluate("node => node.remove()")

                html = await page.content()
                await browser.close()
                return html
        except Exception as e:
            logger.warning(f"Playwright попытка {attempt+1} для {url} не удалась: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
    logger.error(f"Playwright не смог загрузить {url} после {MAX_RETRIES+1} попыток")
    return None

async def fetch_html(url: str, client: httpx.AsyncClient) -> Optional[str]:
    """Сначала httpx, при любой ошибке (включая 403) — playwright."""
    html = await fetch_html_httpx(url, client)
    if html is not None:
        return html
    # Если httpx вернул None (любая ошибка), пробуем playwright
    logger.info(f"  httpx не дал результат, пробуем playwright для {url}")
    return await fetch_html_playwright(url)

# --------------------- Извлечение текста ---------------------

def extract_text_with_readability(html: str) -> str:
    if not html:
        return ""
    try:
        doc = Document(html)
        content_html = doc.summary()
        if content_html:
            tree = lxml_html.fromstring(content_html)
            return tree.text_content().strip() or ""
    except Exception as e:
        logger.info(f"Readability error: {e}")
    return ""

def extract_text_with_trafilatura(html: str) -> str:
    text = extract(html, include_comments=False, include_tables=False)
    if not text or len(text) < MIN_TEXT_LENGTH:
        text = extract(html, include_comments=False, include_tables=True)
    return text.strip() if text else ""

async def extract_text_from_page(html: str, page=None) -> str:
    text = extract_text_with_readability(html)
    if len(text) >= MIN_TEXT_LENGTH:
        return text[:20000]

    text = extract_text_with_trafilatura(html)
    if len(text) >= MIN_TEXT_LENGTH:
        return text[:20000]

    if page:
        for selector in CONTENT_SELECTORS:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text and len(text.strip()) >= MIN_TEXT_LENGTH:
                        return text.strip()[:20000]
            except:
                continue
        text = await page.text_content('body')
        if text and len(text.strip()) >= MIN_TEXT_LENGTH:
            return text.strip()[:20000]

    return text[:20000] if text else ""

# --------------------- Парсинг статьи ---------------------

async def parse_article(url: str, client: httpx.AsyncClient) -> Optional[Article]:
    html = await fetch_html(url, client)
    if not html:
        return None

    text = await extract_text_from_page(html, page=None)
    if len(text) < MIN_TEXT_LENGTH:
        # Если текст короткий, пробуем playwright принудительно (если fetch_html не использовал его)
        html_pw = await fetch_html_playwright(url)
        if html_pw:
            text = await extract_text_from_page(html_pw, page=None)
            if len(text) >= MIN_TEXT_LENGTH:
                html = html_pw

    if len(text) < MIN_TEXT_LENGTH:
        logger.info(f"    Текст слишком короткий ({len(text)} симв.), пропускаем {url}")
        return None

    meta = extract_metadata(html)
    title = meta.title.strip() if meta and meta.title else ""
    author = meta.author.strip() if meta and meta.author else None
    pub_date = meta.date if meta and meta.date else None

    if not title:
        tree = lxml_html.fromstring(html)
        title_elem = tree.xpath("//title/text()")
        if title_elem:
            title = title_elem[0].strip()

    published_at = None
    if pub_date:
        try:
            published_at = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
        except:
            pass

    return Article(
        source=urlparse(url).netloc,
        url=url,
        title=title or "Без заголовка",
        body=text[:20000],
        author=author,
        published_at=published_at,
        scraped_at=datetime.now()
    )

# --------------------- Сбор ссылок (упрощённый фильтр) ---------------------

def is_article_url(url: str) -> bool:
    # Исключаем медиафайлы
    if any(url.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
        return False
    # Исключаем явно служебные страницы
    excluded = ['#', '?', 'search', 'tag', 'category', 'contact', 'about', 'login', 'register', 'feed', 'sitemap', 'javascript:']
    if any(x in url.lower() for x in excluded):
        return False
    # Если ссылка не пустая и не главная страница — считаем статьёй
    return True

async def get_article_links_from_rss(source_url: str, client: httpx.AsyncClient) -> List[str]:
    rss_paths = ['/rss', '/feed', '/rss.xml', '/feed.xml', '/xml']
    base = source_url.rstrip('/')
    for path in rss_paths:
        rss_url = base + path
        try:
            resp = await client.get(rss_url, timeout=10.0)
            if resp.status_code == 200 and 'xml' in resp.headers.get('content-type', ''):
                root = etree.fromstring(resp.content)
                links = []
                for item in root.xpath('//item'):
                    link = item.find('link')
                    if link is not None and link.text:
                        links.append(link.text)
                    else:
                        guid = item.find('guid')
                        if guid is not None and guid.text:
                            links.append(guid.text)
                if links:
                    logger.info(f"    RSS найден: {rss_url}, ссылок: {len(links)}")
                    return links
        except:
            continue
    return []

async def get_article_links_from_html(source_url: str, client: httpx.AsyncClient) -> List[str]:
    html_content = await fetch_html(source_url, client)
    if not html_content:
        # Если fetch_html вернул None, пробуем playwright принудительно
        logger.info(f"    fetch_html не дал результат, пробуем playwright для главной {source_url}")
        html_content = await fetch_html_playwright(source_url)
        if not html_content:
            return []
    tree = lxml_html.fromstring(html_content)
    links = tree.xpath("//a/@href")
    base_domain = urlparse(source_url).netloc
    full_links = []
    for link in links:
        full_url = urljoin(source_url, link)
        if base_domain in full_url:
            full_links.append(full_url)
    unique = list(dict.fromkeys(full_links))
    article_links = [url for url in unique if is_article_url(url)]
    logger.info(f"    Найдено ссылок на статьи: {len(article_links)}")
    return article_links

async def get_article_links(source_url: str, client: httpx.AsyncClient) -> List[str]:
    links = await get_article_links_from_rss(source_url, client)
    if links:
        return links
    return await get_article_links_from_html(source_url, client)

# --------------------- Основная функция для источника ---------------------

async def fetch_articles_from_source(source_url: str, limit: int = 5) -> List[Article]:
    logger.info(f"\nОбработка источника: {source_url}")
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        links = await get_article_links(source_url, client)
        if not links:
            logger.info("    Ссылок на статьи не найдено")
            return []
        links = links[:limit]
        tasks = [parse_article(url, client) for url in links]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles = []
        for res in results:
            if isinstance(res, Article):
                articles.append(res)
            elif isinstance(res, Exception):
                logger.info(f"    Ошибка парсинга: {res}")
        logger.info(f"    Успешно спарсено: {len(articles)} статей")
        return articles