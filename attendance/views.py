from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from .models import Subject, Attendance, StudentProfile, Enrollment, Notification, LeaveApplication, AcademicYearConfig, AcademicCalendar, StudentTimetable, ExtraHolidayReport
from .forms import StudentRegistrationForm, LeaveApplicationForm, ExtraHolidayReportForm
from datetime import datetime, timedelta, date
import calendar
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import re
from django.utils.text import slugify
from django.contrib.auth.models import User
from .ai_utils import analyze_timetable, analyze_academic_calendar, clean_subject_name

def register(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Welcome! Your account has been created successfully.')
            return redirect('student_dashboard')
    else:
        form = StudentRegistrationForm()
    return render(request, 'attendance/register.html', {'form': form})

@login_required
def student_dashboard(request):
    # Check if student has set their semester
    profile = request.user.studentprofile if hasattr(request.user, 'studentprofile') else None
    if not request.user.is_staff and profile:
        if profile.current_semester is None:
            return redirect('select_semester')
            
    today = timezone.now().date()

    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    # Get enrolled subjects with precomputed attendance stats
    from django.db.models import Sum, Q
    enrollments = Enrollment.objects.filter(
        student=request.user, 
        is_active=True
    ).select_related('subject').annotate(
        total_units_held=Sum('subject__attendances__units', filter=Q(subject__attendances__student=request.user)),
        present_units=Sum('subject__attendances__units', filter=Q(subject__attendances__student=request.user, subject__attendances__status='present'))
    )
    
    subjects = [e.subject for e in enrollments]
    
    # Today's attendance status
    today_attendance = Attendance.objects.filter(
        student=request.user, date=today
    ).first()
    
    # Weekly attendance
    weekly_attendance = Attendance.objects.filter(
        student=request.user,
        date__gte=start_of_week,
        date__lte=end_of_week,
        status='present'
    ).aggregate(Sum('units'))['units__sum'] or 0
    
    # Total statistics
    total_attendance = Attendance.objects.filter(student=request.user)
    # total_classes here means total units HELD so far (recorded)
    stats = total_attendance.aggregate(
        total_held=Sum('units'),
        present=Sum('units', filter=Q(status='present')),
        late=Sum('units', filter=Q(status='late'))
    )
    total_held_units = stats['total_held'] or 0
    present_count = stats['present'] or 0
    late_count = stats['late'] or 0
    attendance_percentage = (present_count / total_held_units * 100) if total_held_units > 0 else 0
    
    # Subject-wise attendance calculation
    subject_attendance = []
    for enrollment in enrollments:
        subject = enrollment.subject
        t = enrollment.total_units_held or 0
        p = enrollment.present_units or 0
        percentage = (p / t * 100) if t > 0 else 0
        
        target = enrollment.target_percentage
        m = enrollment.total_classes
        target_fraction = target / 100.0
        
        stats = enrollment.get_bunk_stats()
        subject_attendance.append({
            'subject': subject,
            'percentage': stats['percentage'],
            'total': stats['total_held'],
            'present': stats['present'],
            'bunkable': stats['bunkable'],
            'needs_to_attend': stats['needs_to_attend'],
            'classes_remaining': stats['classes_remaining'],
            'target_percentage': enrollment.target_percentage
        })

    total_bunks_available = sum(item['bunkable'] for item in subject_attendance)

    # Check if safe to bunk today
    today_name = timezone.now().strftime('%A')
    today_classes_entries = day_schedule.get(today_name, [])
    safe_to_bunk_today = True if today_classes_entries else False
    
    for entry in today_classes_entries:
        subj_name = entry.get('subject')
        match_found = False
        for sa in subject_attendance:
            # Fuzzy match subject name
            from .ai_utils import clean_subject_name
            if clean_subject_name(sa['subject'].name) == clean_subject_name(subj_name) or \
               clean_subject_name(sa['subject'].code) == clean_subject_name(subj_name):
                if sa['bunkable'] <= 0:
                    safe_to_bunk_today = False
                match_found = True
                break
        if not match_found:
            safe_to_bunk_today = False
            break

    # Available subjects for enrollment
    if profile and profile.current_semester:
        available_subjects = Subject.objects.filter(semester=profile.current_semester).exclude(enrollments__student=request.user, enrollments__is_active=True)
    else:
        available_subjects = Subject.objects.exclude(enrollments__student=request.user, enrollments__is_active=True)
    
    student_timetable = StudentTimetable.objects.filter(student=request.user, semester=profile.current_semester).first() if profile and profile.current_semester else None
    
    classes_per_day = {}
    day_schedule = {}
    if student_timetable and student_timetable.is_processed and isinstance(student_timetable.schedule_json, dict):
        analytics = student_timetable.schedule_json.get('_analytics', {})
        classes_per_day = analytics.get('classes_per_day', {})
        raw_day_schedule = analytics.get('day_entries', {})
        # Normalize keys to full day names for the template
        normalized_schedule = {}
        for day_name in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
            prefix = day_name[:3].lower()
            for k, v in raw_day_schedule.items():
                if str(k).lower().startswith(prefix):
                    normalized_schedule[day_name] = v
                    break
        day_schedule = normalized_schedule

    # Recent attendance (last 5 records)
    recent_attendance = Attendance.objects.filter(student=request.user).order_by('-date', '-check_in_time')[:5]

    # Notifications
    notifications = Notification.objects.filter(
        Q(is_global=True) | Q(target_students=request.user)
    ).distinct().order_by('-created_at')[:5]

    # Pending leaves
    pending_leaves = LeaveApplication.objects.filter(student=request.user, status='pending').order_by('-applied_on')

    context = {
        'today_attendance': today_attendance,
        'weekly_attendance': weekly_attendance,
        'present_count': present_count,
        'late_count': late_count,
        'attendance_percentage': round(attendance_percentage, 1),
        'total_held_units': total_held_units,
        'subject_attendance': subject_attendance,
        'total_bunks_available': total_bunks_available,
        'safe_to_bunk_today': safe_to_bunk_today,
        'recent_attendance': recent_attendance,
        'notifications': notifications,
        'pending_leaves': pending_leaves,
        'subjects': subjects,
        'available_subjects': available_subjects,
        'student_timetable': student_timetable,
        'classes_per_day': classes_per_day,
        'day_schedule': day_schedule,
        'profile': profile,
        'now': timezone.now()
    }

    return render(request, 'attendance/student_dashboard.html', context)

@login_required
def mark_attendance(request):
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        subject = get_object_or_404(Subject, id=subject_id)
        today = timezone.now().date()
        
        # Check if already marked
        existing = Attendance.objects.filter(
            student=request.user, subject=subject, date=today
        ).first()
        
        if not existing:
            # Auto-detect units from timetable
            units = 1
            profile = getattr(request.user, 'studentprofile', None)
            if profile and profile.current_semester:
                timetable = StudentTimetable.objects.filter(student=request.user, semester=profile.current_semester).first()
                if timetable and timetable.schedule_json:
                    day_name = timezone.now().strftime('%A')
                    day_entries = timetable.schedule_json.get('_analytics', {}).get('day_entries', {}).get(day_name, [])
                    for entry in day_entries:
                        # Use a fuzzy match or clean comparison for subject names
                        if entry.get('subject') == subject.name or entry.get('subject') == subject.code:
                            try:
                                units = int(entry.get('units', 1))
                                break
                            except: pass

            attendance = Attendance.objects.create(
                student=request.user,
                subject=subject,
                date=today,
                status='present',
                units=units,
                marked_by=request.user
            )
            messages.success(request, f'Attendance marked for {subject.name} ({units} unit{"s" if units > 1 else ""})!')
        else:
            messages.warning(request, f'Already marked attendance for {subject.name} today!')
        
        return redirect('student_dashboard')
    
    return redirect('student_dashboard')

@login_required
def attendance_calendar(request):
    today = timezone.now().date()
    
    # Handle POST requests for marking attendance
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            date_str = data.get('date')
            status = data.get('status')
            
            if not date_str or status not in ['present', 'absent', 'excused', 'clear']:
                return JsonResponse({'success': False, 'error': 'Invalid data'})
            
            # Parse date
            try:
                attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid date format'})
            
            # Get user's enrolled subjects
            enrolled_subjects = Enrollment.objects.filter(
                student=request.user, 
                is_active=True
            ).values_list('subject', flat=True)
            
            if not enrolled_subjects.exists():
                return JsonResponse({'success': False, 'error': 'No enrolled subjects'})
            
            # If status is 'clear', delete all attendance records for this date
            if status == 'clear':
                Attendance.objects.filter(
                    student=request.user,
                    date=attendance_date,
                    subject_id__in=enrolled_subjects
                ).delete()
            else:
                # Update or create attendance record for all enrolled subjects
                profile = getattr(request.user, 'studentprofile', None)
                timetable = None
                if profile and profile.current_semester:
                    timetable = StudentTimetable.objects.filter(student=request.user, semester=profile.current_semester).first()
                
                day_name = attendance_date.strftime('%A')
                timetable_entries = timetable.schedule_json.get('_analytics', {}).get('day_entries', {}).get(day_name, []) if timetable and timetable.schedule_json else []

                for subject_id in enrolled_subjects:
                    # Determine units for this specific subject and day
                    units = 1
                    subj_obj = Subject.objects.filter(id=subject_id).first()
                    if subj_obj:
                        for entry in timetable_entries:
                            if entry.get('subject') == subj_obj.name or entry.get('subject') == subj_obj.code:
                                try:
                                    units = int(entry.get('units', 1))
                                    break
                                except: pass

                    attendance, created = Attendance.objects.update_or_create(
                        student=request.user,
                        subject_id=subject_id,
                        date=attendance_date,
                        defaults={
                            'status': status,
                            'units': units,
                            'marked_by': request.user
                        }
                    )
            
            return JsonResponse({'success': True})
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # Handle GET requests
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    cal = calendar.monthcalendar(year, month)
    
    # Create a detailed calendar with day names
    import calendar as cal_module
    detailed_cal = []
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for week in cal:
        detailed_week = []
        for day in week:
            if day == 0:
                detailed_week.append(None)
            else:
                date_obj = datetime(year, month, day).date()
                day_of_week = cal_module.weekday(year, month, day)
                day_name = day_names[day_of_week]
                detailed_week.append({
                    'day': day,
                    'date': date_obj,
                    'day_name': day_name
                })
        detailed_cal.append(detailed_week)

    # Get attendance records for this month
    start_date = datetime(year, month, 1).date()
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date()
    else:
        end_date = datetime(year, month + 1, 1).date()

    attendance_records = Attendance.objects.filter(
        student=request.user,
        date__gte=start_date,
        date__lt=end_date
    ).order_by('date', 'subject_id')
    
    # Build attendance map - use first status for each date
    attendance_map = {}
    for record in attendance_records:
        if record.date.day not in attendance_map:
            attendance_map[record.date.day] = record.status

    if month == 1:
        previous_year = year - 1
        previous_month = 12
    else:
        previous_year = year
        previous_month = month - 1

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    
    context = {
        'calendar': detailed_cal,
        'original_calendar': cal,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'attendance_map': attendance_map,
        'today': today,
        'previous_month_url': f'?year={previous_year}&month={previous_month}',
        'next_month_url': f'?year={next_year}&month={next_month}',
    }
    return render(request, 'attendance/attendance_calendar.html', context)

@login_required
def attendance_history(request):
    records = Attendance.objects.filter(student=request.user)
    
    # Filter by subject
    subject_id = request.GET.get('subject')
    if subject_id:
        records = records.filter(subject_id=subject_id)
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        records = records.filter(status=status)

    # Filter by date
    date_param = request.GET.get('date')
    if date_param:
        records = records.filter(date=date_param)
        
    # Order by most recent
    records = records.order_by('-date', '-check_in_time')
    
    paginator = Paginator(records, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    subjects = Subject.objects.all()
    
    context = {
        'page_obj': page_obj,
        'subjects': subjects,
        'current_subject': subject_id,
        'current_status': status,
        'current_date': date_param,
    }
    return render(request, 'attendance/attendance_history.html', context)

@login_required
def subject_calendar(request, subject_id):
    """Display attendance calendar for a specific subject"""
    today = timezone.now().date()
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Check if student is enrolled in this subject
    enrollment = get_object_or_404(Enrollment, student=request.user, subject=subject, is_active=True)
    
    # Handle POST requests for marking attendance
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            date_str = data.get('date')
            status = data.get('status')
            
            if not date_str or status not in ['present', 'absent', 'excused', 'clear']:
                return JsonResponse({'success': False, 'error': 'Invalid data'})
            
            # Parse date
            try:
                attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid date format'})
            
            # If status is 'clear', delete attendance record for this date and subject
            if status == 'clear':
                Attendance.objects.filter(
                    student=request.user,
                    subject=subject,
                    date=attendance_date
                ).delete()
            else:
                # Update or create attendance record for this specific subject
                units = 1
                profile = getattr(request.user, 'studentprofile', None)
                if profile and profile.current_semester:
                    timetable = StudentTimetable.objects.filter(student=request.user, semester=profile.current_semester).first()
                    if timetable and timetable.schedule_json:
                        day_name = attendance_date.strftime('%A')
                        day_entries = timetable.schedule_json.get('_analytics', {}).get('day_entries', {}).get(day_name, [])
                        for entry in day_entries:
                            if entry.get('subject') == subject.name or entry.get('subject') == subject.code:
                                try:
                                    units = int(entry.get('units', 1))
                                    break
                                except: pass

                attendance, created = Attendance.objects.update_or_create(
                    student=request.user,
                    subject=subject,
                    date=attendance_date,
                    defaults={
                        'status': status,
                        'units': units,
                        'marked_by': request.user
                    }
                )
            
            return JsonResponse({'success': True})
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # Handle GET requests
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    cal = calendar.monthcalendar(year, month)
    
    # Create a detailed calendar with day names
    import calendar as cal_module
    detailed_cal = []
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for week in cal:
        detailed_week = []
        for day in week:
            if day == 0:
                detailed_week.append(None)
            else:
                date_obj = datetime(year, month, day).date()
                day_of_week = cal_module.weekday(year, month, day)
                day_name = day_names[day_of_week]
                detailed_week.append({
                    'day': day,
                    'date': date_obj,
                    'day_name': day_name
                })
        detailed_cal.append(detailed_week)

    # Get attendance records for this month and subject
    start_date = datetime(year, month, 1).date()
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date()
    else:
        end_date = datetime(year, month + 1, 1).date()

    attendance_records = Attendance.objects.filter(
        student=request.user,
        subject=subject,
        date__gte=start_date,
        date__lt=end_date
    ).order_by('date')
    
    # Build attendance map
    attendance_map = {}
    for record in attendance_records:
        attendance_map[record.date.day] = record.status
    
    # Calculate attendance statistics (for all time, not just this month)
    all_attendance = Attendance.objects.filter(
        student=request.user,
        subject=subject
    )
    from django.db.models import Sum
    total_units_held = all_attendance.aggregate(Sum('units'))['units__sum'] or 0
    present_units = all_attendance.filter(status='present').aggregate(Sum('units'))['units__sum'] or 0
    absent_units = all_attendance.filter(status='absent').aggregate(Sum('units'))['units__sum'] or 0
    attendance_percentage = (present_units / total_units_held * 100) if total_units_held > 0 else 0

    target_fraction = enrollment.target_percentage / 100.0
    m = enrollment.total_classes
    bunkable = max(0, int(present_units + ((1 - target_fraction) * m) - total_units_held))
    required = int(target_fraction * m)
    needs_to_attend = max(0, required - present_units)

    if month == 1:
        previous_year = year - 1
        previous_month = 12
    else:
        previous_year = year
        previous_month = month - 1

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    
    context = {
        'calendar': detailed_cal,
        'original_calendar': cal,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'attendance_map': attendance_map,
        'today': today,
        'subject': subject,
        'previous_month_url': f'?year={previous_year}&month={previous_month}',
        'next_month_url': f'?year={next_year}&month={next_month}',
        'attendance_percentage': round(attendance_percentage, 1),
        'total_units_held': total_units_held,
        'present_units': present_units,
        'absent_units': absent_units,
        'bunkable': bunkable,
        'needs_to_attend': needs_to_attend,
    }
    return render(request, 'attendance/subject_calendar.html', context)

@login_required
def ai_chat(request):
    if request.method == 'POST':
        try:
            from .ai_utils import get_ai_chat_response
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            # Optionally pass user statistics to Gemini for better context
            # response = get_ai_chat_response(user_message, context_data={"percentage": 78})
            response = get_ai_chat_response(user_message)
            
            return JsonResponse({'response': response})
        except Exception as e:
            return JsonResponse({'response': f"System error: {str(e)}"}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def apply_leave(request):
    if request.method == 'POST':
        form = LeaveApplicationForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.student = request.user
            leave.save()
            messages.success(request, 'Leave application submitted successfully!')
            return redirect('leave_status')
    else:
        form = LeaveApplicationForm()
    
    subjects = Enrollment.objects.filter(student=request.user).select_related('subject')
    form.fields['subject'].queryset = [e.subject for e in subjects]
    
    return render(request, 'attendance/apply_leave.html', {'form': form})

@login_required
def leave_status(request):
    leaves = LeaveApplication.objects.filter(student=request.user).order_by('-applied_on')
    return render(request, 'attendance/leave_status.html', {'leaves': leaves})

@login_required
def report_extra_holiday(request):
    if request.method == 'POST':
        form = ExtraHolidayReportForm(request.POST, user=request.user)
        if form.is_valid():
            report = form.save(commit=False)
            report.student = request.user
            report.save()
            messages.success(request, 'Extra holiday report submitted successfully! It will be reviewed by admin.')
            return redirect('student_dashboard')
    else:
        form = ExtraHolidayReportForm(user=request.user)
    
    return render(request, 'attendance/report_extra_holiday.html', {'form': form})

@login_required
def leaderboard(request):
    # Top students by attendance points
    top_students = StudentProfile.objects.filter(
        user__is_active=True
    ).select_related('user').order_by('-total_attendance_points')[:20]
    
    return render(request, 'attendance/leaderboard.html', {'top_students': top_students})

@login_required
def select_semester(request):
    profile = request.user.studentprofile if hasattr(request.user, 'studentprofile') else None
    
    if request.method == 'POST':
        semester = request.POST.get('semester')
        if semester and profile:
            profile.current_semester = int(semester)
            profile.save()
            messages.success(request, f'Semester {semester} selected! Welcome to your dashboard.')
            return redirect('student_dashboard')
            
    return render(request, 'attendance/select_semester.html')

@login_required
def profile(request):

    profile = request.user.studentprofile if hasattr(request.user, 'studentprofile') else None
    
    if request.method == 'POST':
        # Update profile
        request.user.first_name = request.POST.get('first_name')
        request.user.last_name = request.POST.get('last_name')
        request.user.email = request.POST.get('email')
        request.user.save()
        
        if profile:
            old_semester = profile.current_semester
            new_semester = request.POST.get('current_semester', 1)
            
            if old_semester and str(old_semester) != str(new_semester):
                # Semester changed: resetting data
                Enrollment.objects.filter(student=request.user).delete()
                Attendance.objects.filter(student=request.user).delete()
                StudentTimetable.objects.filter(student=request.user).delete()
                
                messages.warning(request, f'Semester changed to {new_semester}. Previous subject enrollments, timetable, and attendance data have been reset.')

            profile.phone = request.POST.get('phone')
            profile.address = request.POST.get('address')
            profile.current_semester = new_semester
            profile.save()

        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return render(request, 'attendance/profile.html', {'profile': profile})

@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    return render(request, 'attendance/admin_dashboard.html', {
        'semesters': range(1, 9)
    })

@user_passes_test(lambda u: u.is_staff)
def manage_semester(request, semester):
    subjects = Subject.objects.filter(semester=semester).order_by('name')
    return render(request, 'attendance/manage_semester.html', {
        'subjects': subjects,
        'semester': semester
    })

@user_passes_test(lambda u: u.is_staff)
def manage_students(request):
    students = User.objects.filter(is_staff=False).select_related('studentprofile').order_by('username')
    return render(request, 'attendance/manage_students.html', {
        'students': students
    })

@user_passes_test(lambda u: u.is_staff)
def manage_extra_holiday_reports(request):
    reports = ExtraHolidayReport.objects.select_related('student', 'subject', 'reviewed_by').order_by('-submitted_at')
    return render(request, 'attendance/manage_extra_holiday_reports.html', {
        'reports': reports
    })

@user_passes_test(lambda u: u.is_staff)
def approve_extra_holiday_report(request, report_id):
    report = get_object_or_404(ExtraHolidayReport, id=report_id)
    if report.status == 'pending':
        report.status = 'approved'
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save()
        
        # Adjust total_classes for the subject
        unique_dates = set(report.dates)
        adjustment = len(unique_dates)
        subject = report.subject
        subject.total_classes = max(0, subject.total_classes - adjustment)
        subject.save()
        
        # Update all active enrollments for this subject
        from django.db.models import F
        Enrollment.objects.filter(subject=subject, is_active=True).update(
            total_classes=F('total_classes') - adjustment
        )
        
        # Send notification to all enrolled students
        enrolled_students = Enrollment.objects.filter(subject=subject, is_active=True).values_list('student', flat=True)
        notification = Notification.objects.create(
            title="Extra Holiday Adjustment",
            message=f"Due to reported extra holidays, the total classes for {subject.name} have been adjusted. Your bunk calculations may have changed.",
            created_by=request.user,
            is_global=False
        )
        notification.target_students.set(enrolled_students)
        
        messages.success(request, f'Report approved. Total classes for {subject.name} decreased by {adjustment}.')
    return redirect('manage_extra_holiday_reports')

@user_passes_test(lambda u: u.is_staff)
def reject_extra_holiday_report(request, report_id):
    report = get_object_or_404(ExtraHolidayReport, id=report_id)
    if report.status == 'pending':
        report.status = 'rejected'
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save()
        messages.success(request, 'Report rejected.')
    return redirect('manage_extra_holiday_reports')

@user_passes_test(lambda u: u.is_staff)
def add_subject_admin(request):
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        name = request.POST.get('name')
        semester = request.POST.get('semester', 1)
        total_classes = request.POST.get('total_classes', 40)
        code = request.POST.get('code')
        
        if subject_id:
            # Editing existing subject
            subject = get_object_or_404(Subject, id=subject_id)
            subject.name = name
            subject.semester = semester
            subject.total_classes = total_classes
            if code:
                subject.code = code
            subject.save()
            messages.success(request, f'Subject {name} updated successfully!')
        else:
            # Creating new subject
            if not code:
                prefix = ''.join([w[0].upper() for w in name.split()])[:3]
                existing = Subject.objects.filter(code__startswith=prefix).count()
                code = f"{prefix}{existing+1:02d}"
                
            Subject.objects.create(
                name=name,
                code=code,
                semester=semester,
                total_classes=total_classes,
                teacher_name="TBD",
                time_slot="TBD",
                room_number="TBD"
            )
            messages.success(request, f'Subject {name} created successfully!')
    return redirect('manage_semester', semester=semester)


@user_passes_test(lambda u: u.is_staff)
def update_subject_classes(request, subject_id):
    if request.method == 'POST':
        subject = get_object_or_404(Subject, id=subject_id)
        subject.total_classes = request.POST.get('total_classes', 40)
        subject.save()
        messages.success(request, f'Total classes for {subject.name} updated!')
        return redirect('manage_semester', semester=subject.semester)
    return redirect('admin_dashboard')

@user_passes_test(lambda u: u.is_staff)
def delete_subject(request, subject_id):
    print(f"DEBUG: Deleting subject {subject_id}")
    subject = get_object_or_404(Subject, id=subject_id)
    name = subject.name
    semester = subject.semester
    subject.delete()
    print(f"DEBUG: Deleted subject {name}")
    messages.success(request, f'Subject {name} deleted!')
    return redirect('manage_semester', semester=semester)


@login_required
def select_semester(request):
    profile = request.user.studentprofile if hasattr(request.user, 'studentprofile') else None
    
    if request.method == 'POST':
        semester = request.POST.get('semester')
        if semester and profile:
            profile.current_semester = int(semester)
            profile.save()
            messages.success(request, f'Semester {semester} selected! Welcome to your dashboard.')
            return redirect('student_dashboard')
            
    return render(request, 'attendance/select_semester.html')

@login_required
def my_subjects(request):
    # Check if student has set their semester
    if not request.user.is_staff and hasattr(request.user, 'studentprofile'):
        if request.user.studentprofile.current_semester is None:
            return redirect('select_semester')

    enrollments = Enrollment.objects.filter(student=request.user, is_active=True).select_related('subject')
    
    # Filter available subjects by student's current semester
    if hasattr(request.user, 'studentprofile'):
        current_semester = request.user.studentprofile.current_semester
    else:
        current_semester = None

    if current_semester is not None:
        available_subjects = Subject.objects.filter(semester=current_semester).exclude(enrollments__student=request.user, enrollments__is_active=True)
    else:
        # If the student has no semester mapped, return none to assign
        available_subjects = Subject.objects.none()
    
    from django.db.models import Sum
    # Bunk calculation per subject using personalized total_classes
    for enrollment in enrollments:
        subject = enrollment.subject
        subject_qs = Attendance.objects.filter(student=request.user, subject=subject)
        
        total_units = subject_qs.aggregate(Sum('units'))['units__sum'] or 0
        present_units = subject_qs.filter(status='present').aggregate(Sum('units'))['units__sum'] or 0
        m = enrollment.total_classes  # total expected classes (personalized)
        target = enrollment.target_percentage
        target_fraction = target / 100.0
        
        enrollment.attendance_percentage = round((present_units / total_units * 100), 1) if total_units > 0 else 0
        enrollment.total_classes_held = total_units
        enrollment.present_count = present_units
        enrollment.absent_count = total_units - present_units
        
        # Bunkable using student's custom target
        enrollment.bunkable = max(0, int(present_units + ((1 - target_fraction) * m) - total_units))
        
        # Needs to attend to reach target% of total
        required = int(target_fraction * m)
        enrollment.needs_to_attend = max(0, required - present_units)
        
        # Classes remaining
        enrollment.classes_remaining = max(0, m - total_units)
        enrollment.total_expected = m


    
    return render(request, 'attendance/my_subjects.html', {
        'enrollments': enrollments,
        'available_subjects': available_subjects
    })

@login_required
def add_subject(request):
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        subject = get_object_or_404(Subject, id=subject_id)
        
        # Ensure subject belongs to student's current semester
        profile = request.user.studentprofile if hasattr(request.user, 'studentprofile') else None
        if profile and profile.current_semester and subject.semester != profile.current_semester:
            messages.error(request, f'Cannot enroll! {subject.name} does not belong to semester {profile.current_semester}.')
            return redirect('my_subjects')

        enrollment, created = Enrollment.objects.get_or_create(
            student=request.user,
            subject=subject,
            defaults={'is_active': True, 'total_classes': subject.total_classes}
        )
        
        if not created and not enrollment.is_active:
            enrollment.is_active = True
            enrollment.save()
            messages.success(request, f'Successfully re-enrolled in {subject.name}!')
        elif created:
            messages.success(request, f'Successfully enrolled in {subject.name}!')
        else:
            messages.info(request, f'You are already enrolled in {subject.name}.')
            
    return redirect('my_subjects')

@login_required
def unenroll_subject(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, student=request.user)
    name = enrollment.subject.name
    enrollment.delete()
    messages.success(request, f'Successfully unenrolled from {name}.')
    return redirect('my_subjects')

@login_required
def update_target(request, enrollment_id):
    if request.method == 'POST':
        enrollment = get_object_or_404(Enrollment, id=enrollment_id, student=request.user)
        target = request.POST.get('target_percentage')
        total_classes = request.POST.get('total_classes')
        
        if target:
            target_val = max(1, min(100, int(target)))
            enrollment.target_percentage = target_val
            
        if total_classes:
            total_classes_val = max(1, int(total_classes))
            enrollment.total_classes = total_classes_val
            
        enrollment.save()
        messages.success(request, f'Updated settings for {enrollment.subject.name}!')
    return redirect('my_subjects')

@user_passes_test(lambda u: u.is_staff)
def upload_calendar(request):
    if request.method == 'POST':
        year_val = request.POST.get('year', 2024)
        image = request.FILES.get('calendar_image')
        holiday_image = request.FILES.get('holiday_list_image')
        
        calendar, created = AcademicCalendar.objects.get_or_create(year=year_val)
        if image:
            calendar.calendar_image = image
        if holiday_image:
            calendar.holiday_list_image = holiday_image
        calendar.is_processed = False
        calendar.save()
        
        # Real AI Processing using Gemini
        try:
            ai_data = analyze_academic_calendar(
                calendar.calendar_image.path if calendar.calendar_image else None,
                calendar.holiday_list_image.path if calendar.holiday_list_image else None
            )
            
            # Map extracted data to model fields
            calendar.sem1_data = ai_data.get('sem1', {})
            calendar.sem2_data = ai_data.get('sem2', {})
            calendar.sem3_data = ai_data.get('sem3', {})
            calendar.sem4_data = ai_data.get('sem4', {})
            calendar.sem5_data = ai_data.get('sem5', {})
            calendar.sem6_data = ai_data.get('sem6', {})
            calendar.sem7_data = ai_data.get('sem7', {})
            calendar.sem8_data = ai_data.get('sem8', {})
            calendar.holidays_data = ai_data.get('global_holidays', [])
            
            calendar.is_processed = True
            calendar.save()
            messages.success(request, f'Yearly Academic Calendar processed by Gemini AI!')
        except Exception as e:
            messages.error(request, f'AI Processing failed: {str(e)}. Using fallback simulation.')
            # Fallback simulation
            calendar.sem1_data = {"start": "2024-07-15", "end": "2024-11-30", "holidays": ["2024-08-15", "2024-10-02"]}
            calendar.sem2_data = {"start": "2025-01-10", "end": "2025-05-15", "holidays": ["2025-01-26", "2025-03-14"]}
            calendar.holidays_data = ["2024-08-15", "2024-10-02", "2025-01-26"]
            calendar.is_processed = True
            calendar.save()
        
        messages.success(request, f'Yearly Academic Calendar uploaded! AI successfully identified Odd/Even semester cycles.')
        return redirect('admin_dashboard')
    return redirect('admin_dashboard')

@user_passes_test(lambda u: u.is_staff)
def upload_holiday_list(request):
    if request.method == 'POST':
        year_val = request.POST.get('year', 2024)
        holiday_image = request.FILES.get('holiday_list_image')
        
        calendar, created = AcademicCalendar.objects.get_or_create(year=year_val)
        if holiday_image:
            calendar.holiday_list_image = holiday_image
        calendar.is_processed = False
        calendar.save()
        
        try:
            ai_data = analyze_academic_calendar(
                calendar.calendar_image.path if calendar.calendar_image else None,
                calendar.holiday_list_image.path if calendar.holiday_list_image else None
            )
            
            # Map extracted data to model fields
            calendar.sem1_data = ai_data.get('sem1', calendar.sem1_data)
            calendar.sem2_data = ai_data.get('sem2', calendar.sem2_data)
            calendar.sem3_data = ai_data.get('sem3', calendar.sem3_data)
            calendar.sem4_data = ai_data.get('sem4', calendar.sem4_data)
            calendar.sem5_data = ai_data.get('sem5', calendar.sem5_data)
            calendar.sem6_data = ai_data.get('sem6', calendar.sem6_data)
            calendar.sem7_data = ai_data.get('sem7', calendar.sem7_data)
            calendar.sem8_data = ai_data.get('sem8', calendar.sem8_data)
            calendar.holidays_data = ai_data.get('global_holidays', calendar.holidays_data)
            
            calendar.is_processed = True
            calendar.save()
            messages.success(request, f'Global Holiday List processed by Gemini AI!')
        except Exception as e:
            messages.error(request, f'AI Processing failed: {str(e)}. Using fallback simulation.')
            # Fallback simulation
            calendar.holidays_data = ["2024-08-15", "2024-10-02", "2025-01-26", "2025-03-14", "2025-10-22"]
            calendar.is_processed = True
            calendar.save()
            
        return redirect('admin_dashboard')
    return redirect('admin_dashboard')

@login_required
def upload_timetable(request):
    if request.method == 'POST':
        image = request.FILES.get('timetable_image')
        link = request.POST.get('timetable_link')
        
        # Safe profile access - auto-create if missing
        profile = getattr(request.user, 'studentprofile', None)
        if not profile:
            profile = StudentProfile.objects.create(
                user=request.user,
                student_id=f"STU{request.user.id:04d}"
            )
        semester_val = profile.current_semester
        
        if not semester_val:
            messages.error(request, "Please select your semester first.")
            return redirect('select_semester')
            
        if not image and not link:
            messages.error(request, "Please provide either an image or a public link.")
            return redirect('student_dashboard')

        timetable, created = StudentTimetable.objects.get_or_create(
            student=request.user, 
            semester=semester_val
        )
        
        if image:
            timetable.timetable_image = image
        if link:
            timetable.timetable_link = link
            
        timetable.is_processed = False
        timetable.save()
        
        schedule = {}
        # Real AI Processing using Gemini
        try:
            image_path = timetable.timetable_image.path if timetable.timetable_image else None
            schedule = analyze_timetable(image_path=image_path, link=timetable.timetable_link)
            timetable.schedule_json = schedule
            timetable.is_processed = True
            timetable.save()

            analytics = schedule.get('_analytics', {}) if isinstance(schedule, dict) else {}
            
            # CHECK FOR MISSING LAB EXCEPTION
            needs_clarification = analytics.get('needs_clarification', [])
            if needs_clarification:
                request.session['timetable_clarification'] = needs_clarification
                request.session['pending_timetable_id'] = timetable.id
                messages.warning(request, "Some subjects have practicals that weren't clearly marked as 'Lab' in the grid. Please clarify.")
                return redirect('clarify_timetable')

            total_weekly_classes = analytics.get('total_weekly_classes')
            day_wise = analytics.get('day_wise_total_classes', {})
            parse_source = analytics.get('parse_source', 'unknown') if isinstance(analytics, dict) else 'unknown'
            if total_weekly_classes is not None:
                messages.info(request, f"AI parsed your timetable. Weekly total classes: {total_weekly_classes}")
            if isinstance(day_wise, dict) and day_wise:
                day_parts = [f"{day}: {count}" for day, count in day_wise.items()]
                messages.info(request, "Day-wise class count: " + ", ".join(day_parts))
            if total_weekly_classes == 0:
                messages.warning(request, f"AI could not extract a valid timetable summary from this image (reason: {parse_source}). Please upload a clearer timetable image.")
        except Exception as e:
            messages.error(request, f'AI Timetable analysis failed: {str(e)}')
            # Fallback
            timetable.schedule_json = {"Monday": ["Physics"], "Tuesday": ["Math"]}
            timetable.is_processed = True
            timetable.save()
        
        analytics = schedule.get('_analytics', {}) if isinstance(schedule, dict) else {}
        extracted_total = analytics.get('total_weekly_classes', 0)

        # Get the latest processed yearly calendar (Optional for basic sync)
        calendar = AcademicCalendar.objects.filter(is_processed=True).order_by('-year', '-id').first()
        
        if extracted_total > 0:
            # We call the logic regardless of calendar presence; it handles the fallback now.
            calculate_total_classes_logic(request.user, semester_val, timetable, calendar)
            
            if calendar and calendar.is_processed:
                messages.success(request, 'Timetable synced! Total classes calculated using the Yearly Academic Calendar.')
            else:
                messages.success(request, 'Timetable synced! (Using default 14-week semester as no Academic Calendar is set by admin).')
            
            if calendar and not calendar.is_processed:
                messages.warning(request, 'Academic Calendar found but not processed. Using default values.')
        else:
            messages.error(request, 'Timetable upload saved, but class extraction failed. Please upload a clear full timetable with day names and bottom summary lines.')
            
        return redirect('student_dashboard')
    return redirect('student_dashboard')

@login_required
def clarify_timetable(request):
    clarifications = request.session.get('timetable_clarification', [])
    timetable_id = request.session.get('pending_timetable_id')
    
    if not clarifications or not timetable_id:
        return redirect('student_dashboard')
        
    timetable = get_object_or_404(StudentTimetable, id=timetable_id, student=request.user)
    
    if request.method == 'POST':
        # Process user clarifications
        schedule = timetable.schedule_json
        day_entries = schedule.get('_analytics', {}).get('day_entries', {})
        
        def _acronym(text):
            stop_words = ['and', 'to', 'of', 'in', 'for', 'with', 'the', 'a', 'an']
            words = [w for w in re.findall(r'[a-zA-Z0-9]+', (text or '')) if w.lower() not in stop_words]
            if not words: return ""
            if len(words) == 1 and len(words[0]) <= 5: return words[0].lower()
            return "".join([w[0] for w in words if w and not w.isdigit()]).lower()

        def names_match(name1, name2):
            c1 = clean_subject_name(name1)
            c2 = clean_subject_name(name2)
            if c1 == c2: return True
            a1 = _acronym(c1)
            a2 = _acronym(c2)
            return a1 == a2 and a1 != ""

        # Ensure we are working with the actual dict and it has the right structure
        if '_analytics' not in schedule: schedule['_analytics'] = {}
        if 'day_entries' not in schedule['_analytics']: schedule['_analytics']['day_entries'] = {}
        day_entries = schedule['_analytics']['day_entries']

        import json as json_lib
        debug_log = []
        debug_log.append(f"POST Data: {dict(request.POST)}")
        
        for item in clarifications:
            subject = item.get('subject')
            if not subject: continue
            subject_clean = clean_subject_name(subject)
            subject_slug = slugify(subject)
            debug_log.append(f"Processing: {subject} (Clean: {subject_clean}, Slug: {subject_slug})")
            
            # 1. Handle Lab Day Clarification
            selected_day = request.POST.get(f'day_{subject_slug}')
            if selected_day:
                debug_log.append(f"Lab Day selected: {selected_day}")
                day_prefix = selected_day[:3].lower()
                target_keys = [k for k in day_entries.keys() if k.lower().startswith(day_prefix)]
                for actual_day_key in target_keys:
                    for entry in day_entries.get(actual_day_key, []):
                        if names_match(entry.get('subject'), subject):
                            entry['is_lab'] = True
                            entry['units'] = 1
                            debug_log.append(f"UPDATED LAB: {entry.get('subject')} on {actual_day_key}")
            
            # 2. Handle Ambiguous Width Clarification
            is_width = item.get('is_width_clarification')
            target_day = item.get('day')
            if is_width and target_day:
                selected_width = request.POST.get(f'width_{subject_slug}_{target_day}')
                if selected_width:
                    debug_log.append(f"Width selected for {target_day}: {selected_width}")
                    day_prefix = target_day[:3].lower()
                    target_keys = [k for k in day_entries.keys() if k.lower().startswith(day_prefix)]
                    for actual_day_key in target_keys:
                        for entry in day_entries.get(actual_day_key, []):
                            if names_match(entry.get('subject'), subject):
                                entry['units'] = int(selected_width)
                                entry['is_lab'] = False
                                debug_log.append(f"UPDATED WIDTH: {entry.get('subject')} on {actual_day_key} to {selected_width}")

            # 3. Handle Per-Day Slot Clarification (Mixed subjects)
            is_per_day = item.get('is_per_day_slot_clarification')
            if is_per_day:
                days_occurring = item.get('days_occurring', [])
                debug_log.append(f"Per-Day slots days: {days_occurring}")
                for day in days_occurring:
                    selected_slots = request.POST.get(f'slots_{subject_slug}_{day}')
                    debug_log.append(f"Slots for {day}: {selected_slots}")
                    if selected_slots:
                        day_prefix = day[:3].lower()
                        target_keys = [k for k in day_entries.keys() if k.lower().startswith(day_prefix)]
                        debug_log.append(f"Target keys for {day_prefix}: {target_keys}")
                        for actual_day_key in target_keys:
                            for entry in day_entries.get(actual_day_key, []):
                                if names_match(entry.get('subject'), subject):
                                    entry['units'] = int(selected_slots)
                                    debug_log.append(f"SUCCESS: Updated {entry.get('subject')} on {actual_day_key} to {selected_slots}")
        
        # Save debug log
        try:
            with open("debug_clarify.txt", "a") as f:
                f.write(f"\n--- {timezone.now()} ---\n")
                f.write("\n".join(debug_log) + "\n")
        except: pass

        # Recalculate total weekly classes based on clarifications
        total_weekly = 0
        for day, entries in day_entries.items():
            for entry in entries:
                total_weekly += int(entry.get('units', 1))
        
        schedule['_analytics']['total_weekly_classes'] = total_weekly
        schedule['_analytics']['needs_clarification'] = [] # Clear the flag
        
        timetable.schedule_json = json_lib.loads(json_lib.dumps(schedule))
        timetable.is_processed = True
        timetable.save(update_fields=['schedule_json', 'is_processed'])
        
        # Now trigger the final semester calculation
        calendar = AcademicCalendar.objects.filter(is_processed=True).order_by('-year', '-id').first()
        calculate_total_classes_logic(request.user, timetable.semester, timetable, calendar)
        messages.success(request, 'Timetable finalized with your clarifications!')
        
        # Cleanup session
        del request.session['timetable_clarification']
        del request.session['pending_timetable_id']
        
        return redirect('student_dashboard')
        
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    return render(request, 'attendance/clarify_timetable.html', {
        'clarifications': clarifications,
        'timetable': timetable,
        'days': days
    })

def calculate_total_classes_logic(user, semester, timetable, calendar):
    # Get the specific semester data from the yearly calendar
    sem_data = {}
    if calendar:
        sem_field = f'sem{semester}_data'
        sem_data = getattr(calendar, sem_field, {})
    
    start = None
    end = None
    all_holidays = set()

    if sem_data:
        start_str = sem_data.get('start')
        end_str = sem_data.get('end')
        
        if start_str and end_str:
            try:
                start = date.fromisoformat(start_str)
                end = date.fromisoformat(end_str)
                
                # Merge semester-specific holidays and global holidays
                sem_holidays_raw = sem_data.get('holidays', []) if isinstance(sem_data.get('holidays', []), list) else []
                sem_holidays = []
                for d in sem_holidays_raw:
                    try:
                        sem_holidays.append(date.fromisoformat(d))
                    except (ValueError, TypeError): pass
                
                global_holidays_data = calendar.holidays_data if calendar.holidays_data else []
                global_holidays = []
                for h in global_holidays_data:
                    try:
                        d_str = h['date'] if isinstance(h, dict) else h
                        global_holidays.append(date.fromisoformat(d_str))
                    except (ValueError, TypeError): pass
                
                all_holidays = set(sem_holidays + global_holidays)
            except (ValueError, TypeError):
                start = None
                end = None
    
    schedule = timetable.schedule_json
    day_entries = (schedule.get('_analytics', {}) if isinstance(schedule, dict) else {}).get('day_entries', {})
    if not isinstance(day_entries, dict):
        day_entries = {}

    # 1. Calculate precise teaching day counts (excluding Sundays and holidays)
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    teaching_day_counts = {day: 14 for day in days_of_week} # Default to 14 weeks if no calendar

    if start and end:
        teaching_day_counts = {day: 0 for day in days_of_week}
        curr = start
        while curr <= end:
            if curr.weekday() < 6 and curr not in all_holidays:  # weekday() < 6 excludes Sunday
                day_name = curr.strftime('%A')
                if day_name in teaching_day_counts:
                    teaching_day_counts[day_name] += 1
            curr += timedelta(days=1)

    # 2. Calculate Total Expected units for each subject
    subject_semester_totals = {}
    
    for day, num_occurrences in teaching_day_counts.items():
        # Robust matching for day names (e.g., 'Monday' matches 'MON', 'Mon', 'Monday')
        day_prefix = day[:3].lower()
        target_keys = [k for k in day_entries.keys() if str(k).lower().startswith(day_prefix)]
        
        entries = []
        for k in target_keys:
            entries.extend(day_entries.get(k, []))
        for entry in entries:
            sub_name = entry.get('subject')
            if not sub_name:
                continue
            unit = 1
            try:
                unit = max(1, int(entry.get('units', 1)))
            except (TypeError, ValueError):
                pass
            
            # Precise calculation: units * number of times this day occurs in the teaching calendar
            subject_semester_totals[sub_name] = subject_semester_totals.get(sub_name, 0) + (unit * num_occurrences)

    # 3. Match parsed subject names against ALL subjects in the same semester.
    semester_subjects = list(Subject.objects.filter(semester=semester).distinct())

    def _tokens(text):
        return set(re.findall(r'[a-z0-9]+', (text or '').lower()))

    def _acronym(text):
        stop_words = ['and', 'to', 'of', 'in', 'for', 'with', 'the', 'a', 'an']
        words = [w for w in re.findall(r'[a-zA-Z0-9]+', (text or '')) if w.lower() not in stop_words]
        if len(words) == 1 and len(words[0]) <= 5: return words[0].lower()
        return "".join([w[0] for w in words if w and not w.isdigit()]).lower()

    def _best_subject_match(parsed_name):
        parsed_name_clean = (parsed_name or '').lower().strip()
        if not parsed_name_clean: return None
        
        base_parsed = clean_subject_name(parsed_name_clean)
        parsed_tokens = _tokens(base_parsed)
        parsed_acr = _acronym(base_parsed)

        best = None
        best_score = 0
        
        for subj in semester_subjects:
            subj_name_raw = subj.name.lower()
            subj_code_raw = subj.code.lower()
            subj_base = clean_subject_name(subj.name)
            subj_acr = _acronym(subj_base)
            
            score = 0
            
            # Exact base name match (Merging Lab + Theory)
            if base_parsed == subj_base:
                score = 110
            # Code match
            elif parsed_name_clean == subj_code_raw or base_parsed == subj_code_raw:
                score = 100
            # Acronym match
            elif parsed_acr == subj_acr:
                score = 90
            # Partial match
            elif base_parsed in subj_base or subj_base in base_parsed:
                score = 50
            
            # Token overlap
            all_subj_tokens = _tokens(subj.name).union(_tokens(subj.code))
            overlap = sum(1 for pt in parsed_tokens if any(pt in st or st in pt for st in all_subj_tokens))
            if parsed_tokens: score += (overlap / len(parsed_tokens)) * 20

            if score > best_score:
                best = subj
                best_score = score
            elif score == best_score and best:
                # Tie-breaker: Prefer the subject with the shorter name (usually the base theory one)
                if len(subj.name) < len(best.name):
                    best = subj
                    
        return best if best_score >= 15 else None

    # 4. Final Aggregation and Enrollment Update
    subject_updates = {} # Map Subject -> total_classes
    
    for parsed_name, total_expected in subject_semester_totals.items():
        matched = _best_subject_match(parsed_name)
        
        if not matched:
            # Create subject if totally new
            clean_name = parsed_name.strip()
            matched = Subject.objects.filter(name__iexact=clean_name).first()
            if not matched:
                base_code = slugify(clean_name).upper()[:10]
                code = base_code
                suffix = 1
                while Subject.objects.filter(code=code).exists():
                    code = f"{base_code}{suffix}"
                    suffix += 1
                matched = Subject.objects.create(
                    name=clean_name, 
                    code=code, 
                    semester=semester,
                    teacher_name="TBD",
                    time_slot="TBD",
                    room_number="TBD"
                )
        
        if matched:
            subject_updates[matched] = subject_updates.get(matched, 0) + total_expected

    # Apply updates and deactivate ghosts
    active_subjects = set()
    for subj, total_classes in subject_updates.items():
        enrollment, created = Enrollment.objects.get_or_create(
            student=user,
            subject=subj
        )
        enrollment.total_classes = total_classes
        enrollment.is_active = True
        enrollment.save()
        active_subjects.add(subj.id)
    
    # Deactivate enrollments that are no longer part of this timetable for this semester
    Enrollment.objects.filter(student=user, subject__semester=semester).exclude(subject__id__in=active_subjects).update(is_active=False)


