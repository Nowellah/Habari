from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from channels.sim_views import sim_sms, sim_sms_outbox, sim_ussd
from channels.sms import sms_hook
from channels.ussd import ussd_hook
from channels.views import channel_api
from channels.voice_views import voice_shortcut, voice_transcribe
from dashboard import officer_views as ov
from dashboard import pwa_views
from dashboard.views import chat_page, metrics_page, officer_list, status_page
from partners_mock.views import referral_ack

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/channel/<str:name>", channel_api, name="channel_api"),
    path("hooks/sms", sms_hook, name="sms_hook"),
    path("hooks/ussd", ussd_hook, name="ussd_hook"),
    path("sim/sms", sim_sms, name="sim_sms"),
    path("sim/sms/outbox", sim_sms_outbox, name="sim_sms_outbox"),
    path("sim/ussd", sim_ussd, name="sim_ussd"),
    path("chat", chat_page, name="chat"),
    path("manifest.webmanifest", pwa_views.manifest, name="manifest"),
    path("sw.js", pwa_views.service_worker, name="service_worker"),
    path("share", pwa_views.share, name="share"),
    path("r", pwa_views.report_link, name="report_link"),
    path("mock/social", pwa_views.mock_social, name="mock_social"),
    path("metrics", metrics_page, name="metrics"),
    path("voice", voice_shortcut, name="voice"),
    path("api/voice/transcribe", voice_transcribe, name="voice_transcribe"),
    path("status/<str:code>", status_page, name="status"),
    path("officer/", officer_list, name="officer_list"),
    path("officer/partners", ov.partner_board, name="partner_board"),
    path("officer/polls", ov.poll_list, name="poll_list"),
    path("officer/map", ov.heat_map, name="heat_map"),
    path("officer/map.json", ov.heat_map_data, name="heat_map_data"),
    path("officer/polls/<int:poll_id>/send", ov.poll_send, name="poll_send"),
    path("officer/case/<str:code>/", ov.case_detail, name="case_detail"),
    path("officer/case/<str:code>/ack", ov.case_ack, name="case_ack"),
    path("officer/case/<str:code>/reply", ov.case_reply, name="case_reply"),
    path("officer/case/<str:code>/refer", ov.case_refer, name="case_refer"),
    path("officer/case/<str:code>/status", ov.case_status, name="case_status"),
    path("officer/case/<str:code>/close", ov.case_close, name="case_close"),
    path("officer/case/<str:code>/reassign", ov.case_reassign, name="case_reassign"),
    path("api/referrals/<int:referral_id>/ack", referral_ack, name="referral_ack"),
    path("login/", auth_views.LoginView.as_view(template_name="dashboard/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
