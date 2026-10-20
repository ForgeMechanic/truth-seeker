class TruthSeekerError(Exception):
    """A recoverable input, policy, evidence, or state error."""


class MissingEvidence(TruthSeekerError):
    pass


class Conflict(TruthSeekerError):
    pass
