"""
Serializers for the Reconciliation API.
"""
from rest_framework import serializers
from .models import RawEvent, StudentState, AuditLog


class EventIngestSerializer(serializers.Serializer):
    source = serializers.CharField(max_length=20)
    userId = serializers.CharField(max_length=100, allow_blank=True, allow_null=True, required=False)
    eventType = serializers.CharField(max_length=30)
    timestamp = serializers.CharField()
    details = serializers.JSONField(required=False, default=dict)


class RawEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawEvent
        fields = '__all__'


class StudentStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentState
        fields = '__all__'


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'
