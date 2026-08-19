class FormationDomainError(Exception):
    pass


class InvalidFormationMembers(FormationDomainError):
    pass


class InvalidFormationStack(FormationDomainError):
    pass


class ReadyCheckNotPending(FormationDomainError):
    pass


class ReadyCheckExpired(FormationDomainError):
    pass


class ReadyCheckNotReplaceable(FormationDomainError):
    pass


class FormationAlreadyReady(FormationDomainError):
    pass


class MemberHasActiveProjectRun(FormationDomainError):
    pass


class FormationCompletionConflict(FormationDomainError):
    pass
