"""Persist the already-current DesiredNode realization contract."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_intent_catalog", "0002_ipam_intent_contract"),
    ]

    operations = [
        migrations.AddField(
            model_name="desirednode",
            name="accepted_actual_types",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Nautobot object types that may realize this desired node. "
                    "Allowed values are device, virtual_machine, and container."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="desirednode",
            name="node_type",
            field=models.CharField(
                choices=[
                    ("device", "Device"),
                    ("virtual_machine", "Virtual machine"),
                    ("container", "Container"),
                    ("service_host", "Service host"),
                ],
                default="device",
                max_length=64,
            ),
        ),
    ]
