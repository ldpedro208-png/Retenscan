# chat/views.py

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.models import (
    CatalogoMateria,
    Estudiante,
    MateriaProfesor,
    Profesor,
    Usuario
)

from .models import (
    SubjectChatRoom,
    SubjectChatMessage,
    ChatMessage,
    ChatRoom,
    ChatRoomMessage
)
from .serializers import (
    SubjectChatRoomSerializer,
    SubjectChatMessageSerializer,
    ChatMessageSerializer,
    ChatRoomSerializer,
    ChatRoomMessageSerializer,
    UsuarioSimpleSerializer
)

Usuario = get_user_model()


# ============================================
# HELPER: universidad del usuario
# ============================================

def _get_universidad_id(user):
    """Obtiene el ID de universidad del usuario (None si es superuser)."""
    if user.is_superuser:
        return None
    return getattr(user, 'idUniversidad_id', None)


# ============================================
# VIEWSET: MENSAJES PRIVADOS
# ============================================
class ChatMessageViewSet(viewsets.ModelViewSet):
    """ViewSet para mensajes privados"""
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return ChatMessage.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).select_related('sender', 'receiver').order_by('-timestamp')

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

    # ============================================
    # GET /api/chat/messages/conversations/
    # ============================================
    @action(detail=False, methods=['get'],
            url_path='conversations', url_name='conversations')
    def conversations(self, request):
        """Lista de conversaciones del usuario"""
        user = request.user

        user_ids = set()
        convs = ChatMessage.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).values_list('sender_id', 'receiver_id')

        for sender_id, receiver_id in convs:
            if sender_id != user.id:
                user_ids.add(sender_id)
            if receiver_id != user.id:
                user_ids.add(receiver_id)

        result = []
        for other_user in Usuario.objects.filter(id__in=user_ids):
            last_message = ChatMessage.objects.filter(
                Q(sender=user, receiver=other_user) |
                Q(sender=other_user, receiver=user)
            ).order_by('-timestamp').first()

            unread_count = ChatMessage.objects.filter(
                sender=other_user,
                receiver=user,
                is_read=False
            ).count()

            result.append({
                'user': UsuarioSimpleSerializer(other_user).data,
                'last_message': {
                    'message': last_message.message if last_message else None,
                    'timestamp': last_message.timestamp.isoformat() if last_message else None,
                    'sender': last_message.sender.username if last_message else None,
                    'sender_id': last_message.sender.id if last_message else None,
                },
                'unread_count': unread_count,
            })

        result.sort(key=lambda x: x['last_message']['timestamp'] or '', reverse=True)
        return Response(result)

    # ============================================
    # GET /api/chat/messages/unread_count/
    # ============================================
    @action(detail=False, methods=['get'],
            url_path='unread_count', url_name='unread_count')
    def unread_count(self, request):
        """Contar mensajes no leídos"""
        count = ChatMessage.objects.filter(
            receiver=request.user,
            is_read=False
        ).count()
        return Response({'unread_count': count})

    # ============================================
    # GET /api/chat/messages/conversation/<user_id>/
    # ============================================
    @action(detail=False, methods=['get'],
            url_path=r'conversation/(?P<user_id>\d+)',
            url_name='conversation')
    def conversation(self, request, user_id=None):
        """Obtener la conversación con un usuario específico."""
        user = request.user

        try:
            other_user = Usuario.objects.get(id=user_id)
        except Usuario.DoesNotExist:
            return Response(
                {'error': 'Usuario no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        messages = ChatMessage.objects.filter(
            Q(sender=user, receiver=other_user) |
            Q(sender=other_user, receiver=user)
        ).select_related('sender', 'receiver').order_by('timestamp')[:50]

        updated = ChatMessage.objects.filter(
            sender=other_user,
            receiver=user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())

        serializer = self.get_serializer(messages, many=True)

        return Response({
            'user': UsuarioSimpleSerializer(other_user).data,
            'messages': serializer.data,
            'marked_read_count': updated,
        })

    # ============================================
    # POST /api/chat/messages/mark_all_read/
    # ============================================
    @action(detail=False, methods=['post'],
            url_path='mark_all_read', url_name='mark_all_read')
    def mark_all_read(self, request):
        """Marcar todos los mensajes como leídos"""
        updated = ChatMessage.objects.filter(
            receiver=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({'status': f'{updated} messages marked as read'})

    # ============================================
    # GET /api/chat/messages/my_subjects/
    # ✅ AHORA CON FILTRO POR UNIVERSIDAD
    # ============================================
    @action(detail=False, methods=['get'],
            url_path='my_subjects', url_name='my_subjects')
    def my_subjects(self, request):
        """
        Devuelve las materias/canales a los que el usuario tiene acceso.
        ✅ Filtra por universidad (multi-tenant).
        """
        user = request.user
        universidad_id = _get_universidad_id(user)

        # ✅ Base queryset con filtro por universidad
        if user.is_superuser:
            materias_base = CatalogoMateria.objects.all()
        elif universidad_id:
            materias_base = CatalogoMateria.objects.filter(
                idCarrera__idUniversidad_id=universidad_id
            )
        else:
            materias_base = CatalogoMateria.objects.none()

        # ✅ Admin de universidad: todas las materias de SU universidad
        if user.is_superuser or user.is_staff or getattr(user, 'es_admin_universidad', False):
            materias = materias_base
        else:
            materias = CatalogoMateria.objects.none()

            # ✅ Profesor: materias que imparte (solo de su universidad)
            if user.rol == 'profesor':
                materias = materias | materias_base.filter(
                    profesores_asignados__usuario_id=user.id
                )

            # ✅ Tutor: materias de las carreras donde tutoriza
            if user.rol == 'tutor':
                materias = materias | materias_base.filter(
                    idCarrera__estudiantes__tutores_asignados__usuario_id=user.id
                )

            # ✅ Estudiante: materias de su carrera
            if user.rol == 'estudiante':
                materias = materias | materias_base.filter(
                    idCarrera__estudiantes__idUsuario_id=user.id
                )

        materias = materias.select_related('idCarrera', 'idCarrera__idUniversidad').distinct().order_by('nombre')

        result = []
        for m in materias:
            room = SubjectChatRoom.objects.filter(materia=m, is_active=True).first()
            unread = 0
            if room:
                unread = room.subject_messages.exclude(read_by=user).count()

            result.append({
                'id': m.idMateria,
                'nombre': m.nombre,
                'codigo': m.codigo or '',
                'carrera': m.idCarrera.nombre if m.idCarrera else '',
                'universidad': m.idCarrera.idUniversidad.nombre if m.idCarrera and m.idCarrera.idUniversidad else '',
                'chat_exists': bool(room),
                'unread_count': unread,
            })

        return Response({
            'count': len(result),
            'subjects': result,
        })


# ============================================
# VIEWSET: SALAS DE CHAT
# ============================================
class ChatRoomViewSet(viewsets.ModelViewSet):
    """ViewSet para salas de chat"""
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatRoom.objects.filter(participants=self.request.user)

    def perform_create(self, serializer):
        room = serializer.save(created_by=self.request.user)
        room.participants.add(self.request.user)

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        room = self.get_object()
        room.participants.add(request.user)
        return Response({'status': 'joined successfully'})

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        room = self.get_object()
        room.participants.remove(request.user)
        return Response({'status': 'left successfully'})


# ============================================
# VIEWSET: MENSAJES DE SALA
# ============================================
class ChatRoomMessageViewSet(viewsets.ModelViewSet):
    """ViewSet para mensajes en salas grupales"""
    serializer_class = ChatRoomMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        room_id = self.kwargs.get('room_pk')
        if room_id:
            return ChatRoomMessage.objects.filter(
                room_id=room_id,
                room__participants=self.request.user
            )
        return ChatRoomMessage.objects.none()

    def perform_create(self, serializer):
        room_id = self.kwargs.get('room_pk')
        room = ChatRoom.objects.get(id=room_id)
        serializer.save(sender=self.request.user, room=room)


# ============================================
# VIEWSET: BÚSQUEDA DE USUARIOS
# ✅ AHORA CON FILTRO POR UNIVERSIDAD
# ============================================
class UsuarioSearchViewSet(viewsets.ReadOnlyModelViewSet):
    """Vista para buscar usuarios (para el chat)"""
    serializer_class = UsuarioSimpleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        universidad_id = _get_universidad_id(user)

        queryset = Usuario.objects.all().exclude(id=user.id)

        # ✅ Filtrar por universidad (excepto superuser)
        if not user.is_superuser and universidad_id:
            queryset = queryset.filter(idUniversidad_id=universidad_id)

        search = self.request.query_params.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        return queryset[:20]


# ============================================
# VIEWSET: CHAT POR MATERIA
# ✅ CORREGIDO: usa materias_catalogo (nuevo related_name)
# ✅ AHORA CON FILTRO POR UNIVERSIDAD
# ============================================
class SubjectChatViewSet(viewsets.ModelViewSet):
    """ViewSet para chats por materia"""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        universidad_id = _get_universidad_id(user)

        # ✅ Base: filtrar por universidad (excepto superuser)
        base = SubjectChatRoom.objects.filter(is_active=True)
        if not user.is_superuser and universidad_id:
            base = base.filter(materia__idCarrera__idUniversidad_id=universidad_id)

        # ✅ Admin ve todos los canales de su universidad
        if user.is_superuser or user.is_staff or getattr(user, 'es_admin_universidad', False):
            return base.select_related(
                'materia', 'materia__idCarrera', 'created_by'
            )

        # ✅ Materias donde el usuario es profesor
        professor_materias = MateriaProfesor.objects.filter(
            usuario_id=user.id
        ).values_list('materia_id', flat=True)

        # ✅ CORREGIDO: usar 'materias_catalogo' (nuevo related_name)
        # El related_name de CatalogoMateria.idCarrera es 'materias_catalogo'
        # así que desde Estudiante: estudiante.idCarrera.materias_catalogo.all()
        # En queries reversas: idCarrera__materias_catalogo__id
        student_materias = Estudiante.objects.filter(
            idUsuario_id=user.id
        ).values_list('idCarrera__materias_catalogo__id', flat=True)

        # ✅ Tutor: materias de los estudiantes que tutoriza
        tutor_materias = Estudiante.objects.filter(
            tutores_asignados__usuario_id=user.id
        ).values_list('idCarrera__materias_catalogo__id', flat=True)

        materias_ids = set(
            list(professor_materias) +
            list(student_materias) +
            list(tutor_materias)
        )

        return base.filter(
            materia_id__in=materias_ids
        ).select_related('materia', 'materia__idCarrera', 'created_by')

    def get_serializer_class(self):
        if self.action == 'messages':
            return SubjectChatMessageSerializer
        return SubjectChatRoomSerializer

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Obtener mensajes de una sala específica"""
        room = self.get_object()
        messages = room.subject_messages.select_related(
            'sender'
        ).prefetch_related('read_by').order_by('timestamp')[:50]
        serializer = SubjectChatMessageSerializer(
            messages, many=True, context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Marcar mensajes como leídos"""
        room = self.get_object()
        message_ids = request.data.get('message_ids', [])

        if message_ids:
            messages = room.subject_messages.filter(id__in=message_ids)
        else:
            messages = room.subject_messages.all()

        for message in messages:
            message.mark_as_read(request.user)

        return Response({'status': 'messages marked as read'})

    @action(detail=True, methods=['post'])
    def pin_message(self, request, pk=None):
        """Fijar un mensaje (solo profesores)"""
        room = self.get_object()
        message_id = request.data.get('message_id')

        if not MateriaProfesor.objects.filter(
            materia_id=room.materia_id,
            usuario_id=request.user.id
        ).exists():
            return Response(
                {'error': 'Solo los profesores pueden fijar mensajes'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            message = room.subject_messages.get(id=message_id)
            message.is_pinned = not message.is_pinned
            message.save()
            return Response({
                'status': 'message pinned' if message.is_pinned else 'message unpinned',
                'is_pinned': message.is_pinned
            })
        except SubjectChatMessage.DoesNotExist:
            return Response(
                {'error': 'Mensaje no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )


@login_required
def subject_chat_view(request):
    """Vista para renderizar la interfaz del chat por materias"""
    context = {
        'is_teacher': (
            request.user.rol == 'profesor' or
            request.user.is_staff or
            request.user.is_superuser
        ),
        'is_tutor': request.user.rol == 'tutor',
    }
    return render(request, 'chat/subject_chat.html', context)