from urllib.parse import urlparse

def clean_domain(raw: str) -> str:
    """
    Очищает домен от протоколов, путей, портов и www.
    Не отклоняет невалидные форматы, а максимально их нормализует.
    """
    if not raw:
        return ""
    
    raw = raw.strip().lower()
    
    # Добавляем схему, чтобы urlparse корректно выделил netloc
    if not raw.startswith(('http://', 'https://')):
        raw = 'http://' + raw
        
    parsed = urlparse(raw)
    domain = parsed.netloc
    
    # Fallback, если netloc пустой
    if not domain:
        domain = parsed.path
        
    # Убираем www.
    if domain.startswith('www.'):
        domain = domain[4:]
        
    # Убираем порт
    domain = domain.split(':')[0]
    
    # Убираем слеши в конце
    domain = domain.strip('/')
    
    return domain