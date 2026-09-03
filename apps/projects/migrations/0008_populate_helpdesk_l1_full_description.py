from django.db import migrations


TARGET_PROJECT_SLUG = "helpdesk-lite"
TARGET_LEVEL_NUMBER = 1
TARGET_VERSION_NUMBER = 1

APPROVED_FULL_DESCRIPTION = (
    "Helpdesk Lite یک پروژه تیمی برای طراحی و توسعه یک سیستم پشتیبانی و مدیریت "
    "درخواست‌هاست. در این پروژه، یک تیم سه‌نفره شامل Backend Developer، Frontend "
    "Developer و Product Designer طی ۶ هفته روی ساخت یک محصول واقعی کار می‌کنند. "
    "زمان مورد انتظار برای هر عضو حدود ۱۰ تا ۱۲ ساعت در هفته است.\n\n"
    "محصول دو نوع کاربر اصلی دارد: Requester و Agent. Requester می‌تواند درخواست "
    "پشتیبانی یا Ticket ایجاد کند، Ticketهای خودش را ببیند و روند رسیدگی به آن‌ها را "
    "دنبال کند. Agent نیز Ticketهای قابل رسیدگی را مشاهده می‌کند، یک Ticket بدون "
    "مسئول را Claim می‌کند و پس از آن می‌تواند وضعیت و اولویت آن را طبق قوانین پروژه "
    "مدیریت کند. سیستم همچنین شامل Category، Comments، History، Search، Filter و "
    "Pagination است و دسترسی کاربران باید بر اساس نقش و مالکیت اطلاعات کنترل شود.\n\n"
    "پروژه در ۶ Sprint پیش می‌رود. ابتدا زیرساخت محصول و Authentication ساخته می‌شود؛ "
    "سپس جریان کامل Requester، فرایند کاری Agent، Comments و History تکمیل می‌شود. در "
    "Sprintهای بعد Search، Filter، Pagination و بخش‌های مربوط به پایداری و کیفیت محصول "
    "بررسی می‌شوند. Sprint پایانی نیز به یکپارچه‌سازی نهایی، تست، بررسی امنیت و "
    "دیتابیس، مستندسازی و آماده‌سازی نسخه قابل تحویل اختصاص دارد.\n\n"
    "در تمام Sprintها سه نقش تیم روی یک محصول مشترک کار می‌کنند و علاوه بر وظایف مخصوص "
    "هر نقش، فعالیت‌های مشترکی برای هماهنگی، Integration و بررسی نسخه فعلی محصول دارند. "
    "تست و یکپارچه‌سازی نیز از ابتدای پروژه بخشی از روند کار است و فقط به مرحله پایانی "
    "موکول نمی‌شود."
)


def populate_helpdesk_l1_full_description(apps, schema_editor):
    ProjectVersion = apps.get_model("projects", "ProjectVersion")
    TeamFormation = apps.get_model("formations", "TeamFormation")
    ProjectRun = apps.get_model("formations", "ProjectRun")
    db_alias = schema_editor.connection.alias

    target_ids = list(
        ProjectVersion.objects.using(db_alias)
        .filter(
            project_template__slug=TARGET_PROJECT_SLUG,
            project_template__level__number=TARGET_LEVEL_NUMBER,
            version_number=TARGET_VERSION_NUMBER,
        )
        .values_list("id", flat=True)
    )
    if len(target_ids) != 1:
        raise RuntimeError(
            "Helpdesk Lite Level 1 ProjectVersion v1 must exist exactly once; "
            f"found {len(target_ids)}."
        )

    project_version = (
        ProjectVersion.objects.using(db_alias)
        .select_for_update()
        .get(id=target_ids[0])
    )
    if project_version.full_description == APPROVED_FULL_DESCRIPTION:
        return
    if project_version.full_description:
        raise RuntimeError(
            "Helpdesk Lite Level 1 ProjectVersion v1 has a different non-empty "
            "full description. No content was changed."
        )

    is_referenced = (
        TeamFormation.objects.using(db_alias)
        .filter(project_version_id=project_version.id)
        .exists()
        or ProjectRun.objects.using(db_alias)
        .filter(project_version_id=project_version.id)
        .exists()
    )
    if is_referenced:
        raise RuntimeError(
            "Helpdesk Lite Level 1 ProjectVersion v1 is referenced by a "
            "TeamFormation or ProjectRun and its full description is not already "
            "canonical. No content was changed."
        )

    project_version.full_description = APPROVED_FULL_DESCRIPTION
    project_version.save(using=db_alias, update_fields=["full_description"])
    project_version.refresh_from_db(using=db_alias, fields=["full_description"])
    if project_version.full_description != APPROVED_FULL_DESCRIPTION:
        raise RuntimeError(
            "Helpdesk Lite Level 1 ProjectVersion v1 full-description population "
            "did not produce the exact approved content."
        )


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("projects", "0007_projectversion_full_description"),
    ]

    operations = [
        migrations.RunPython(
            populate_helpdesk_l1_full_description,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
