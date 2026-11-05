from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from channels.views import channel_api
from dashboard.views import officer_list, status_page

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/channel/<str:name>", channel_api, name="channel_api"),
    path("status/<str:code>", status_page, name="status"),
    path("officer/", officer_list, name="officer_list"),
    path("login/", auth_views.LoginView.as_view(template_name="dashboard/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
