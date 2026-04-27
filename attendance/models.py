from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    enrollment_year = models.IntegerField(default=2024)
    current_semester = models.IntegerField(null=True, blank=True, default=None)



    
    def __str__(self):
        return f"{self.student_id} - {self.user.get_full_name()}"
    


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    credits = models.IntegerField(default=3)
    time_slot = models.CharField(max_length=100)
    room_number = models.CharField(max_length=20)
    teacher_name = models.CharField(max_length=100)
    semester = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    max_students = models.IntegerField(default=60)
    total_classes = models.IntegerField(default=40)

    
    def __str__(self):
        return f"{self.name} ({self.code})"

class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    target_percentage = models.IntegerField(default=75)
    total_classes = models.IntegerField(default=40)

    
    class Meta:
        unique_together = ['student', 'subject']
    
    def __str__(self):
        return f"{self.student.username} - {self.subject.name}"

class Attendance(models.Model):
    ATTENDANCE_TYPES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('excused', 'Excused'),
        ('holiday', 'Holiday'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=10, choices=ATTENDANCE_TYPES, default='absent')
    units = models.IntegerField(default=1, help_text="Number of class units (e.g., 2 for double theory, 1 for lab)")
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='marked_attendances')
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'subject', 'date']
        ordering = ['-date']
    
    def save(self, *args, **kwargs):
        if self.status == 'present' and not self.check_in_time:
            self.check_in_time = timezone.now().time()
        super().save(*args, **kwargs)

    
    def __str__(self):
        return f"{self.student.username} - {self.subject.name} - {self.date} - {self.status}"

class Semester(models.Model):
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name

class Holiday(models.Model):
    name = models.CharField(max_length=100)
    date = models.DateField()
    
    def __str__(self):
        return f"{self.name} - {self.date}"

class Notification(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_global = models.BooleanField(default=True)
    target_students = models.ManyToManyField(User, blank=True, related_name='notifications')
    
    def __str__(self):
        return self.title

class LeaveApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_applications')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    applied_on = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reviewed_leaves')
    remarks = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.student.username} - {self.start_date} to {self.end_date}"

class AcademicYearConfig(models.Model):
    year = models.IntegerField(unique=True)  # 1, 2, 3, 4
    total_classes = models.IntegerField(default=100)
    
    class Meta:
        ordering = ['year']
        
    def __str__(self):
        return f"Year {self.year} Config"

class AcademicCalendar(models.Model):
    year = models.IntegerField(default=2024)
    calendar_image = models.ImageField(upload_to='academic_calendars/')
    holiday_list_image = models.ImageField(upload_to='holiday_lists/', null=True, blank=True)
    holidays_data = models.JSONField(default=list, blank=True)
    # Data for each semester extracted from the yearly calendar
    sem1_data = models.JSONField(default=dict, blank=True)
    sem2_data = models.JSONField(default=dict, blank=True)
    sem3_data = models.JSONField(default=dict, blank=True)
    sem4_data = models.JSONField(default=dict, blank=True)
    sem5_data = models.JSONField(default=dict, blank=True)
    sem6_data = models.JSONField(default=dict, blank=True)
    sem7_data = models.JSONField(default=dict, blank=True)
    sem8_data = models.JSONField(default=dict, blank=True)
    
    is_processed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Academic Year {self.year} Calendar"

class StudentTimetable(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    semester = models.IntegerField()
    timetable_image = models.ImageField(upload_to='timetables/', null=True, blank=True)
    timetable_link = models.URLField(null=True, blank=True)
    schedule_json = models.JSONField(default=dict, blank=True) # {"Monday": ["ML", "DAA"], ...}
    is_processed = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    class Meta:
        unique_together = ['student', 'semester']
        
    def __str__(self):
        return f"{self.student.username} - Sem {self.semester} Timetable"

class ExtraHolidayReport(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='extra_holiday_reports')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='extra_holiday_reports')
    dates = models.JSONField(default=list, help_text="List of dates in YYYY-MM-DD format")
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_extra_holiday_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.student.username} - {self.subject.name} - {self.status}"
    
    def get_unique_dates_count(self):
        return len(set(self.dates))
