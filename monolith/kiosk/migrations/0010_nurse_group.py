from django.db import migrations


def create_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.get_or_create(name="Nurse")


class Migration(migrations.Migration):
    dependencies = [("kiosk", "0009_doctor_group")]

    operations = [migrations.RunPython(create_group, migrations.RunPython.noop)]
