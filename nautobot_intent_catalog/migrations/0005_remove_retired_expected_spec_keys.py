"""Remove retired placement and platform declarations from desired node JSON."""

from django.db import migrations


RETIRED_EXPECTED_SPEC_KEYS = ("ansible_groups", "host_os", "os")


def remove_retired_expected_spec_keys(apps, schema_editor):
    DesiredNode = apps.get_model("nautobot_intent_catalog", "DesiredNode")
    database = schema_editor.connection.alias

    for node in DesiredNode.objects.using(database).iterator():
        expected_spec = node.expected_spec
        if not isinstance(expected_spec, dict):
            continue

        cleaned_spec = {
            key: value
            for key, value in expected_spec.items()
            if key not in RETIRED_EXPECTED_SPEC_KEYS
        }
        if cleaned_spec != expected_spec:
            node.expected_spec = cleaned_spec
            node.save(using=database, update_fields=["expected_spec"])


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_intent_catalog", "0004_service_placement_operational_config"),
    ]

    operations = [
        migrations.RunPython(remove_retired_expected_spec_keys),
    ]
