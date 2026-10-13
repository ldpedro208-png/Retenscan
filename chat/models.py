# chat/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from core.models import CatalogoMateria


class ChatMessage(models.Model):
    """Mensaje privado entre dos usuarios"""
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['sender', 'receiver', 'timestamp']),
            models.Index(fields=['receiver', 'is_read']),
        ]

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}: {self.message[:50]}"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    @classmethod
    def get_conversation(cls, user1, user2, limit=50):
        """Obtener la conversación entre dos usuarios en orden cronológico"""
        messages = cls.objects.filter(
            Q(sender=user1, receiver=user2) |
            Q(sender=user2, receiver=user1)
        ).order_by('timestamp')

        if messages.count() > limit:
            messages = messages[messages.count() - limit:]

        return messages

    @classmethod
    def get_unread_count_for_user(cls, user):
        """Contar mensajes no leídos para un usuario"""
        return cls.objects.filter(receiver=user, is_read=False).count()


class ChatRoom(models.Model):
    """Sala de chat grupal"""
    name = models.CharField(max_length=100, unique=True)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='chat_rooms'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_rooms'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_private = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def participant_count(self):
        return self.participants.count()


class ChatRoomMessage(models.Model):
    """Mensajes en salas grupales"""
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='room_messages'
    )
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender.username} en {self.room.name}: {self.message[:50]}"


class SubjectChatRoom(models.Model):
    """
    Sala de chat por materia.
    ✅ Ahora usa CatalogoMateria (única fuente de verdad).
    """
    materia = models.ForeignKey(
        CatalogoMateria,
        on_delete=models.CASCADE,
        related_name='chat_rooms'
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_subject_chats'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='subject_chats',
        blank=True
    )

    class Meta:
        ordering = ['materia__nombre']
        verbose_name = 'Sala de Chat por Materia'
        verbose_name_plural = 'Salas de Chat por Materia'
        indexes = [
            models.Index(fields=['materia', 'is_active']),
        ]

    def __str__(self):
        return f"{self.materia.nombre} - {self.name}"

    def get_participant_count(self):
        return self.participants.count()

    def get_recent_messages(self, limit=50):
        return self.subject_messages.all().order_by('-timestamp')[:limit]

    # ✅ NUEVO: Universidad de la sala (a través de la materia → carrera → universidad)
    @property
    def idUniversidad(self):
        """Universidad a la que pertenece esta sala (vía la materia)."""
        if self.materia and self.materia.idCarrera:
            return self.materia.idCarrera.idUniversidad
        return None


class SubjectChatMessage(models.Model):
    """Mensajes en el chat por materia"""
    room = models.ForeignKey(
        SubjectChatRoom,
        on_delete=models.CASCADE,
        related_name='subject_messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subject_chat_messages'
    )
    message = models.TextField()
    is_announcement = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    file_attachment = models.FileField(
        upload_to='subject_chat_files/%Y/%m/%d/',
        null=True,
        blank=True
    )
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='read_subject_messages',
        blank=True
    )

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['room', 'timestamp']),
            models.Index(fields=['sender', 'timestamp']),
            models.Index(fields=['is_announcement']),
        ]

    def __str__(self):
        return f"{self.sender.username} en {self.room.name}: {self.message[:50]}"

    def mark_as_read(self, user):
        if not self.read_by.filter(id=user.id).exists():
            self.read_by.add(user)

    def is_read_by(self, user):
        return self.read_by.filter(id=user.id).exists()


class SubjectChatInvitation(models.Model):
    """Invitación a un chat por materia"""
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptada'),
        ('rejected', 'Rechazada'),
    ]

    room = models.ForeignKey(
        SubjectChatRoom,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subject_chat_invitations'
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_subject_invitations'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.invited_by.username} invitó a {self.invited_user.username} a {self.room.name}"