from collections import Counter
import hashlib
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import connection
from django.db.models import Count

from apps.formations.services import ProposedMember, create_team_formation
from apps.profiles.models import UserProfile
from apps.projects.models import ProjectTaskTemplate, ProjectVersion, SprintTemplate


canonical_migration = import_module(
    "apps.projects.migrations.0006_populate_helpdesk_l1_canonical_content"
)
CANONICAL_SPRINTS = canonical_migration.CANONICAL_SPRINTS


@pytest.fixture
def valid_formation_reference(
    django_user_model,
    password,
    backend_role,
    frontend_role,
    designer_role,
    django_stack,
):
    def create_reference(project_version):
        assert project_version.is_published
        facilitator = django_user_model.objects.create_user(
            email="canonical-content-facilitator@example.com",
            password=password,
            is_staff=True,
        )
        members = []
        member_specs = (
            (
                "canonical-content-backend@example.com",
                backend_role,
                django_stack,
            ),
            (
                "canonical-content-frontend@example.com",
                frontend_role,
                None,
            ),
            (
                "canonical-content-designer@example.com",
                designer_role,
                None,
            ),
        )
        for email, role, technology_stack in member_specs:
            member_user = django_user_model.objects.create_user(
                email=email,
                password=password,
            )
            UserProfile.objects.create(
                user=member_user,
                selected_role=role,
            )
            members.append(ProposedMember(member_user, role, technology_stack))

        return create_team_formation(
            project_version=project_version,
            created_by=facilitator,
            members=members,
        )

    return create_reference


def canonical_yaml_data(yaml_path):
    lines = yaml_path.read_text(encoding="utf-8").splitlines()
    sprints = []
    sprint = None
    work_item = None
    index = 0

    while index < len(lines):
        line = lines[index]
        if line.startswith("  - sequence: "):
            sprint = {
                "sequence": int(line.removeprefix("  - sequence: ")),
                "title": None,
                "brief": None,
                "planned_start_offset_days": None,
                "planned_duration_days": None,
                "work_items": [],
            }
            sprints.append(sprint)
            work_item = None
        elif line.startswith("    title: ") and work_item is None:
            sprint["title"] = line.removeprefix("    title: ")
        elif line == "    brief: >-":
            index += 1
            sprint["brief"] = lines[index].strip()
        elif line.startswith("    planned_start_offset_days: "):
            sprint["planned_start_offset_days"] = int(
                line.removeprefix("    planned_start_offset_days: ")
            )
        elif line.startswith("    planned_duration_days: "):
            sprint["planned_duration_days"] = int(
                line.removeprefix("    planned_duration_days: ")
            )
        elif line.startswith("    - role: "):
            role = line.removeprefix("    - role: ")
            work_item = {
                "role": None if role == "null" else role,
                "technology_stack": None,
                "position": None,
                "title": None,
                "description": None,
            }
            sprint["work_items"].append(work_item)
        elif line.startswith("      technology_stack: "):
            stack = line.removeprefix("      technology_stack: ")
            work_item["technology_stack"] = None if stack == "null" else stack
        elif line.startswith("      position: "):
            work_item["position"] = int(line.removeprefix("      position: "))
        elif line.startswith("      title: "):
            work_item["title"] = line.removeprefix("      title: ")
        elif line == "      description: >-":
            index += 1
            work_item["description"] = lines[index].strip()
        index += 1

    return tuple(
        {
            **sprint,
            "work_items": tuple(dict(item) for item in sprint["work_items"]),
        }
        for sprint in sprints
    )


def expected_work_items():
    return [
        (
            sprint["sequence"],
            work_item["role"],
            work_item["technology_stack"],
            work_item["position"],
            work_item["title"],
            work_item["description"],
        )
        for sprint in CANONICAL_SPRINTS
        for work_item in sprint["work_items"]
    ]


def work_item_sort_key(item):
    return (
        item[0],
        item[1] or "",
        item[2] or "",
        item[3],
        item[4],
    )


def test_canonical_yaml_checksum_matches_frozen_migration_source():
    yaml_path = Path(__file__).resolve().parents[2] / "helpdesk_l1_content.yaml"

    assert hashlib.sha256(yaml_path.read_bytes()).hexdigest().upper() == (
        canonical_migration.CANONICAL_SOURCE_SHA256
    )
    assert canonical_yaml_data(yaml_path) == CANONICAL_SPRINTS


def test_frozen_canonical_dataset_has_the_approved_shape():
    assert len(CANONICAL_SPRINTS) == 6
    assert [sprint["sequence"] for sprint in CANONICAL_SPRINTS] == [1, 2, 3, 4, 5, 6]
    assert sum(len(sprint["work_items"]) for sprint in CANONICAL_SPRINTS) == 126

    for sprint in CANONICAL_SPRINTS:
        counts = Counter(item["role"] for item in sprint["work_items"])
        assert counts == {
            "BACKEND_DEVELOPER": 6,
            "FRONTEND_DEVELOPER": 6,
            "PRODUCT_DESIGNER": 6,
            None: 3,
        }
        assert all(
            item["technology_stack"] is None for item in sprint["work_items"]
        )


@pytest.mark.django_db
@pytest.mark.postgresql
class TestHelpdeskL1CanonicalDatabaseContent:
    def test_target_project_version_and_sprints_are_exact(self, helpdesk_version):
        assert helpdesk_version.project_template.slug == "helpdesk-lite"
        assert helpdesk_version.project_template.level.number == 1
        assert helpdesk_version.version_number == 1

        actual = list(
            helpdesk_version.sprint_templates.order_by("sequence", "id").values(
                "sequence",
                "title",
                "brief",
                "planned_start_offset_days",
                "planned_duration_days",
            )
        )
        expected = [
            {
                "sequence": sprint["sequence"],
                "title": sprint["title"],
                "brief": sprint["brief"],
                "planned_start_offset_days": sprint["planned_start_offset_days"],
                "planned_duration_days": sprint["planned_duration_days"],
            }
            for sprint in CANONICAL_SPRINTS
        ]

        assert actual == expected

    def test_work_items_match_every_frozen_canonical_value(self, helpdesk_version):
        actual = [
            (
                work_item.sprint_template.sequence,
                work_item.role.code if work_item.role_id is not None else None,
                (
                    work_item.technology_stack.code
                    if work_item.technology_stack_id is not None
                    else None
                ),
                work_item.position,
                work_item.title,
                work_item.description,
            )
            for work_item in helpdesk_version.work_items.select_related(
                "sprint_template", "role", "technology_stack"
            )
        ]

        assert sorted(actual, key=work_item_sort_key) == sorted(
            expected_work_items(), key=work_item_sort_key
        )

    def test_each_sprint_has_exact_role_shared_counts_and_positions(
        self,
        helpdesk_version,
    ):
        sprints = helpdesk_version.sprint_templates.prefetch_related(
            "work_items__role", "work_items__technology_stack"
        ).order_by("sequence", "id")

        for sprint in sprints:
            items = list(sprint.work_items.all())
            counts = Counter(
                item.role.code if item.role_id is not None else None for item in items
            )
            assert len(items) == 21
            assert counts == {
                "BACKEND_DEVELOPER": 6,
                "FRONTEND_DEVELOPER": 6,
                "PRODUCT_DESIGNER": 6,
                None: 3,
            }
            assert all(item.technology_stack_id is None for item in items)
            assert sorted(
                item.position
                for item in items
                if item.role_id is not None
                and item.role.code == "BACKEND_DEVELOPER"
            ) == [1, 2, 3, 4, 5, 6]
            assert sorted(
                item.position
                for item in items
                if item.role_id is not None
                and item.role.code == "FRONTEND_DEVELOPER"
            ) == [1, 2, 3, 4, 5, 6]
            assert sorted(
                item.position
                for item in items
                if item.role_id is not None
                and item.role.code == "PRODUCT_DESIGNER"
            ) == [1, 2, 3, 4, 5, 6]
            assert sorted(item.position for item in items if item.role_id is None) == [
                1,
                2,
                3,
            ]

    def test_no_unscheduled_legacy_or_duplicate_canonical_keys(
        self,
        helpdesk_version,
    ):
        assert helpdesk_version.work_items.count() == 126
        assert not helpdesk_version.work_items.filter(
            sprint_template__isnull=True
        ).exists()
        assert not helpdesk_version.work_items.values(
            "sprint_template_id",
            "role_id",
            "technology_stack_id",
            "position",
        ).annotate(row_count=Count("id")).filter(row_count__gt=1).exists()

    def test_population_rerun_does_not_touch_another_project_version(
        self,
        helpdesk_version,
    ):
        another_version = ProjectVersion.objects.create(
            project_template=helpdesk_version.project_template,
            version_number=2,
        )

        canonical_migration.populate_helpdesk_l1_canonical_content(
            django_apps,
            SimpleNamespace(connection=connection),
        )

        assert not SprintTemplate.objects.filter(
            project_version=another_version
        ).exists()
        assert not ProjectTaskTemplate.objects.filter(
            project_version=another_version
        ).exists()

    def test_exact_legacy_unscheduled_row_is_reconciled(self, helpdesk_version):
        legacy_item = ProjectTaskTemplate.objects.create(
            project_version=helpdesk_version,
            title="Authentication",
            position=1,
        )

        canonical_migration.populate_helpdesk_l1_canonical_content(
            django_apps,
            SimpleNamespace(connection=connection),
        )

        assert not ProjectTaskTemplate.objects.filter(id=legacy_item.id).exists()
        assert helpdesk_version.work_items.count() == 126

    def test_unrecognized_unscheduled_row_is_not_deleted(self, helpdesk_version):
        unknown_item = ProjectTaskTemplate.objects.create(
            project_version=helpdesk_version,
            title="Developer-owned unscheduled content",
            position=500,
        )

        with pytest.raises(RuntimeError, match="unrecognized unscheduled"):
            canonical_migration.populate_helpdesk_l1_canonical_content(
                django_apps,
                SimpleNamespace(connection=connection),
            )

        assert ProjectTaskTemplate.objects.filter(id=unknown_item.id).exists()

    def test_referenced_exact_target_is_a_noop(
        self,
        helpdesk_version,
        valid_formation_reference,
    ):
        valid_formation_reference(helpdesk_version)

        canonical_migration.populate_helpdesk_l1_canonical_content(
            django_apps,
            SimpleNamespace(connection=connection),
        )

        assert helpdesk_version.sprint_templates.count() == 6
        assert helpdesk_version.work_items.count() == 126

    def test_referenced_noncanonical_target_is_rejected_before_writes(
        self,
        helpdesk_version,
        valid_formation_reference,
    ):
        removed_item = helpdesk_version.work_items.order_by("id").first()
        removed_item.delete()
        valid_formation_reference(helpdesk_version)

        with pytest.raises(RuntimeError, match="is referenced"):
            canonical_migration.populate_helpdesk_l1_canonical_content(
                django_apps,
                SimpleNamespace(connection=connection),
            )

        assert helpdesk_version.work_items.count() == 125
