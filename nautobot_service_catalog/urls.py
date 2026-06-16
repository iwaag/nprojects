"""URL patterns for the Nautobot Service Catalog App."""

from django.urls import path

from . import views

urlpatterns = [
    path("repositories/source-yaml/", views.source_yaml_repository_list, name="repository_source_yaml_list"),
]

if hasattr(views, "ServiceRepositoryListView"):
    urlpatterns.extend(
        [
            path("repositories/", views.ServiceRepositoryListView.as_view(), name="servicerepository_list"),
            path("repositories/add/", views.ServiceRepositoryEditView.as_view(), name="servicerepository_add"),
            path("repositories/<uuid:pk>/", views.ServiceRepositoryView.as_view(), name="servicerepository"),
            path(
                "repositories/<uuid:pk>/edit/",
                views.ServiceRepositoryEditView.as_view(),
                name="servicerepository_edit",
            ),
            path(
                "repositories/<uuid:pk>/delete/",
                views.ServiceRepositoryDeleteView.as_view(),
                name="servicerepository_delete",
            ),
            path(
                "candidates/",
                views.DesiredServiceCandidateListView.as_view(),
                name="desiredservicecandidate_list",
            ),
            path(
                "candidates/<uuid:pk>/",
                views.DesiredServiceCandidateView.as_view(),
                name="desiredservicecandidate",
            ),
            path(
                "candidates/<uuid:pk>/edit/",
                views.DesiredServiceCandidateEditView.as_view(),
                name="desiredservicecandidate_edit",
            ),
            path(
                "candidates/<uuid:pk>/delete/",
                views.DesiredServiceCandidateDeleteView.as_view(),
                name="desiredservicecandidate_delete",
            ),
            path("dependencies/", views.ServiceDependencyListView.as_view(), name="servicedependency_list"),
            path("dependencies/<uuid:pk>/", views.ServiceDependencyView.as_view(), name="servicedependency"),
            path(
                "dependencies/<uuid:pk>/edit/",
                views.ServiceDependencyEditView.as_view(),
                name="servicedependency_edit",
            ),
            path(
                "dependencies/<uuid:pk>/delete/",
                views.ServiceDependencyDeleteView.as_view(),
                name="servicedependency_delete",
            ),
        ]
    )
else:
    urlpatterns.append(path("repositories/", views.source_yaml_repository_list, name="repository_list"))
