from django.db import migrations


def create_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.get_or_create(name="Doctor")


class Migration(migrations.Migration):
    """Members of the Doctor group can record diagnoses and prescriptions."""

    dependencies = [("kiosk", "0008_finalize_visits"), ("auth", "0012_alter_user_first_name_max_length")]

    operations = [migrations.RunPython(create_group, migrations.RunPython.noop)]
