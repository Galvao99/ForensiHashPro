class BiometricReportError(Exception):
    """Base para erros controlados da leitura de relatórios biométricos."""


class UnsupportedBiometricExtensionError(BiometricReportError):
    pass


class InvalidBiometricJsonError(BiometricReportError):
    pass


class UnrecognizedBiometricReportError(BiometricReportError):
    pass


class AmbiguousBiometricReportError(BiometricReportError):
    pass


class BiometricReportParsingError(BiometricReportError):
    pass

