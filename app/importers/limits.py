class ImportValidationError(ValueError):
    """A safe, static message that may be shown to the archive owner."""


class ImportItemError(ImportValidationError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
