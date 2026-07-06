class IpIntegrationError(Exception):
    pass

class MissingIpApiKeyError(IpIntegrationError):
    pass

class InvalidIpLookupError(IpIntegrationError):
    pass

class UnsupportedIpProviderError(IpIntegrationError):
    pass

class IpRateLimitError(IpIntegrationError):
    pass