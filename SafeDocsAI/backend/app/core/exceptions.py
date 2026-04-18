class ExternalServiceError(Exception):
    def __init__(
        self,
        message: str,
        *,
        service: str,
        status_code: int = 502,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.service = service
        self.status_code = status_code
        self.cause = cause
