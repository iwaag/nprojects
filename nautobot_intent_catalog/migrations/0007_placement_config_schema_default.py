"""Default placement config_schema_version to the production profile contract version."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_intent_catalog", "0006_deployment_profile_projection"),
    ]

    operations = [
        migrations.AlterField(
            model_name="desiredserviceplacement",
            name="config_schema_version",
            # Matches PRODUCTION_PROFILE_CONTRACT_VERSION; placements created via the
            # operation always overwrite this with the selected profile's value, so the
            # default only guards against empty saves and satisfies the nonempty constraint.
            field=models.CharField(default="1", max_length=64),
        ),
    ]
