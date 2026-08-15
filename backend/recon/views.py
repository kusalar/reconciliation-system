"""
API Views for the Reconciliation System.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import StudentState, AuditLog, RawEvent
from .serializers import (
    EventIngestSerializer, StudentStateSerializer,
    AuditLogSerializer, RawEventSerializer
)
from .engine import ReconciliationEngine, ReplayEngine
from .ai_model import compute_risk_score


engine = ReconciliationEngine()
replay_engine = ReplayEngine()


class EventIngestView(APIView):
    """
    POST /api/events/
    Accepts a behavioral event payload and runs the reconciliation engine.
    """
    def post(self, request):
        serializer = EventIngestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        result = engine.ingest(request.data)

        http_status = status.HTTP_200_OK
        if result.get('status') == 'rejected':
            http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
        elif result.get('status') == 'duplicate':
            http_status = status.HTTP_200_OK

        return Response(result, status=http_status)


class StudentTimelineView(APIView):
    """
    GET /api/students/<user_id>/timeline/
    Returns the full versioned state history for a student.
    """
    def get(self, request, user_id):
        states = StudentState.objects.filter(user_id=user_id).order_by('version')
        if not states.exists():
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(StudentStateSerializer(states, many=True).data)


class StudentCurrentStateView(APIView):
    """
    GET /api/students/<user_id>/state/
    Returns only the latest reconciled state.
    """
    def get(self, request, user_id):
        state = StudentState.objects.filter(user_id=user_id).order_by('-version').first()
        if not state:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(StudentStateSerializer(state).data)


class StudentAuditView(APIView):
    """
    GET /api/students/<user_id>/audit/
    Returns the full audit trail for a student.
    """
    def get(self, request, user_id):
        logs = AuditLog.objects.filter(user_id=user_id).order_by('timestamp')
        return Response(AuditLogSerializer(logs, many=True).data)


class StudentRiskView(APIView):
    """
    GET /api/students/<user_id>/risk/
    Runs the AI model on the current reconciled state and returns a risk score.
    """
    def get(self, request, user_id):
        state = StudentState.objects.filter(user_id=user_id).order_by('-version').first()
        if not state:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

        state_dict = StudentStateSerializer(state).data
        risk = compute_risk_score(state_dict)
        return Response({
            'user_id': user_id,
            'state_version': state.version,
            **risk,
        })


class ReplayView(APIView):
    """
    POST /api/replay/
    Body: {"userId": "..."} or {} for full replay.
    Replays all raw events for a user (or all users) and rebuilds state.
    """
    def post(self, request):
        user_id = request.data.get('userId') or request.data.get('user_id')
        result = replay_engine.replay(user_id=user_id or None)
        return Response(result)


class AllStudentsView(APIView):
    """
    GET /api/students/
    Returns the latest state + risk score for all students.
    """
    def get(self, request):
        # Get latest version per user
        from django.db.models import Max
        user_max = StudentState.objects.values('user_id').annotate(max_version=Max('version'))
        results = []
        for um in user_max:
            state = StudentState.objects.filter(
                user_id=um['user_id'], version=um['max_version']
            ).first()
            if state:
                state_dict = StudentStateSerializer(state).data
                risk = compute_risk_score(state_dict)
                results.append({
                    'user_id': um['user_id'],
                    'state_version': state.version,
                    'state': state_dict,
                    'risk': risk,
                })
        return Response(results)


class RawEventsView(APIView):
    """
    GET /api/events/?userId=<user_id>
    Returns raw events, optionally filtered by userId.
    """
    def get(self, request):
        user_id = request.query_params.get('userId') or request.query_params.get('user_id')
        qs = RawEvent.objects.all().order_by('event_timestamp')
        if user_id:
            qs = qs.filter(user_id=user_id)
        return Response(RawEventSerializer(qs, many=True).data)


class AllAuditView(APIView):
    """
    GET /api/audit/
    Returns all audit log entries.
    """
    def get(self, request):
        logs = AuditLog.objects.all().order_by('timestamp')
        return Response(AuditLogSerializer(logs, many=True).data)
