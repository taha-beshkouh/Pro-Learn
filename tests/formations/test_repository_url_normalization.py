import pytest

from apps.formations.exceptions import InvalidRepositoryUrl
from apps.formations.services import _repository_url_identity


def test_repository_identity_normalizes_obvious_github_aliases():
    first_url, first_identity = _repository_url_identity(
        " HTTPS://WWW.GITHUB.COM/ProLearn/Example.git/ "
    )
    second_url, second_identity = _repository_url_identity(
        "http://github.com/prolearn/example?source=staff#readme"
    )

    assert first_url == "https://github.com/prolearn/example"
    assert second_url == "http://github.com/prolearn/example"
    assert first_identity == second_identity


def test_repository_identity_keeps_distinct_repository_paths_distinct():
    _, first_identity = _repository_url_identity(
        "https://github.com/prolearn/project-one"
    )
    _, second_identity = _repository_url_identity(
        "https://github.com/prolearn/project-two"
    )

    assert first_identity != second_identity


def test_repository_identity_rejects_embedded_credentials():
    with pytest.raises(InvalidRepositoryUrl):
        _repository_url_identity("https://token@github.com/prolearn/private")
