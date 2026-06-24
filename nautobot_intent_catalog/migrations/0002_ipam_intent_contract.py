# Generated manually for desired IP allocation intent.

from __future__ import annotations

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_intent_catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="desiredendpoint",
            name="ip_policy",
            field=models.CharField(
                choices=[
                    ("static", "Static"),
                    ("dhcp_reserved", "DHCP reserved"),
                    ("external", "External"),
                ],
                default="static",
                max_length=64,
            ),
        ),
        migrations.CreateModel(
            name="DesiredIPRange",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("_custom_field_data", models.JSONField(blank=True, default=dict, editable=False)),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=255, unique=True)),
                ("start_address", models.CharField(max_length=128)),
                ("end_address", models.CharField(max_length=128)),
                (
                    "range_policy",
                    models.CharField(
                        choices=[
                            ("static_pool", "Static pool"),
                            ("dhcp_reservable_pool", "DHCP reservable pool"),
                            ("dhcp_dynamic_pool", "DHCP dynamic pool"),
                            ("excluded", "Excluded"),
                        ],
                        default="static_pool",
                        max_length=64,
                    ),
                ),
                (
                    "lifecycle",
                    models.CharField(
                        choices=[
                            ("planned", "Planned"),
                            ("approved", "Approved"),
                            ("active", "Active"),
                            ("deprecated", "Deprecated"),
                            ("retired", "Retired"),
                        ],
                        default="planned",
                        max_length=64,
                    ),
                ),
                ("generate_dnsmasq", models.BooleanField(default=False)),
                ("dnsmasq_options", models.JSONField(blank=True, default=dict)),
                ("description", models.TextField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "desired IP range",
                "verbose_name_plural": "desired IP ranges",
                "ordering": ("start_address", "end_address", "name"),
            },
        ),
    ]
