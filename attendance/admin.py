from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Subject, Attendance, StudentProfile, Enrollment, AcademicYearConfig, Notification, LeaveApplication, Holiday, AcademicCalendar, ExtraHolidayReport

# Define an inline admin descriptor for StudentProfile model
# which acts a bit like a singleton
class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    verbose_name_plural = 'Student Profile Details'

# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = [StudentProfileInline]
    
    # Add custom fields to the list display in the admin panel
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_student_id', 'get_semester')
    
    def get_student_id(self, instance):
        if hasattr(instance, 'studentprofile'):
            return instance.studentprofile.student_id
        return '-'
    get_student_id.short_description = 'Student ID'

    def get_semester(self, instance):
        if hasattr(instance, 'studentprofile'):
            return instance.studentprofile.current_semester
        return '-'
    get_semester.short_description = 'Semester'

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'current_semester', 'enrollment_year')
    search_fields = ('user__username', 'student_id')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'semester', 'teacher_name')
    search_fields = ('code', 'name', 'teacher_name')
    list_filter = ('semester',)

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'date', 'status', 'marked_by')
    list_filter = ('status', 'date')
    search_fields = ('student__username', 'subject__name')

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'target_percentage', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('student__username', 'subject__name')

admin.site.register(AcademicYearConfig)
admin.site.register(Notification)
admin.site.register(LeaveApplication)
admin.site.register(Holiday)
admin.site.register(AcademicCalendar)
admin.site.register(ExtraHolidayReport)
