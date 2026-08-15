from django.urls import path
from . import views

urlpatterns = [
    # Event ingestion
    path('events/', views.EventIngestView.as_view(), name='event-ingest'),
    path('events/raw/', views.RawEventsView.as_view(), name='raw-events'),

    # Student endpoints
    path('students/', views.AllStudentsView.as_view(), name='all-students'),
    path('students/<str:user_id>/state/', views.StudentCurrentStateView.as_view(), name='student-state'),
    path('students/<str:user_id>/timeline/', views.StudentTimelineView.as_view(), name='student-timeline'),
    path('students/<str:user_id>/audit/', views.StudentAuditView.as_view(), name='student-audit'),
    path('students/<str:user_id>/risk/', views.StudentRiskView.as_view(), name='student-risk'),

    # Replay
    path('replay/', views.ReplayView.as_view(), name='replay'),

    # Global audit
    path('audit/', views.AllAuditView.as_view(), name='all-audit'),
]
