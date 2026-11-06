from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from channels.sim_views import sim_sms, sim_sms_outbox, sim_ussd
from channels.sms import sms_hook
from channels.ussd import ussd_hook
from channels.whatsapp import whatsapp_hook
from channels.views import channel_api
from channels.proof_views import proof_upload
from channels.status_views import case_status
from channels.voice_views import voice_note, voice_shortcut, voice_transcribe
from dashboard import officer_views as ov
from dashboard import pwa_views
from kb import views as kb_views
from dashboard.views import (app_config, chat_page, feature_status, metrics_page, officer_list, spa_page,
                             status_page, web_asset)
from partners_mock.views import referral_ack

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/channel/<str:name>", channel_api, name="channel_api"),
    path("api/config", app_config, name="app_config"),
    path("hooks/sms", sms_hook, name="sms_hook"),
    path("hooks/ussd", ussd_hook, name="ussd_hook"),
    path("hooks/whatsapp", whatsapp_hook, name="whatsapp_hook"),
    path("sim/sms", sim_sms, name="sim_sms"),
    path("sim/sms/outbox", sim_sms_outbox, name="sim_sms_outbox"),
    path("sim/ussd", sim_ussd, name="sim_ussd"),
    path("chat", chat_page, name="chat"),
    path("", spa_page, name="home"),
    path("age", spa_page, name="age"),
    path("language", spa_page, name="language"),
    path("report", spa_page, name="report"),
    path("confirmation", spa_page, name="confirmation"),
    path("status", spa_page, name="status_lookup"),
    path("help", spa_page, name="help"),
    path("kb", kb_views.kb_list, name="kb_list"),
    path("kb/<slug:slug>", kb_views.kb_article, name="kb_article"),
    path("manifest.webmanifest", pwa_views.manifest, name="manifest"),
    path("sw.js", pwa_views.service_worker, name="service_worker"),
    path("share", pwa_views.share, name="share"),
    path("r", pwa_views.report_link, name="report_link"),
    path("mock/social", pwa_views.mock_social, name="mock_social"),
    path("metrics", metrics_page, name="metrics"),
    path("about/status", feature_status, name="feature_status"),
    path("voice", voice_shortcut, name="voice"),
    path("api/voice/transcribe", voice_transcribe, name="voice_transcribe"),
    path("api/voice-note", voice_note, name="voice_note"),
    path("api/proof", proof_upload, name="proof_upload"),
    path("api/case-status", case_status, name="case_status_api"),
    path("status/<str:code>", status_page, name="status"),
    path("officer/", officer_list, name="officer_list"),
    path("officer/partners", ov.partner_board, name="partner_board"),
    path("officer/polls", ov.poll_list, name="poll_list"),
    path("officer/map", ov.heat_map, name="heat_map"),
    path("officer/calls", ov.call_list, name="call_list"),
    path("officer/calls/start", ov.call_start, name="call_start"),
    path("officer/calls/<int:session_id>/", ov.call_detail, name="call_detail"),
    path("officer/calls/<int:session_id>.json", ov.call_data, name="call_data"),
    path("officer/map.json", ov.heat_map_data, name="heat_map_data"),
    path("officer/polls/<int:poll_id>/send", ov.poll_send, name="poll_send"),
    path("officer/case/<str:code>/", ov.case_detail, name="case_detail"),
    path("officer/case/<str:code>/voice/<int:evidence_id>", ov.case_voice, name="case_voice"),
    path("officer/case/<str:code>/proof/<int:evidence_id>", ov.case_proof, name="case_proof"),
    path("officer/case/<str:code>/ack", ov.case_ack, name="case_ack"),
    path("officer/case/<str:code>/reply", ov.case_reply, name="case_reply"),
    path("officer/case/<str:code>/refer", ov.case_refer, name="case_refer"),
    path("officer/case/<str:code>/status", ov.case_status, name="case_status"),
    path("officer/case/<str:code>/close", ov.case_close, name="case_close"),
    path("officer/case/<str:code>/reassign", ov.case_reassign, name="case_reassign"),
    path("api/referrals/<int:referral_id>/ack", referral_ack, name="referral_ack"),
    path("login/", auth_views.LoginView.as_view(template_name="dashboard/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("assets/<path:path>", web_asset, name="web_asset"),
]
