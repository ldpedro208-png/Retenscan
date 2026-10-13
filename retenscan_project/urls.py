# retenscan_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ============================================
    # ADMIN DE DJANGO
    # ============================================
    path('admin/', admin.site.urls),

    # ============================================
    # AUTENTICACIÓN (login/logout personalizados)
    # ============================================
    path('login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    # ============================================
    # APP PRINCIPAL (core)
    # ============================================
    path('', include('core.urls')),

    # ============================================
    # API DE CHAT (Django REST Framework)
    # ============================================
    path('api/chat/', include('chat.urls')),
]

# ============================================
# ARCHIVOS ESTÁTICOS Y MEDIA (solo en DEBUG)
# ============================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)