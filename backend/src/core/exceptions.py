class ParseError(Exception):
    """Raised when a parsing error occurs."""
    pass

class EmbeddingError(Exception):
    """Raised when an error occurs during embedding generation."""
    pass

class StoreError(Exception):
    """Raised when an error occurs during storage operations."""
    pass