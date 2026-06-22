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
        ]
    )
else:
    urlpatterns.append(path("sources/", views.source_yaml_intent_source_list, name="source_list"))
