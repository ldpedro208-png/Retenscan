# chat/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'messages', views.ChatMessageViewSet, basename='chat-messages')
router.register(r'rooms', views.ChatRoomViewSet, basename='chat-rooms')
router.register(r'room-messages', views.ChatRoomMessageViewSet, basename='chat-room-messages')
router.register(r'users', views.UsuarioSearchViewSet, basename='chat-users')
router.register(r'subject-chat', views.SubjectChatViewSet, basename='subject-chat')

urlpatterns = [
    # ✅ Vista HTML del chat por materias
    path('subject-chat-page/', views.subject_chat_view, name='subject_chat'),

    # Rutas de la API REST
    path('', include(router.urls)),
]

# ✅ Debug: imprimir rutas registradas
print("=== CHAT URLs registradas ===")
for url in router.urls:
    print(f"  {url}")