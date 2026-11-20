class ApiError(Exception):
    """Mapped by the coordinator to {"error", "detail"?, **extra}; backends may raise it too."""

    def __init__(self, status: int, error: str, detail: str | None = None, **extra) -> None:
        self.status = status
        self.body = {"error": error, **({"detail": detail} if detail else {}), **extra}
