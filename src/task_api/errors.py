"""Application errors with safe client-facing messages."""


class ApiError(Exception):
    """An expected HTTP error."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(ApiError):
    def __init__(self) -> None:
        super().__init__(404, "not_found", "Task not found.")


class ConflictError(ApiError):
    def __init__(self) -> None:
        super().__init__(409, "conflict", "Task already exists.")
