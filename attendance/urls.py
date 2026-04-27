from django.urls import path
from . import views

urlpatterns = [
    path('', views.student_dashboard, name='student_dashboard'),
    path('register/', views.register, name='register'),
    path('mark-attendance/', views.mark_attendance, name='mark_attendance'),
    path('attendance-calendar/', views.attendance_calendar, name='attendance_calendar'),
    path('subject-calendar/<int:subject_id>/', views.subject_calendar, name='subject_calendar'),
    path('attendance-history/', views.attendance_history, name='attendance_history'),
    path('apply-leave/', views.apply_leave, name='apply_leave'),
    path('leave-status/', views.leave_status, name='leave_status'),
    path('report-extra-holiday/', views.report_extra_holiday, name='report_extra_holiday'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('profile/', views.profile, name='profile'),
    path('select-semester/', views.select_semester, name='select_semester'),
    path('my-subjects/', views.my_subjects, name='my_subjects'),

    path('add-subject/', views.add_subject, name='add_subject'),
    path('update-target/<int:enrollment_id>/', views.update_target, name='update_target'),
    path('unenroll-subject/<int:enrollment_id>/', views.unenroll_subject, name='unenroll_subject'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('manage/students/', views.manage_students, name='manage_students'),
    path('manage/extra-holiday-reports/', views.manage_extra_holiday_reports, name='manage_extra_holiday_reports'),
    path('manage/approve-extra-holiday/<int:report_id>/', views.approve_extra_holiday_report, name='approve_extra_holiday_report'),
    path('manage/reject-extra-holiday/<int:report_id>/', views.reject_extra_holiday_report, name='reject_extra_holiday_report'),
    path('manage/semester/<int:semester>/', views.manage_semester, name='manage_semester'),


    path('manage/add-subject/', views.add_subject_admin, name='add_subject_admin'),
    path('manage/update-subject/<int:subject_id>/', views.update_subject_classes, name='update_subject_classes'),
    path('manage/delete-subject/<int:subject_id>/', views.delete_subject, name='delete_subject'),
    path('upload-calendar/', views.upload_calendar, name='upload_calendar'),
    path('upload-holiday-list/', views.upload_holiday_list, name='upload_holiday_list'),
    path('upload-timetable/', views.upload_timetable, name='upload_timetable'),
    path('clarify-timetable/', views.clarify_timetable, name='clarify_timetable'),
    path('ai-chat/', views.ai_chat, name='ai_chat'),
    
]