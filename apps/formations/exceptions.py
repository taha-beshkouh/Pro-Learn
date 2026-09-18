class FormationDomainError(Exception):
    pass


class InvalidProjectReadinessSelection(FormationDomainError):
    pass


class ActiveProjectReadinessExists(FormationDomainError):
    pass


class MemberHasUnresolvedFormation(FormationDomainError):
    pass


class InvalidFormationMembers(FormationDomainError):
    pass


class InvalidFormationReadiness(FormationDomainError):
    pass


class InvalidFormationStack(FormationDomainError):
    pass


class ReadyCheckNotPending(FormationDomainError):
    pass


class ReadyCheckExpired(FormationDomainError):
    pass


class ReadyCheckNotReplaceable(FormationDomainError):
    pass


class GithubUsernameRequired(FormationDomainError):
    pass


class InvalidGithubUsername(FormationDomainError):
    pass


class InvalidRepositoryUrl(FormationDomainError):
    pass


class RepositoryAlreadyAssigned(FormationDomainError):
    pass


class InvalidDesignWorkspaceUrl(FormationDomainError):
    pass


class DesignWorkspaceAccessDenied(FormationDomainError):
    pass


class ProjectRunRepositoryRequired(FormationDomainError):
    pass


class DesignWorkspaceRequired(FormationDomainError):
    pass


class InvalidFinalCommitUrl(FormationDomainError):
    pass


class InvalidDeploymentUrl(FormationDomainError):
    pass


class FormationAlreadyReady(FormationDomainError):
    pass


class MemberHasActiveProjectRun(FormationDomainError):
    pass


class FormationCompletionConflict(FormationDomainError):
    pass


class SprintRuntimeConfigurationError(FormationDomainError):
    pass


class SprintTransitionNotAllowed(FormationDomainError):
    pass


class SprintAccessDenied(FormationDomainError):
    pass


class SprintSubmissionNotAllowed(FormationDomainError):
    pass


class InvalidReviewFeedback(FormationDomainError):
    pass


class SprintDeadlinePassed(FormationDomainError):
    pass


class ProjectRunTransitionNotAllowed(FormationDomainError):
    pass


class ProjectRunDeadlineNotReached(FormationDomainError):
    pass
