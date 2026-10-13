# chat/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Chat privado
    re_path(r'ws/chat/(?P<user_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
    # Chat global
    re_path(r'ws/chat/$', consumers.ChatConsumer.as_asgi()),
    # ✅ Chat por materia
    re_path(r'ws/subject-chat/(?P<subject_id>\d+)/$', consumers.SubjectChatConsumer.as_asgi()),
]