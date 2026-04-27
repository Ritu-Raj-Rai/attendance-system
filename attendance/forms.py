from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import StudentProfile, LeaveApplication, ExtraHolidayReport, Subject

class StudentRegistrationForm(UserCreationForm):
    current_semester = forms.ChoiceField(
        choices=[
            ('1', 'Semester 1'),
            ('2', 'Semester 2'),
            ('3', 'Semester 3'),
            ('4', 'Semester 4'),
            ('5', 'Semester 5'),
            ('6', 'Semester 6'),
            ('7', 'Semester 7'),
            ('8', 'Semester 8'),
        ],
        required=True,
        label='Current Semester'
    )
    
    class Meta:
        model = User
        fields = ['username', 'current_semester']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            student_id = f"STU{user.id:05d}"
            StudentProfile.objects.create(
                user=user,
                student_id=student_id,
                enrollment_year=2024,
                current_semester=int(self.cleaned_data['current_semester'])
            )

        return user


class LeaveApplicationForm(forms.ModelForm):
    class Meta:
        model = LeaveApplication
        fields = ['subject', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 4}),
        }

class ExtraHolidayReportForm(forms.ModelForm):
    dates = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control date-picker',
            'placeholder': 'Click to select dates...',
            'readonly': 'readonly'
        }),
        help_text="Click the calendar icon or input field to select multiple dates"
    )
    
    class Meta:
        model = ExtraHolidayReport
        fields = ['subject', 'dates', 'reason']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            # Filter subjects to only enrolled active subjects
            enrolled_subjects = self.user.enrollments.filter(is_active=True).values_list('subject', flat=True)
            if enrolled_subjects:
                self.fields['subject'].queryset = Subject.objects.filter(id__in=enrolled_subjects)
            else:
                # If user has no enrollments, show all subjects (for admin or testing)
                self.fields['subject'].queryset = Subject.objects.all()
        else:
            # If no user provided, show all subjects
            self.fields['subject'].queryset = Subject.objects.all()
    
    def clean_dates(self):
        dates_str = self.cleaned_data['dates']
        dates = []
        # Split by comma and clean up
        for date_str in dates_str.split(','):
            date_str = date_str.strip()
            if date_str:
                try:
                    # Validate date format
                    from datetime import datetime
                    datetime.strptime(date_str, '%Y-%m-%d')
                    dates.append(date_str)
                except ValueError:
                    raise forms.ValidationError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD.")
        if not dates:
            raise forms.ValidationError("At least one date must be selected.")
        return dates