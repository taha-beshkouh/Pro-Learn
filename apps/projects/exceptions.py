class ProjectConfigurationError(Exception):
    """The persisted project definition violates a domain invariant."""


class InvalidProjectStackSelection(Exception):
    """A requested stack is not valid for the selected project role."""
