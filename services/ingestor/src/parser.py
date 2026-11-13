import asyncio
import re
import logging
from datetime import datetime
from urllib.parse import urlparse, urljoin
from typing import List, Optional, Tuple
import httpx
from playwright.async_api import async_playwright
from trafilatura import extract, extract_metadata
from readability import Document
from lxml import html as lxml_html
from lxml import etree

from .models import Article
from .settings import settings
SOURCES = settings.SOURCES
OUTPUT_DIR = settings.OUTPUT_DIR
SKIP_EXTENSIONS = settings.SKIP_EXTENSIONS
MIN_TEXT_LENGTH = settings.MIN_TEXT_LENGTH
ARTICLE_URL_PATTERNS = settings.ARTICLE_URL_PATTERNS

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

# НОВОЕ (уровень 2.1): чёрный список URL-путей.
# Работает для любой тематики — это индексные, служебные, юридические страницы,
# а не «новостные» в узком смысле.
BLACKLIST_URL_PATTERNS = [
    r'/news/?$',              # голый индекс /news/ (interfax)
    r'/story/?$',             # голый индекс /story/ (interfax)
    r'/about/?$',
    r'/contacts?/?$',
    r'/policy/?$',
    r'/privacy/?$',
    r'/rules/?$',
    r'/recommendation',
    r'/rss/?$',
    r'/feed/?$',
    r'/tag/',
    r'/category/',
    r'/archive/',
    r'/search',
    r'/login',
    r'/register',
    r'/sitemap',
]

# НОВОЕ (уровень 2.2): "плохие" заголовки индексных/служебных страниц.
# Универсально для любой тематики.
BAD_TITLES = {
    "новости", "сюжеты", "о компании", "новости за",
    "политика конфиденциальности", "правила применения",
    "правила использования", "правила применения рекомендательных технологий",
    "архив", "все материалы", "фотогалереи", "фотохроника",
    "проекты", "о нас", "контакты", "реклама", "подписка",
}

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

# --------------------- НОВОЕ (уровень 2.2): проверка "это статья?" ---------------------

def _is_bad_title(t: str) -> bool:
    """Заголовок похож на дату/служебный, а не на название материала."""
    if not t or len(t.strip()) < 10:
        return True
    t = t.strip()
    # "03 November 2026 - Colonel Cassad"
    if re.match(
        r'^\d{1,2}\s+'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+\d{4}\s*[-—:]',
        t, re.IGNORECASE
    ):
        return True
    # "03 ноября 2026 - ..."
    if re.match(
        r'^\d{1,2}\s+'
        r'(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)'
        r'\s+\d{4}\s*[-—:]',
        t, re.IGNORECASE
    ):
        return True
    # "2026-11-03 ..."
    if re.match(r'^\d{4}-\d{2}-\d{2}', t):
        return True
    return False


def is_article_page(html: str, url: str) -> Tuple[bool, str]:
    """
    Структурная эвристика: является ли HTML-страница статьёй любого жанра,
    а не индексной/служебной страницей.

    Правило: 2 из 3 структурных маркеров:
      1) есть published_at (meta/time/itemprop);
      2) ровно один <h1> с осмысленным текстом;
      3) низкая плотность анкоров в основном тексте (< 0.35).

    Тематика (спорт, мода, политика, авто...) не важна — проверка жанро-нейтральна.
    """
    if not html:
        return False, "no_html"

    try:
        tree = lxml_html.fromstring(html)
    except Exception as e:
        return False, f"parse_error:{type(e).__name__}"

    # Быстрая проверка: заголовок индексной/служебной страницы
    title_xpath = tree.xpath("//meta[@property='og:title']/@content | //title/text()")
    title_raw = (title_xpath[0].strip().lower() if title_xpath else "")
    # отрезаем типичный суффикс "— сайт.ru"
    title_core = re.split(r'\s*[-—|]\s*', title_raw)[0].strip() if title_raw else ""
    if title_core in BAD_TITLES or title_raw in BAD_TITLES:
        return False, f"bad_title:{title_core[:40] or title_raw[:40]}"
    if title_raw.startswith("новости за"):
        return False, "index_news_by_date"

    markers = 0
    details = []

    # Маркер 1: published_at
    has_pubdate = bool(tree.xpath(
        "//meta[@property='article:published_time']/@content or "
        "//meta[@property='og:article:published_time']/@content or "
        "//meta[@name='date']/@content or "
        "//meta[@name='publish-date']/@content or "
        "//meta[@name='pubdate']/@content or "
        "//time[@datetime]/@datetime or "
        "//*[@itemprop='datePublished']/@content or "
        "//*[@itemprop='datePublished']/text()"
    ))
    if has_pubdate:
        markers += 1
        details.append("pubdate")

    # Маркер 2: единственный <h1> с осмысленным текстом
    h1_list = tree.xpath("//h1")
    if len(h1_list) == 1:
        h1_text = (h1_list[0].text_content() or "").strip()
        if len(h1_text) >= 10 and not _is_bad_title(h1_text):
            markers += 1
            details.append("h1")

    # Маркер 3: низкая плотность анкоров в основном тексте
    link_ratio = 1.0
    body = tree.xpath("//body")
    if body:
        try:
            # Удаляем навигацию/футер/сайдбар, чтобы не портили плотность
            for bad in body[0].xpath(".//nav | .//footer | .//aside | .//header"):
                parent = bad.getparent()
                if parent is not None:
                    parent.remove(bad)
            body_text = body[0].text_content() or ""
            links = body[0].xpath(".//a")
            link_text = " ".join((l.text_content() or "") for l in links)
            total_len = max(len(body_text), 1)
            link_ratio = len(link_text) / total_len
        except Exception:
            link_ratio = 1.0

    if link_ratio < 0.35:
        markers += 1
        details.append(f"links={link_ratio:.2f}")
    else:
        details.append(f"links={link_ratio:.2f}!high")

    if markers >= 2:
        return True, "ok(" + ",".join(details) + ")"
    return False, "not_article(" + ",".join(details) + ")"


# --------------------- Парсинг статьи ---------------------

async def parse_article(url: str, client: httpx.AsyncClient) -> Optional[Article]:
    html = await fetch_html(url, client)
    if not html:
        logger.info(f"    skip[fetch]: {url}")
        return None

    # НОВОЕ (уровень 2.2): проверяем, что это статья, а не индекс/справка
    is_article, reason = is_article_page(html, url)
    if not is_article:
        logger.info(f"    skip[{reason}]: {url}")
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
        logger.info(f"    skip[short]: {url} ({len(text)} симв.)")
        return None

    meta = extract_metadata(html)
    title = meta.title.strip() if meta and meta.title else ""
    author = meta.author.strip() if meta and meta.author else None
    pub_date = meta.date if meta and meta.date else None

    tree = lxml_html.fromstring(html)

    # НОВОЕ (уровень 2.3): каскад извлечения title.
    # Если trafilatura вернул дату ("03 November 2026 - Colonel Cassad") или мусор —
    # пробуем og:title, затем единственный h1, затем <title>.
    if _is_bad_title(title):
        og_title = tree.xpath("//meta[@property='og:title']/@content")
        if og_title and not _is_bad_title(og_title[0]):
            title = og_title[0].strip()
        else:
            h1 = tree.xpath("//h1")
            if len(h1) == 1:
                h1_text = " ".join(x.strip() for x in h1[0].itertext() if x.strip())
                if not _is_bad_title(h1_text):
                    title = h1_text
            if _is_bad_title(title):
                t_title = tree.xpath("//title/text()")
                if t_title and not _is_bad_title(t_title[0]):
                    title = t_title[0].strip()

    if not title:
        title = "Без заголовка"

    published_at = None
    if pub_date:
        try:
            published_at = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
        except:
            pass

    return Article(
        source=urlparse(url).netloc,
        url=url,
        title=title,
        body=text[:20000],
        author=author,
        published_at=published_at,
        scraped_at=datetime.now()
    )

# --------------------- Сбор ссылок ---------------------

def is_article_url(url: str) -> bool:
    # Исключаем медиафайлы
    if any(url.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
        return False
    # Исключаем явно служебные страницы
    excluded = ['#', 'search', 'tag', 'category', 'contact', 'about', 'login', 'register', 'feed', 'sitemap', 'javascript:']
    if any(x in url.lower() for x in excluded):
        return False
    # НОВОЕ (уровень 2.1): чёрный список путей
    for bp in BLACKLIST_URL_PATTERNS:
        if re.search(bp, url.lower()):
            return False
    for pattern in ARTICLE_URL_PATTERNS:
        if re.search(pattern, url):
            return True
    return False

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
    # 1. Сначала пробуем стандартный fetch_html (httpx, при ошибке — playwright)
    html_content = await fetch_html(source_url, client)
    if not html_content:
        # Если совсем ничего нет, пробуем playwright принудительно
        logger.info(f"    fetch_html не дал результат, пробуем playwright для главной {source_url}")
        html_content = await fetch_html_playwright(source_url)
        if not html_content:
            return []

    # 2. Извлекаем ссылки из HTML
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

    # 3. Если ссылок слишком мало (меньше 3) — сайт, вероятно, динамический,
    #    принудительно рендерим через Playwright и повторяем сбор.
    if len(article_links) < 3:
        logger.info("    Мало ссылок, пробуем через Playwright с рендерингом")
        html_pw = await fetch_html_playwright(source_url)
        if html_pw:
            tree_pw = lxml_html.fromstring(html_pw)
            links_pw = tree_pw.xpath("//a/@href")
            full_links_pw = []
            for link in links_pw:
                full_url = urljoin(source_url, link)
                if base_domain in full_url:
                    full_links_pw.append(full_url)
            unique_pw = list(dict.fromkeys(full_links_pw))
            article_links_pw = [url for url in unique_pw if is_article_url(url)]
            if article_links_pw:
                logger.info(f"    После рендеринга найдено ссылок: {len(article_links_pw)}")
                article_links = article_links_pw
            else:
                logger.info("    Рендеринг не дал новых ссылок, оставляем оригинальный список")

    return article_links

async def get_article_links(source_url: str, client: httpx.AsyncClient) -> List[str]:
    links = await get_article_links_from_rss(source_url, client)
    if links:
        return links
    return await get_article_links_from_html(source_url, client)

# --------------------- Основная функция для источника ---------------------

async def fetch_articles_from_source(
    source_url: str,
    limit: int = 5,
    stats: Optional[dict] = None,
) -> List[Article]:
    if stats is None:
        stats = {}
    # Инициализируем нулями — чтобы в отчёте всегда были все ключи
    stats.update({
        "links_rss": 0,
        "links_html": 0,
        "links_total": 0,
        "links_used": 0,
        "articles_parsed": 0,
        "articles_skipped": 0,
        "articles_error": 0,
        "fetch_method": "none",
        "rss_urls_tried": 0,
    })

    logger.info(f"\nОбработка источника: {source_url}")
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        # Пробуем RSS — считаем, сколько путей проверено
        rss_paths = ['/rss', '/feed', '/rss.xml', '/feed.xml', '/xml']
        stats["rss_urls_tried"] = len(rss_paths)

        rss_links = await get_article_links_from_rss(source_url, client)
        stats["links_rss"] = len(rss_links)

        if rss_links:
            stats["fetch_method"] = "rss"
            links = rss_links
        else:
            stats["fetch_method"] = "html"
            links = await get_article_links_from_html(source_url, client)
            stats["links_html"] = len(links)

        stats["links_total"] = len(links)
        links = links[:limit]
        stats["links_used"] = len(links)

        if not links:
            logger.info("    Ссылок на статьи не найдено")
            return []

        tasks = [parse_article(url, client) for url in links]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles = []
        for res in results:
            if isinstance(res, Article):
                articles.append(res)
                stats["articles_parsed"] += 1
            elif isinstance(res, Exception):
                stats["articles_error"] += 1
                logger.info(f"    Ошибка парсинга: {res}")
            else:
                # None — отсеяно по длине текста или fetch не удался
                stats["articles_skipped"] += 1
        return articles