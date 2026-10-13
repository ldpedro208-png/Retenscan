# chat/admin.py
from django.contrib import admin
from .models import ChatMessage, ChatRoom, ChatRoomMessage

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'receiver', 'message', 'timestamp', 'is_read']  # ← Cambiar user por sender/receiver
    list_filter = ['is_read', 'timestamp']
    search_fields = ['sender__username', 'receiver__username', 'message']
    readonly_fields = ['timestamp']
    list_select_related = ['sender', 'receiver']  # ← Optimizar consultas
    
    fieldsets = (
        ('Información del Mensaje', {
            'fields': ('sender', 'receiver', 'message')
        }),
        ('Estado', {
            'fields': ('is_read', 'read_at', 'timestamp')
        }),
    )

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'created_at', 'is_private', 'participant_count']
    filter_horizontal = ['participants']
    search_fields = ['name', 'created_by__username']
    readonly_fields = ['created_at']
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participantes'

@admin.register(ChatRoomMessage)
class ChatRoomMessageAdmin(admin.ModelAdmin):
    list_display = ['room', 'sender', 'message', 'timestamp', 'is_read']  # ← Cambiar user por sender
    list_filter = ['room', 'is_read', 'timestamp']
    search_fields = ['sender__username', 'message']
    list_select_related = ['room', 'sender']
    
    fieldsets = (
        ('Información del Mensaje', {
            'fields': ('room', 'sender', 'message')
        }),
        ('Estado', {
            'fields': ('is_read', 'timestamp')
        }),
    )