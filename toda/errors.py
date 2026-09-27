class TodaError(Exception):
    pass


class ManifestError(TodaError):
    pass


class SectionNotFound(ManifestError):
    pass


class SourceMissing(TodaError):
    pass


class DeployError(TodaError):
    pass
