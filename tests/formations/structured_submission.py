from apps.formations.models import ProjectRun, SprintRun
from apps.formations.services import submit_sprint as _submit_sprint


def configure_submission_runtime(project_run: ProjectRun) -> ProjectRun:
    update_fields = []
    if not project_run.repository_url:
        project_run.repository_url = (
            f"https://github.com/prolearn/run-{project_run.id.hex}"
        )
        update_fields.append("repository_url")
    if not project_run.design_workspace_url:
        project_run.design_workspace_url = (
            f"https://design.example.com/workspaces/{project_run.id}"
        )
        update_fields.append("design_workspace_url")
    if update_fields:
        project_run.save(update_fields=update_fields)
    return project_run


def structured_submission_kwargs(
    *, project_run: ProjectRun, sprint_run_id, revision_character: str = "a"
):
    project_run = configure_submission_runtime(project_run)
    return {
        "final_commit_url": (
            f"{project_run.repository_url}/commit/{revision_character * 40}"
        ),
        "deployment_url": (
            f"https://deploy.example.com/runs/{project_run.id}/sprints/{sprint_run_id}"
        ),
    }


def submit_structured_sprint(*, sprint_run_id, **kwargs):
    project_run = SprintRun.objects.select_related("project_run").get(
        id=sprint_run_id
    ).project_run
    kwargs.update(
        structured_submission_kwargs(
            project_run=project_run,
            sprint_run_id=sprint_run_id,
        )
    )
    return _submit_sprint(sprint_run_id=sprint_run_id, **kwargs)
