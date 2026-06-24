"""URL patterns for the Nautobot Intent Catalog App."""

from django.urls import path

from . import views

urlpatterns = [
    path("sources/source-yaml/", views.source_yaml_intent_source_list, name="source_yaml_list"),
]

if hasattr(views, "IntentSourceListView"):
    urlpatterns.extend(
        [
            path("sources/", views.IntentSourceListView.as_view(), name="intentsource_list"),
            path("sources/add/", views.IntentSourceEditView.as_view(), name="intentsource_add"),
            path("sources/<uuid:pk>/", views.IntentSourceView.as_view(), name="intentsource"),
            path("sources/<uuid:pk>/edit/", views.IntentSourceEditView.as_view(), name="intentsource_edit"),
            path(
                "sources/<uuid:pk>/delete/",
                views.IntentSourceDeleteView.as_view(),
                name="intentsource_delete",
            ),
            path("services/", views.DesiredServiceListView.as_view(), name="desiredservice_list"),
            path("services/<uuid:pk>/", views.DesiredServiceView.as_view(), name="desiredservice"),
            path("services/<uuid:pk>/edit/", views.DesiredServiceEditView.as_view(), name="desiredservice_edit"),
            path(
                "services/<uuid:pk>/delete/",
                views.DesiredServiceDeleteView.as_view(),
                name="desiredservice_delete",
            ),
            path("dependencies/", views.DesiredDependencyListView.as_view(), name="desireddependency_list"),
            path("dependencies/<uuid:pk>/", views.DesiredDependencyView.as_view(), name="desireddependency"),
            path(
                "dependencies/<uuid:pk>/edit/",
                views.DesiredDependencyEditView.as_view(),
                name="desireddependency_edit",
            ),
            path(
                "dependencies/<uuid:pk>/delete/",
                views.DesiredDependencyDeleteView.as_view(),
                name="desireddependency_delete",
            ),
            path("nodes/", views.DesiredNodeListView.as_view(), name="desirednode_list"),
            path("nodes/quick-add/", views.DesiredHostQuickAddView.as_view(), name="desiredhost_quick_add"),
            path("nodes/add/", views.DesiredNodeEditView.as_view(), name="desirednode_add"),
            path("nodes/<uuid:pk>/", views.DesiredNodeView.as_view(), name="desirednode"),
            path("nodes/<uuid:pk>/edit/", views.DesiredNodeEditView.as_view(), name="desirednode_edit"),
            path(
                "nodes/<uuid:pk>/delete/",
                views.DesiredNodeDeleteView.as_view(),
                name="desirednode_delete",
            ),
            path("endpoints/", views.DesiredEndpointListView.as_view(), name="desiredendpoint_list"),
            path("endpoints/add/", views.DesiredEndpointEditView.as_view(), name="desiredendpoint_add"),
            path("endpoints/<uuid:pk>/", views.DesiredEndpointView.as_view(), name="desiredendpoint"),
            path(
                "endpoints/<uuid:pk>/edit/",
                views.DesiredEndpointEditView.as_view(),
                name="desiredendpoint_edit",
            ),
            path(
                "endpoints/<uuid:pk>/delete/",
                views.DesiredEndpointDeleteView.as_view(),
                name="desiredendpoint_delete",
            ),
            path("ip-ranges/", views.DesiredIPRangeListView.as_view(), name="desirediprange_list"),
            path("ip-ranges/add/", views.DesiredIPRangeEditView.as_view(), name="desirediprange_add"),
            path("ip-ranges/<uuid:pk>/", views.DesiredIPRangeView.as_view(), name="desirediprange"),
            path(
                "ip-ranges/<uuid:pk>/edit/",
                views.DesiredIPRangeEditView.as_view(),
                name="desirediprange_edit",
            ),
            path(
                "ip-ranges/<uuid:pk>/delete/",
                views.DesiredIPRangeDeleteView.as_view(),
                name="desirediprange_delete",
            ),
            path("evaluations/", views.IntentEvaluationListView.as_view(), name="intentevaluation_list"),
            path("evaluations/add/", views.IntentEvaluationEditView.as_view(), name="intentevaluation_add"),
            path("evaluations/<uuid:pk>/", views.IntentEvaluationView.as_view(), name="intentevaluation"),
            path(
                "evaluations/<uuid:pk>/edit/",
                views.IntentEvaluationEditView.as_view(),
                name="intentevaluation_edit",
            ),
            path(
                "evaluations/<uuid:pk>/delete/",
                views.IntentEvaluationDeleteView.as_view(),
                name="intentevaluation_delete",
            ),
        ]
    )
else:
    urlpatterns.append(path("sources/", views.source_yaml_intent_source_list, name="source_list"))
