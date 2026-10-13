# chat/consumers.py

import json
import logging
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.db import models

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

logger = logging.getLogger(__name__)
Usuario = get_user_model()


# ============================================
# CONSUMER: CHAT PRIVADO
# ============================================
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']

        logger.info(
            f"🔌 WebSocket connect attempt by user: "
            f"{self.user.username if self.user.is_authenticated else 'Anonymous'}"
        )

        if not self.user.is_authenticated:
            logger.warning("❌ WebSocket rejected: User not authenticated")
            await self.close()
            return

        self.other_user_id = self.scope['url_route']['kwargs'].get('user_id')

        if self.other_user_id:
            user_ids = sorted([self.user.id, int(self.other_user_id)])
            self.room_name = f'private_{user_ids[0]}_{user_ids[1]}'
        else:
            self.room_name = 'global'

        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"✅ WebSocket connected: {self.room_group_name} by {self.user.username}")

        if self.other_user_id:
            await self.send_private_history()

    async def disconnect(self, close_code):
        logger.info(f"⚠️ WebSocket disconnected: {self.room_group_name} - code: {close_code}")
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            logger.debug(f"📨 RECV [{message_type}] from {self.user.username}: {data}")

            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                }))
                return

            if message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'read':
                await self.handle_read(data)
            else:
                logger.warning(f"⚠️ Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON received: {e}")
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")

    async def handle_message(self, data):
        message = data.get('message', '').strip()
        receiver_id = data.get('receiver_id')

        if not message:
            logger.warning("⚠️ Empty message received")
            return

        if receiver_id:
            try:
                await self.save_private_message(message, receiver_id)
                logger.info(f"💬 Private message saved: {self.user.username} -> user {receiver_id}")
            except Exception as e:
                logger.error(f"❌ Error saving private message: {e}")
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender': self.user.username,
                    'sender_id': self.user.id,
                    'receiver_id': int(receiver_id),
                    'timestamp': datetime.now().isoformat(),
                    'is_private': True
                }
            )
        else:
            try:
                await self.save_room_message(message)
                logger.info(f"💬 Room message saved: {self.user.username} in {self.room_name}")
            except Exception as e:
                logger.error(f"❌ Error saving room message: {e}")
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender': self.user.username,
                    'sender_id': self.user.id,
                    'timestamp': datetime.now().isoformat(),
                    'is_private': False
                }
            )

    async def handle_typing(self, data):
        receiver_id = data.get('receiver_id')
        is_typing = data.get('is_typing', True)

        logger.debug(f"⌨️ [SERVER] TYPING: user={self.user.username} (id={self.user.id}) "
                     f"is_typing={is_typing} receiver_id={receiver_id}")

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'sender': self.user.username,
                'sender_id': self.user.id,
                'is_typing': is_typing,
                'receiver_id': receiver_id
            }
        )

    async def handle_read(self, data):
        message_ids = data.get('message_ids', [])
        try:
            count = await self.mark_messages_read(message_ids)
            logger.info(f"📖 Marked {count} messages as read for {self.user.username}")
        except Exception as e:
            logger.error(f"❌ Error marking messages as read: {e}")

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'sender': event['sender'],
            'sender_id': event['sender_id'],
            'receiver_id': event.get('receiver_id'),
            'timestamp': event['timestamp'],
            'is_private': event.get('is_private', False)
        }))

    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'sender': event['sender'],
            'sender_id': event.get('sender_id'),
            'is_typing': event['is_typing'],
            'receiver_id': event.get('receiver_id')
        }))

    async def send_private_history(self):
        try:
            messages = await self.get_private_messages(int(self.other_user_id))
            await self.send(text_data=json.dumps({
                'type': 'history',
                'messages': messages
            }))
            logger.info(f"📜 Sent private history for {self.user.username} with user {self.other_user_id}")
        except Exception as e:
            logger.error(f"❌ Error sending private history: {e}")

    @database_sync_to_async
    def save_private_message(self, message, receiver_id):
        receiver = Usuario.objects.get(id=receiver_id)
        return ChatMessage.objects.create(
            sender=self.user,
            receiver=receiver,
            message=message
        )

    @database_sync_to_async
    def save_room_message(self, message):
        room, created = ChatRoom.objects.get_or_create(
            name=self.room_name,
            defaults={
                'created_by': self.user,
                'is_private': True if self.other_user_id else False
            }
        )
        return ChatRoomMessage.objects.create(
            room=room,
            sender=self.user,
            message=message
        )

    @database_sync_to_async
    def get_private_messages(self, other_user_id, limit=50):
        other_user = Usuario.objects.get(id=other_user_id)
        messages = ChatMessage.objects.filter(
            models.Q(sender=self.user, receiver=other_user) |
            models.Q(sender=other_user, receiver=self.user)
        ).order_by('-timestamp')[:limit]

        return [
            {
                'message': msg.message,
                'sender': msg.sender.username,
                'sender_id': msg.sender.id,
                'timestamp': msg.timestamp.isoformat(),
                'is_read': msg.is_read
            }
            for msg in reversed(messages)
        ]

    @database_sync_to_async
    def mark_messages_read(self, message_ids):
        if message_ids:
            return ChatMessage.objects.filter(id__in=message_ids).update(is_read=True)
        return ChatMessage.objects.filter(receiver=self.user, is_read=False).update(is_read=True)


# ============================================
# CONSUMER: CHAT POR MATERIA
# ============================================
class SubjectChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.subject_id = self.scope['url_route']['kwargs'].get('subject_id')
        self.room_name = f'subject_{self.subject_id}'
        self.room_group_name = f'chat_{self.room_name}'

        logger.info(f"🔌 SubjectChat connect: user={self.user.username}, subject={self.subject_id}")

        if not self.user.is_authenticated:
            logger.warning("❌ SubjectChat rejected: User not authenticated")
            await self.close()
            return

        if not await self.user_has_access(self.subject_id):
            logger.warning(f"❌ Usuario {self.user.username} no tiene acceso a la materia {self.subject_id}")
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"✅ SubjectChat connected: {self.user.username} to {self.room_group_name}")

        await self.send_chat_history()

    async def disconnect(self, close_code):
        logger.info(f"⚠️ SubjectChat disconnected: {self.room_group_name} - code: {close_code}")
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            logger.debug(f"📨 SubjectChat [{message_type}] from {self.user.username}: {data}")

            if message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
                return

            if message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'announcement':
                await self.handle_announcement(data)
            elif message_type == 'pin':
                await self.handle_pin_message(data)
            else:
                logger.warning(f"⚠️ Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")

    async def handle_message(self, data):
        message = data.get('message', '').strip()
        file_data = data.get('file', None)

        if not message and not file_data:
            return

        message_obj = await self.save_subject_message(message, file_data)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'subject_chat_message',
                'message_id': message_obj.id if message_obj else None,
                'message': message,
                'sender': self.user.username,
                'sender_id': self.user.id,
                'sender_role': await self.get_user_role(),
                'timestamp': datetime.now().isoformat(),
                'is_announcement': False,
                'is_pinned': False,
                'file': file_data,
            }
        )

    async def handle_announcement(self, data):
        if not await self.is_teacher():
            logger.warning(f"⚠️ Usuario {self.user.username} intentó enviar anuncio sin ser profesor")
            return

        message = data.get('message', '').strip()
        if not message:
            return

        message_obj = await self.save_subject_message(message, is_announcement=True)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'subject_chat_message',
                'message_id': message_obj.id,
                'message': message,
                'sender': self.user.username,
                'sender_id': self.user.id,
                'sender_role': 'teacher',
                'timestamp': datetime.now().isoformat(),
                'is_announcement': True,
                'is_pinned': False,
                'file': None,
            }
        )

    async def handle_pin_message(self, data):
        message_id = data.get('message_id')
        action = data.get('action')

        if not await self.is_teacher():
            return

        await self.toggle_pin_message(message_id, action)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'message_pinned',
                'message_id': message_id,
                'action': action,
                'sender': self.user.username,
            }
        )

    async def handle_typing(self, data):
        is_typing = data.get('is_typing', True)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'sender': self.user.username,
                'sender_id': self.user.id,
                'is_typing': is_typing,
                'sender_role': await self.get_user_role(),
            }
        )

    async def subject_chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message_id': event.get('message_id'),
            'message': event['message'],
            'sender': event['sender'],
            'sender_id': event['sender_id'],
            'sender_role': event.get('sender_role', 'student'),
            'timestamp': event['timestamp'],
            'is_announcement': event.get('is_announcement', False),
            'is_pinned': event.get('is_pinned', False),
            'file': event.get('file'),
        }))

    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'sender': event['sender'],
            'sender_id': event['sender_id'],
            'is_typing': event['is_typing'],
            'sender_role': event.get('sender_role', 'student'),
        }))

    async def message_pinned(self, event):
        await self.send(text_data=json.dumps({
            'type': 'pin_update',
            'message_id': event['message_id'],
            'action': event['action'],
            'sender': event['sender'],
        }))

    async def send_chat_history(self):
        messages = await self.get_subject_history()
        pinned_messages = await self.get_pinned_messages()

        await self.send(text_data=json.dumps({
            'type': 'history',
            'messages': messages,
            'pinned_messages': pinned_messages,
        }))

    # ============================================
    # ✅ CORREGIDO: user_has_access
    # ============================================
    @database_sync_to_async
    def user_has_access(self, subject_id):
        """
        Verificar si el usuario tiene acceso a la materia.
        Se corrigieron las rutas de lookup para usar los nombres reales de tu BD:
        - Estudiante.idCarrera (no 'carrera')
        - CatalogoCarrera.materias_catalogo (related_name de CatalogoMateria.idCarrera)
        - Estudiante.tutores_asignados (related_name de UsuarioEstudiantes.estudiante)
        """
        from core.models import Estudiante, CatalogoMateria, MateriaProfesor

        user = self.user

        # ✅ Admin tiene acceso a TODO
        if user.is_superuser or user.is_staff or getattr(user, 'es_admin_universidad', False):
            logger.info(f"👑 Admin {user.username} accede a materia {subject_id}")
            return True

        # ✅ Profesor: materias que imparte
        if MateriaProfesor.objects.filter(
            materia_id=subject_id,
            usuario_id=user.id
        ).exists():
            logger.info(f"👨‍🏫 Profesor {user.username} accede a materia {subject_id}")
            return True

        # ✅ Estudiante: materias de su carrera
        if Estudiante.objects.filter(
            idUsuario_id=user.id,
            idCarrera__materias_catalogo__idMateria=subject_id
        ).exists():
            logger.info(f"🎓 Estudiante {user.username} accede a materia {subject_id}")
            return True

        # ✅ Tutor: materias de las carreras donde tutoriza
        if Estudiante.objects.filter(
            tutores_asignados__usuario_id=user.id,
            idCarrera__materias_catalogo__idMateria=subject_id
        ).exists():
            logger.info(f"🧑‍🏫 Tutor {user.username} accede a materia {subject_id}")
            return True

        logger.warning(f"❌ Usuario {user.username} (rol={user.rol}) NO tiene acceso a materia {subject_id}")
        return False

    # ============================================
    # ✅ CORREGIDO: is_teacher
    # ============================================
    @database_sync_to_async
    def is_teacher(self):
        """Verificar si el usuario es profesor de la materia"""
        from core.models import MateriaProfesor
        return MateriaProfesor.objects.filter(
            materia_id=self.subject_id,
            usuario_id=self.user.id
        ).exists()

    # ============================================
    # ✅ CORREGIDO: get_user_role
    # ============================================
    @database_sync_to_async
    def get_user_role(self):
        """Obtener rol del usuario en la materia"""
        from core.models import MateriaProfesor, Estudiante

        user = self.user

        # Admin
        if user.is_superuser or user.is_staff or getattr(user, 'es_admin_universidad', False):
            return 'admin'

        # Profesor
        if MateriaProfesor.objects.filter(
            materia_id=self.subject_id,
            usuario_id=user.id
        ).exists():
            return 'teacher'

        # Estudiante
        if Estudiante.objects.filter(
            idUsuario_id=user.id,
            idCarrera__materias_catalogo__idMateria=self.subject_id
        ).exists():
            return 'student'

        # Tutor
        if Estudiante.objects.filter(
            tutores_asignados__usuario_id=user.id,
            idCarrera__materias_catalogo__idMateria=self.subject_id
        ).exists():
            return 'tutor'

        return 'viewer'

    @database_sync_to_async
    def save_subject_message(self, message, file_data=None, is_announcement=False):
        try:
            room, created = SubjectChatRoom.objects.get_or_create(
                materia_id=self.subject_id,
                defaults={
                    'name': f"Chat de {self.subject_id}",
                    'code': f"SUBJ-{self.subject_id}",
                    'created_by': self.user,
                }
            )

            room.participants.add(self.user)

            message_obj = SubjectChatMessage.objects.create(
                room=room,
                sender=self.user,
                message=message,
                is_announcement=is_announcement,
            )

            message_obj.read_by.add(self.user)

            return message_obj
        except Exception as e:
            logger.error(f"❌ Error saving subject message: {e}")
            return None

    @database_sync_to_async
    def get_subject_history(self, limit=50):
        try:
            room = SubjectChatRoom.objects.get(materia_id=self.subject_id)
            messages = room.subject_messages.filter(
                is_pinned=False
            ).order_by('-timestamp')[:limit]

            return [
                {
                    'id': msg.id,
                    'message': msg.message,
                    'sender': msg.sender.username,
                    'sender_id': msg.sender.id,
                    'timestamp': msg.timestamp.isoformat(),
                    'is_announcement': msg.is_announcement,
                    'is_pinned': msg.is_pinned,
                    'file': msg.file_attachment.url if msg.file_attachment else None,
                    'is_read_by_me': msg.is_read_by(self.user),
                }
                for msg in reversed(messages)
            ]
        except SubjectChatRoom.DoesNotExist:
            return []

    @database_sync_to_async
    def get_pinned_messages(self):
        try:
            room = SubjectChatRoom.objects.get(materia_id=self.subject_id)
            messages = room.subject_messages.filter(is_pinned=True).order_by('-timestamp')

            return [
                {
                    'id': msg.id,
                    'message': msg.message,
                    'sender': msg.sender.username,
                    'sender_id': msg.sender.id,
                    'timestamp': msg.timestamp.isoformat(),
                    'is_announcement': msg.is_announcement,
                    'is_pinned': True,
                }
                for msg in messages
            ]
        except SubjectChatRoom.DoesNotExist:
            return []

    @database_sync_to_async
    def toggle_pin_message(self, message_id, action):
        try:
            message = SubjectChatMessage.objects.get(id=message_id)
            if action == 'pin':
                message.is_pinned = True
            elif action == 'unpin':
                message.is_pinned = False
            message.save()
            return True
        except SubjectChatMessage.DoesNotExist:
            return False