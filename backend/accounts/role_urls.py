from django.urls import path

from accounts.role_views import (
    AssignRoleView,
    ChangeRoleView,
    RevokeRoleView,
    RoleManagementUserDetailView,
)

urlpatterns = [
    path(
        "role-management/users/<int:user_id>/",
        RoleManagementUserDetailView.as_view(),
        name="role-management-user-detail",
    ),
    path(
        "role-management/users/<int:user_id>/assign/",
        AssignRoleView.as_view(),
        name="role-management-assign",
    ),
    path(
        "role-management/users/<int:user_id>/change/",
        ChangeRoleView.as_view(),
        name="role-management-change",
    ),
    path(
        "role-management/users/<int:user_id>/revoke/",
        RevokeRoleView.as_view(),
        name="role-management-revoke",
    ),
]
