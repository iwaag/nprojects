"""Add the read-only deployment_profiles projection synced from Ansible."""

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_intent_catalog", "0005_remove_retired_expected_spec_keys"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeploymentProfileProjection",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("_custom_field_data", models.JSONField(blank=True, default=dict, editable=False)),
                ("digest", models.CharField(max_length=64, unique=True)),
                ("profiles", models.JSONField(blank=True, default=dict)),
                ("synced_at", models.DateTimeField()),
            ],
            options={
                "verbose_name": "deployment profile projection",
                "verbose_name_plural": "deployment profile projections",
                "ordering": ("-synced_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="deploymentprofileprojection",
            constraint=models.CheckConstraint(
                check=models.expressions.RawSQL(
                    "jsonb_typeof(profiles) = 'object'",
                    (),
                    output_field=models.BooleanField(),
                ),
                name="nic_profile_projection_object",
            ),
        ),
    ]
