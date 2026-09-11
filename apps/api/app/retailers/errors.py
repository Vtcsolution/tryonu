class RetailerNotConfiguredError(Exception):
    """Raised by a real retailer adapter when it has no API credentials.
    The ingestion service catches this, logs a warning, and skips the
    retailer instead of failing the whole sync."""
