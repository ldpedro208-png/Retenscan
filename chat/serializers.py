# chat/serializers.py

from rest_framework import serializers

from .models import (
    SubjectChatRoom,
    SubjectChatMessage,
    ChatMessage,
    ChatRoom,
    ChatRoomMessage
)
from core.models import Usuario, CatalogoMateria, MateriaProfesor


# ============================================
# USUARIO
# ============================================
class UsuarioSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'rol']


# ============================================
# CHAT PRIVADO
# ============================================
class ChatMessageSerializer(serializers.ModelSerializer):
    sender = UsuarioSimpleSerializer(read_only=True)
    receiver = UsuarioSimpleSerializer(read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            'id', 'sender', 'receiver',
            'message', 'timestamp', 'is_read', 'read_at'
        ]
        read_only_fields = ['id', 'timestamp', 'is_read', 'read_at']


class ChatRoomSerializer(serializers.ModelSerializer):
    participants = UsuarioSimpleSerializer(many=True, read_only=True)
    participant_ids = serializers.PrimaryKeyRelatedField(
        source='participants',
        queryset=Usuario.objects.all(),
        many=True,
        write_only=True
    )
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            'id', 'name', 'participants', 'participant_ids',
            'created_by', 'created_at', 'is_private', 'last_message'
        ]

    def get_last_message(self, obj):
        last_msg = obj.messages.first()
        if last_msg:
            return {
                'message': last_msg.message,
                'sender': last_msg.sender.username,
                'timestamp': last_msg.timestamp,
            }
        return None


class ChatRoomMessageSerializer(serializers.ModelSerializer):
    sender = UsuarioSimpleSerializer(read_only=True)
    sender_id = serializers.PrimaryKeyRelatedField(
        source='sender',
        queryset=Usuario.objects.all(),
        write_only=True
    )

    class Meta:
        model = ChatRoomMessage
        fields = [
            'id', 'room', 'sender', 'sender_id',
            'message', 'timestamp', 'is_read'
        ]
        read_only_fields = ['id', 'timestamp']


# ============================================
# CHAT POR MATERIA
# ============================================
class SubjectChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    sender_role = serializers.SerializerMethodField()
    is_read_by_me = serializers.SerializerMethodField()

    class Meta:
        model = SubjectChatMessage
        fields = [
            'id', 'message', 'sender', 'sender_name', 'sender_role',
            'timestamp', 'is_announcement', 'is_pinned',
            'file_attachment', 'file_name', 'is_read_by_me'
        ]
        read_only_fields = ['id', 'timestamp', 'sender']

    def get_sender_role(self, obj):
        if MateriaProfesor.objects.filter(
            materia_id=obj.room.materia_id,
            usuario_id=obj.sender_id
        ).exists():
            return 'teacher'
        return 'student'

    def get_is_read_by_me(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.is_read_by(request.user)
        return False


class SubjectChatRoomSerializer(serializers.ModelSerializer):
    materia_name = serializers.CharField(source='materia.nombre', read_only=True)
    materia_code = serializers.CharField(source='materia.codigo', read_only=True)
    participant_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = SubjectChatRoom
        fields = [
            'id', 'materia', 'materia_name', 'materia_code',
            'name', 'code', 'is_active', 'created_by',
            'created_at', 'participant_count', 'last_message',
            'unread_count'
        ]

    def get_participant_count(self, obj):
        return obj.participants.count()

    def get_last_message(self, obj):
        last_msg = obj.subject_messages.order_by('-timestamp').first()
        if last_msg:
            return {
                'message': last_msg.message[:100],
                'sender': last_msg.sender.username,
                'timestamp': last_msg.timestamp.isoformat(),
                'is_announcement': last_msg.is_announcement,
            }
        return None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.subject_messages.exclude(read_by=request.user).count()
        return 0