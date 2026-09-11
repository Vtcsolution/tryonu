class AffiliateNetworkNotConfiguredError(Exception):
    """Raised by a network adapter with no API credentials yet — the
    caller should skip it, not fail the whole operation."""
