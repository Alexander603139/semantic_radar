class OPRClientError(Exception):
    """Базовое исключение для OPR клиента."""

class OPRServerError(OPRClientError):
    """Ошибка на стороне OpenPageRank (5xx)."""

class OPRClientValidationError(OPRClientError):
    """Ошибка валидации/авторизации на стороне OpenPageRank (4xx)."""