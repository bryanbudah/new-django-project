from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer

class ConversationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows conversations to be viewed or created.
    """
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return conversations where the current user is either sender or receiver
        """
        return self.queryset.filter(participants=self.request.user)

    def perform_create(self, serializer):
        """
        Automatically add the current user as a participant when creating a conversation
        """
        conversation = serializer.save()
        conversation.participants.add(self.request.user)

    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        """
        Add a participant to an existing conversation
        """
        conversation = self.get_object()
        user = request.data.get('user_id')
        if not user:
            return Response({'error': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        conversation.participants.add(user)
        return Response({'status': 'participant added'}, status=status.HTTP_200_OK)


class MessageViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows messages to be viewed or created.
    """
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return messages for a specific conversation if conversation_id is provided,
        otherwise return all messages for conversations involving the current user.
        """
        queryset = self.queryset
        conversation_id = self.request.query_params.get('conversation_id', None)
        
        if conversation_id is not None:
            conversation = get_object_or_404(Conversation, id=conversation_id)
            if self.request.user not in conversation.participants.all():
                return queryset.none()
            return queryset.filter(conversation=conversation)
        
        # Filter messages for conversations where user is a participant
        user_conversations = Conversation.objects.filter(participants=self.request.user)
        return queryset.filter(conversation__in=user_conversations)

    def perform_create(self, serializer):
        """
        Automatically set the sender to the current user and validate
        that they are a participant in the conversation.
        """
        conversation = serializer.validated_data['conversation']
        if self.request.user not in conversation.participants.all():
            raise serializers.ValidationError("You are not a participant in this conversation.")
        serializer.save(sender=self.request.user)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Get recent messages across all conversations for the current user.
        """
        user_conversations = Conversation.objects.filter(participants=request.user)
        recent_messages = self.get_queryset().filter(
            conversation__in=user_conversations
        ).order_by('-timestamp')[:10]
        serializer = self.get_serializer(recent_messages, many=True)
        return Response(serializer.data)
