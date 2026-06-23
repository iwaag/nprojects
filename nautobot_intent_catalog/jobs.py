"""Nautobot Jobs for intent source analysis."""

from __future__ import annotations

import json
from pathlib import Path

from .analysis import analyze_intent_sources
from .dnsmasq import export_dnsmasq_records, render_dnsmasq_export_json, render_dnsmasq_records_conf
from .evaluations import (
    ENDPOINT_TARGET_TYPE,
    NODE_TARGET_TYPE,
    evaluate_endpoint_intent,
    evaluate_node_intent,
    evaluate_service_intent,
)
from .importers import (
    desired_service_defaults,
    desired_service_dependencies,
    desired_service_identity,
    desired_endpoint_defaults,
    desired_endpoint_identity,
    desired_node_defaults,
    desired_node_identity,
    intent_source_defaults,
)
from .loaders import IntentSourceEntry
from .loaders import load_default_intent_sources, load_intent_sources

try:
    from django.conf import settings
    from django.utils import timezone
    from dcim.models import Device
    from ipam.models import IPAddress
    from nautobot.apps.jobs import BooleanVar, IntegerVar, Job, StringVar, register_jobs
    from virtualization.models import VirtualMachine

    from .models import DesiredDependency, DesiredEndpoint, DesiredNode, DesiredService, IntentEvaluation, IntentSource
except ImportError:  # pragma: no cover - Nautobot is not available in local unit tests.
    jobs = ()
else:

    class PreviewIntentSourceAnalysis(Job):
        """Dry-run analyze configured intent sources."""

        source_file = StringVar(
            default="",
            description="Optional path to intent_sources.yaml. Empty uses App configuration.",
        )
        fetch_timeout = IntegerVar(
            default=10,
            description="HTTP timeout in seconds for each lightweight file request.",
        )
        include_service_preview = BooleanVar(
            default=True,
            description="Log generated desired services as JSON.",
        )

        class Meta:
            name = "Preview Intent Source Analysis"
            description = "Dry-run Backstage catalog detection for configured intent sources."
            has_sensitive_variables = False

        def run(self, source_file: str, fetch_timeout: int, include_service_preview: bool) -> None:
            if source_file:
                load_result = load_intent_sources(Path(source_file))
            else:
                load_result = load_default_intent_sources(_configured_source_file())

            for error in load_result.errors:
                self.logger.warning(error)

            if load_result.errors and not load_result.intent_sources:
                raise ValueError("Intent source catalog could not be loaded; see Job logs for details.")

            result = analyze_intent_sources(
                load_result.intent_sources,
                fetch_timeout=float(fetch_timeout),
            )
            summary = {
                "source_path": str(load_result.source_path),
                "intent_sources": len(load_result.intent_sources),
                "source_analyses": len(result.source_analyses),
                "desired_services": len(result.desired_services),
                "analysis_errors": len(result.errors),
                "generated_at": result.generated_at,
            }

            self.logger.info("Intent source analysis summary: %s", _json(summary))
            self.logger.info("Intent source analysis detail: %s", _json(result.source_analyses))
            for error in result.errors:
                self.logger.warning(error)

            if include_service_preview:
                self.logger.info("Desired service preview: %s", _json(result.desired_services))


    class ImportIntentSources(Job):
        """Import intent source inputs from configured YAML into DB models."""

        source_file = StringVar(
            default="",
            description="Optional path to intent_sources.yaml. Empty uses App configuration.",
        )
        disable_missing = BooleanVar(
            default=False,
            description="Disable existing DB intent sources that are not present in the YAML input.",
        )

        class Meta:
            name = "Import Intent Sources"
            description = "Import intent source YAML rows into IntentSource records."
            has_sensitive_variables = False

        def run(self, source_file: str, disable_missing: bool) -> None:
            if source_file:
                load_result = load_intent_sources(Path(source_file))
            else:
                load_result = load_default_intent_sources(_configured_source_file())

            for error in load_result.errors:
                self.logger.warning(error)
            if load_result.errors:
                raise ValueError("Intent source catalog could not be loaded; see Job logs for details.")

            seen_urls = set()
            counts = {
                "created": 0,
                "updated": 0,
                "unchanged": 0,
                "disabled": 0,
                "nodes_created": 0,
                "nodes_updated": 0,
                "nodes_unchanged": 0,
                "endpoints_created": 0,
                "endpoints_updated": 0,
                "endpoints_unchanged": 0,
            }
            for source in load_result.intent_sources:
                seen_urls.add(source.url)
                defaults = intent_source_defaults(source)
                obj, created = IntentSource.objects.get_or_create(url=source.url, defaults=defaults)
                if created:
                    counts["created"] += 1
                elif _object_matches_defaults(obj, defaults):
                    counts["unchanged"] += 1
                else:
                    for key, value in defaults.items():
                        setattr(obj, key, value)
                    obj.save(update_fields=tuple(defaults.keys()))
                    counts["updated"] += 1

            if disable_missing:
                missing = IntentSource.objects.exclude(url__in=seen_urls).filter(enabled=True)
                counts["disabled"] = missing.update(enabled=False)

            source_by_key = _intent_source_lookup()
            node_by_key = {}
            for node in load_result.desired_nodes:
                intent_source = source_by_key.get(node.intent_source) if node.intent_source else None
                defaults = desired_node_defaults(node, intent_source_id=getattr(intent_source, "pk", None))
                identity = desired_node_identity(node)
                node_obj, created = DesiredNode.objects.get_or_create(**identity, defaults=defaults)
                if created:
                    counts["nodes_created"] += 1
                elif _object_matches_defaults(obj=node_obj, defaults=defaults):
                    counts["nodes_unchanged"] += 1
                else:
                    for key, value in defaults.items():
                        setattr(node_obj, key, value)
                    node_obj.save(update_fields=tuple(defaults.keys()))
                    counts["nodes_updated"] += 1
                node_by_key[node.slug] = node_obj
                node_by_key[node.name] = node_obj

            if load_result.desired_endpoints:
                existing_nodes = DesiredNode.objects.all()
                for node_obj in existing_nodes:
                    node_by_key.setdefault(node_obj.slug, node_obj)
                    node_by_key.setdefault(node_obj.name, node_obj)

            for endpoint in load_result.desired_endpoints:
                desired_node = node_by_key.get(endpoint.desired_node)
                if desired_node is None:
                    raise ValueError(f"Desired endpoint references missing desired node: {endpoint.desired_node}")
                identity = desired_endpoint_identity(endpoint, desired_node_id=desired_node.pk)
                defaults = desired_endpoint_defaults(endpoint)
                endpoint_obj, created = DesiredEndpoint.objects.get_or_create(**identity, defaults=defaults)
                if created:
                    counts["endpoints_created"] += 1
                elif _object_matches_defaults(obj=endpoint_obj, defaults=defaults):
                    counts["endpoints_unchanged"] += 1
                else:
                    for key, value in defaults.items():
                        setattr(endpoint_obj, key, value)
                    endpoint_obj.save(update_fields=tuple(defaults.keys()))
                    counts["endpoints_updated"] += 1

            self.logger.info(
                "Intent source import summary: %s",
                _json(
                    {
                        "source_path": str(load_result.source_path),
                        "intent_sources": len(load_result.intent_sources),
                        "desired_nodes": len(load_result.desired_nodes),
                        "desired_endpoints": len(load_result.desired_endpoints),
                        **counts,
                    }
                ),
            )


    class AnalyzeIntentSources(Job):
        """Analyze DB-backed intent sources and persist desired services plus dependencies."""

        fetch_timeout = IntegerVar(
            default=10,
            description="HTTP timeout in seconds for each lightweight file request.",
        )
        include_disabled = BooleanVar(
            default=False,
            description="Include disabled IntentSource rows in analysis.",
        )

        class Meta:
            name = "Analyze Intent Sources"
            description = "Analyze IntentSource records and persist desired services plus dependencies."
            has_sensitive_variables = False

        def run(self, fetch_timeout: int, include_disabled: bool) -> None:
            queryset = IntentSource.objects.all()
            if not include_disabled:
                queryset = queryset.filter(enabled=True)
            intent_sources = list(queryset.order_by("url"))
            entries = [_entry_from_intent_source(intent_source) for intent_source in intent_sources]
            source_by_url = {intent_source.url: intent_source for intent_source in intent_sources}

            result = analyze_intent_sources(entries, fetch_timeout=float(fetch_timeout))
            now = timezone.now()
            counts = {
                "intent_sources": len(intent_sources),
                "source_analyses": len(result.source_analyses),
                "services_created": 0,
                "services_updated": 0,
                "dependencies_created": 0,
                "dependencies_replaced": 0,
                "analysis_errors": len(result.errors),
            }

            for analysis in result.source_analyses:
                intent_source = source_by_url.get(analysis.get("url"))
                if intent_source is None:
                    continue
                intent_source.last_import_status = analysis.get("status")
                intent_source.last_imported_at = now
                intent_source.last_import_summary = analysis
                intent_source.save(
                    update_fields=("last_import_status", "last_imported_at", "last_import_summary")
                )

            for service in result.desired_services:
                source = service.get("intent_source") if isinstance(service.get("intent_source"), dict) else {}
                intent_source = source_by_url.get(source.get("url"))
                if intent_source is None:
                    self.logger.warning("Skipping desired service without matching intent source: %s", _json(service))
                    continue

                identity = desired_service_identity(service)
                defaults = desired_service_defaults(service)
                defaults["last_analyzed_at"] = now
                service_obj, created = DesiredService.objects.update_or_create(
                    intent_source=intent_source,
                    catalog_namespace=identity["catalog_namespace"],
                    catalog_metadata_name=identity["catalog_metadata_name"],
                    service_type=identity["service_type"],
                    defaults=defaults,
                )
                if created:
                    counts["services_created"] += 1
                else:
                    counts["services_updated"] += 1

                old_dependency_count = service_obj.dependencies.count()
                service_obj.dependencies.all().delete()
                counts["dependencies_replaced"] += old_dependency_count
                dependencies = [
                    DesiredDependency(source_service=service_obj, **dependency)
                    for dependency in desired_service_dependencies(service)
                ]
                DesiredDependency.objects.bulk_create(dependencies)
                counts["dependencies_created"] += len(dependencies)

            for error in result.errors:
                self.logger.warning(error)

            self.logger.info("Desired service import summary: %s", _json(counts))


    class EvaluateNodeIntent(Job):
        """Evaluate desired nodes against actual Nautobot Device/VM objects."""

        include_inactive = BooleanVar(
            default=False,
            description="Include deprecated and retired DesiredNode rows.",
        )

        class Meta:
            name = "Evaluate Node Intent"
            description = "Persist deterministic DesiredNode evaluations against actual Device and VirtualMachine rows."
            has_sensitive_variables = False

        def run(self, include_inactive: bool) -> None:
            nodes = DesiredNode.objects.select_related("realized_device", "realized_vm").order_by("slug")
            if not include_inactive:
                nodes = nodes.exclude(lifecycle__in=("deprecated", "retired"))

            device_candidates = list(Device.objects.all().order_by("name"))
            vm_candidates = list(VirtualMachine.objects.all().order_by("name"))
            counts = {"evaluated": 0, "created": 0, "updated": 0, "statuses": {}}
            for desired_node in nodes:
                payload = evaluate_node_intent(
                    desired_node,
                    device_candidates=device_candidates,
                    vm_candidates=vm_candidates,
                )
                created = _upsert_evaluation(payload)
                counts["evaluated"] += 1
                counts["created" if created else "updated"] += 1
                counts["statuses"][payload.status] = counts["statuses"].get(payload.status, 0) + 1

            self.logger.info("Desired node evaluation summary: %s", _json(counts))


    class EvaluateEndpointIntent(Job):
        """Evaluate desired endpoints against actual Nautobot IP and interface facts."""

        include_inactive = BooleanVar(
            default=False,
            description="Include endpoints attached to deprecated and retired DesiredNode rows.",
        )

        class Meta:
            name = "Evaluate Endpoint Intent"
            description = "Persist deterministic DesiredEndpoint evaluations against actual IPAddress and interface facts."
            has_sensitive_variables = False

        def run(self, include_inactive: bool) -> None:
            endpoints = DesiredEndpoint.objects.select_related(
                "desired_node",
                "desired_node__realized_device",
                "desired_node__realized_vm",
                "realized_ip_address",
            ).order_by("desired_node__slug", "endpoint_type", "name")
            if not include_inactive:
                endpoints = endpoints.exclude(desired_node__lifecycle__in=("deprecated", "retired"))

            ip_candidates = list(IPAddress.objects.all().order_by("address"))
            counts = {"evaluated": 0, "created": 0, "updated": 0, "statuses": {}}
            for desired_endpoint in endpoints:
                desired_node = desired_endpoint.desired_node
                node_payload = evaluate_node_intent(
                    desired_node,
                    device_candidates=(),
                    vm_candidates=(),
                )
                payload = evaluate_endpoint_intent(
                    desired_endpoint,
                    ip_candidates=ip_candidates,
                    node_evaluation=node_payload,
                )
                created = _upsert_evaluation(payload)
                counts["evaluated"] += 1
                counts["created" if created else "updated"] += 1
                counts["statuses"][payload.status] = counts["statuses"].get(payload.status, 0) + 1

            self.logger.info("Desired endpoint evaluation summary: %s", _json(counts))


    class EvaluateServiceIntent(Job):
        """Evaluate desired services without invoking AI review."""

        include_inactive = BooleanVar(
            default=False,
            description="Include deprecated and retired DesiredService rows.",
        )
        ai_review_enabled = BooleanVar(
            default=False,
            description="Reserve the AI review interface in evaluation facts without executing AI review.",
        )

        class Meta:
            name = "Evaluate Service Intent"
            description = "Persist deterministic DesiredService evaluations from lifecycle, requirements, and dependencies."
            has_sensitive_variables = False

        def run(self, include_inactive: bool, ai_review_enabled: bool) -> None:
            services = DesiredService.objects.select_related("intent_source").prefetch_related(
                "dependencies",
                "dependencies__resolved_service",
            ).order_by("catalog_namespace", "catalog_metadata_name", "service_type")
            if not include_inactive:
                services = services.exclude(lifecycle__in=("deprecated", "retired"))

            counts = {"evaluated": 0, "created": 0, "updated": 0, "statuses": {}}
            for desired_service in services:
                payload = evaluate_service_intent(
                    desired_service,
                    ai_review_enabled=ai_review_enabled,
                )
                created = _upsert_evaluation(payload)
                counts["evaluated"] += 1
                counts["created" if created else "updated"] += 1
                counts["statuses"][payload.status] = counts["statuses"].get(payload.status, 0) + 1

            self.logger.info("Desired service evaluation summary: %s", _json(counts))


    class ExportDnsmasqRecords(Job):
        """Dry-run export desired endpoint dnsmasq records."""

        include_skipped = BooleanVar(
            default=True,
            description="Include skipped endpoint details in the Job log.",
        )

        class Meta:
            name = "Export dnsmasq Records"
            description = "Dry-run deterministic dnsmasq record export from DesiredEndpoint rows."
            has_sensitive_variables = False

        def run(self, include_skipped: bool) -> None:
            endpoints = DesiredEndpoint.objects.select_related("desired_node").order_by(
                "desired_node__slug",
                "endpoint_type",
                "name",
            )
            endpoint_list = list(endpoints)
            export = export_dnsmasq_records(
                endpoint_list,
                endpoint_evaluations=_latest_evaluations(ENDPOINT_TARGET_TYPE),
                node_evaluations=_latest_evaluations(NODE_TARGET_TYPE),
                include_skipped=include_skipped,
            )
            generated_at = timezone.now().isoformat()
            job_result_id = str(getattr(self.job_result, "id", "")) or None
            self.create_file(
                "dnsmasq-records.conf",
                render_dnsmasq_records_conf(export, generated_at=generated_at, job_result_id=job_result_id),
            )
            self.create_file(
                "dnsmasq-export.json",
                render_dnsmasq_export_json(export, generated_at=generated_at, job_result_id=job_result_id),
            )
            self.logger.info("dnsmasq export summary: %s", _json(export.summary))
            self.logger.info(
                "dnsmasq export counts: %s",
                _json(
                    {
                        "dns_records": len(export.dns_records),
                        "dhcp_reservations": len(export.dhcp_reservations),
                        "skipped_details": len(export.skipped),
                    }
                ),
            )
            self.logger.info("dnsmasq export files: dnsmasq-records.conf, dnsmasq-export.json")
            if include_skipped:
                self.logger.info("dnsmasq export skipped endpoints: %s", _json(export.skipped))

    jobs = (
        PreviewIntentSourceAnalysis,
        ImportIntentSources,
        AnalyzeIntentSources,
        EvaluateNodeIntent,
        EvaluateEndpointIntent,
        EvaluateServiceIntent,
        ExportDnsmasqRecords,
    )
    register_jobs(*jobs)


def _configured_source_file():
    plugins_config = getattr(settings, "PLUGINS_CONFIG", {}) or {}
    app_config = plugins_config.get("nautobot_intent_catalog", {}) or {}
    return app_config.get("intent_sources_file")


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _upsert_evaluation(payload) -> bool:
    _, created = IntentEvaluation.objects.update_or_create(
        target_type=payload.target_type,
        target_id=payload.target_id,
        source_hash=payload.source_hash,
        defaults={
            **payload.as_defaults(),
            "reviewed_at": timezone.now(),
        },
    )
    return created


def _latest_evaluations(target_type: str) -> dict:
    evaluations = {}
    rows = IntentEvaluation.objects.filter(target_type=target_type).order_by("target_id", "-reviewed_at", "-created")
    for evaluation in rows:
        evaluations.setdefault(str(evaluation.target_id), evaluation)
    return evaluations


def _entry_from_intent_source(intent_source) -> IntentSourceEntry:
    source_config = intent_source.source_config or {}
    return IntentSourceEntry(
        url=intent_source.url,
        enabled=intent_source.enabled,
        ref=intent_source.ref,
        owner=intent_source.owner,
        service_hint=source_config.get("service_hint") or intent_source.name,
        catalog_paths=list(source_config.get("catalog_paths") or []),
        basic_file_paths=list(source_config.get("basic_file_paths") or []),
        raw_url_template=source_config.get("raw_url_template"),
    )


def _intent_source_lookup() -> dict:
    lookup = {}
    for intent_source in IntentSource.objects.all():
        lookup[intent_source.slug] = intent_source
        lookup[intent_source.name] = intent_source
        if intent_source.url:
            lookup[intent_source.url] = intent_source
    return lookup


def _object_matches_defaults(obj, defaults: dict) -> bool:
    return all(getattr(obj, key) == value for key, value in defaults.items())
