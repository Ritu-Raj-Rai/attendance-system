"""
College-specific configuration for AI Document Processing
Contains all edge cases, patterns, and college-specific rules
"""

# SEMESTER CONFIGURATION
SEMESTER_CONFIG = {
    1: {
        "name": "Semester 1",
        "type": "odd",  # odd semester
        "keywords": ["Sem-1", "1st Sem", "Semester-1", "Odd Sem"],
    },
    2: {
        "name": "Semester 2",
        "type": "even",  # even semester
        "keywords": ["Sem-2", "2nd Sem", "Semester-2", "Even Sem"],
    },
    3: {
        "name": "Semester 3",
        "type": "odd",
        "keywords": ["Sem-3", "3rd Sem", "Semester-3", "Odd Sem"],
    },
    4: {
        "name": "Semester 4",
        "type": "even",
        "keywords": ["Sem-4", "4th Sem", "Semester-4", "Even Sem"],
    },
    5: {
        "name": "Semester 5",
        "type": "odd",
        "keywords": ["Sem-5", "5th Sem", "Semester-5", "Odd Sem"],
    },
    6: {
        "name": "Semester 6",
        "type": "even",
        "keywords": ["Sem-6", "6th Sem", "Semester-6", "Even Sem"],
    },
    7: {
        "name": "Semester 7",
        "type": "odd",
        "keywords": ["Sem-7", "7th Sem", "Semester-7", "Odd Sem"],
    },
    8: {
        "name": "Semester 8",
        "type": "even",
        "keywords": ["Sem-8", "8th Sem", "Semester-8", "Even Sem"],
    },
}

# SUBJECT CONFIGURATION
SUBJECT_CONFIG = {
    "ICP": {
        "code": "I01",
        "name": "Integrated Circuit Programming",
        "semesters": [1, 2, 3, 4],  # Available in these semesters
    },
    "coaa": {
        "code": "C01",
        "name": "Computer Organization and Architecture",
        "semesters": [1, 2, 3, 4],
    },
    "AAD": {
        "code": "A01",
        "name": "Analysis and Design",
        "semesters": [1, 2, 3, 4],
    },
    "CSW": {
        "code": "C02",
        "name": "Communication Software",
        "semesters": [1, 2, 3, 4],
    },
    "IM": {
        "code": "I02",
        "name": "Information Management",
        "semesters": [3, 4, 5, 6],
    },
}

# TIME SLOT CONFIGURATION
TIME_SLOTS = [
    "08:00 AM",
    "08:15 AM",
    "09:00 AM",
    "09:15 AM",
    "10:00 AM",
    "10:15 AM",
    "11:00 AM",
    "11:15 AM",
    "12:00 PM",
    "12:15 PM",
    "01:00 PM",
    "01:15 PM",
    "02:00 PM",
    "02:15 PM",
    "03:00 PM",
    "03:15 PM",
    "04:00 PM",
    "04:15 PM",
    "05:00 PM",
    "05:15 PM",
    "06:00 PM",
]

# ROOM PATTERNS
ROOM_PATTERNS = {
    "pattern": r"[A-Z][-]?\d{2,3}",  # Matches E-406, E406, etc.
    "buildings": {
        "A": "Building A",
        "B": "Building B",
        "C": "Building C",
        "E": "Engineering Block",
        "L": "Lab Block",
    }
}

# HOLIDAY KEYWORDS
HOLIDAY_KEYWORDS = [
    "Holiday",
    "Break",
    "Vacation",
    "Closed",
    "No Class",
    "Off",
    "Leave",
    "Exam Break",
    "Mid Semester",
    "End Semester",
    "Revision Period",
    "Non-teaching Week",
    "Semester Break",
    "Preparation Leave",
]

# OPTIONAL HOLIDAY KEYWORDS - For holidays that are optional/elective
OPTIONAL_HOLIDAY_KEYWORDS = [
    "Optional",
    "Elective",
    "Optional Holiday",
    "Can take",
    "May apply",
    "If interested",
    "As per choice",
    "Discretionary",
    "May be availed",
    "Student choice",
    "Personal",
    "Flexible",
]

# HOLIDAY TYPES - Categories of holidays
HOLIDAY_TYPES = {
    "mandatory": {
        "name": "Mandatory Holiday",
        "description": "College closed, all have off",
        "keywords": ["holiday", "break", "vacation", "closed", "exam break"],
        "affects_attendance": True,
    },
    "optional": {
        "name": "Optional Holiday",
        "description": "Student can choose to take or attend",
        "keywords": ["optional", "elective", "can take", "may apply"],
        "affects_attendance": False,  # Student choice
    },
    "festival": {
        "name": "Festival Holiday",
        "description": "Religious/cultural festival",
        "keywords": ["festival", "celebration", "religious", "cultural"],
        "affects_attendance": True,
    },
    "exam_break": {
        "name": "Exam Break",
        "description": "No classes during exam period",
        "keywords": ["exam break", "examination", "test period", "assessment"],
        "affects_attendance": True,
    },
    "vacation": {
        "name": "Vacation Period",
        "description": "Summer/semester break",
        "keywords": ["vacation", "summer break", "semester break", "winter break"],
        "affects_attendance": True,
    },
    "special": {
        "name": "Special Holiday",
        "description": "Special occasion or event",
        "keywords": ["special", "event", "occasion", "anniversary"],
        "affects_attendance": True,
    },
}


# EXAM KEYWORDS
EXAM_KEYWORDS = [
    "Exam",
    "Test",
    "Assessment",
    "Quiz",
    "Evaluation",
    "Practical",
    "Viva",
    "Thesis",
    "Project Review",
    "Final Exam",
    "Mid Exam",
]

# LAB KEYWORDS - Classes that should count as 1 class regardless of duration
LAB_KEYWORDS = [
    "Lab",
    "Laboratory",
    "Practical",
    "Workshop",
    "P", # Often used as shorthand for Practical/Lab
]

# ACADEMIC CALENDAR EVENT TYPES
CALENDAR_EVENT_TYPES = {
    "holiday": "Holiday",
    "exam": "Exam",
    "assignment": "Assignment Due",
    "project": "Project Deadline",
    "seminar": "Seminar",
    "workshop": "Workshop",
    "class_start": "Classes Start",
    "class_end": "Classes End",
    "registration": "Registration",
    "result_declaration": "Result Declaration",
}

# DATE FORMATS TO TRY (in order of preference)
DATE_FORMATS = [
    "%d-%m-%Y",      # 25-04-2026
    "%d/%m/%Y",      # 25/04/2026
    "%d-%m-%y",      # 25-04-26
    "%d/%m/%y",      # 25/04/26
    "%B %d, %Y",     # April 25, 2026
    "%b %d, %Y",     # Apr 25, 2026
    "%d %B %Y",      # 25 April 2026
    "%d %b %Y",      # 25 Apr 2026
    "%Y-%m-%d",      # 2026-04-25
]

# VALIDATION RULES
VALIDATION_RULES = {
    "min_classes_per_week": 3,  # Each subject should have at least 3 classes/week
    "max_classes_per_day": 5,   # Maximum classes in a single day
    "min_semester_weeks": 14,   # Minimum weeks in a semester
    "max_semester_weeks": 20,   # Maximum weeks in a semester
    "valid_hours_start": 8,     # Classes should not start before 8 AM
    "valid_hours_end": 18,      # Classes should not end after 6 PM
}


def get_semester_info(current_semester):
    """Get current semester information"""
    return SEMESTER_CONFIG.get(current_semester, {})


def get_semester_type(current_semester):
    """Get if current semester is even or odd"""
    return SEMESTER_CONFIG.get(current_semester, {}).get("type")


def get_semester_keywords(current_semester):
    """Get keywords to identify the semester"""
    return SEMESTER_CONFIG.get(current_semester, {}).get("keywords", [])


def is_valid_subject_for_semester(subject_code, semester):
    """Check if subject is valid for given semester"""
    for subject, config in SUBJECT_CONFIG.items():
        if config["code"] == subject_code:
            return semester in config["semesters"]
    return False


def get_all_keywords():
    """Get all keyword patterns for identification"""
    return {
        "holidays": HOLIDAY_KEYWORDS,
        "exams": EXAM_KEYWORDS,
    }


def is_optional_holiday(holiday_name):
    """Check if a holiday is optional/elective"""
    if not holiday_name:
        return False
    name_upper = holiday_name.upper()
    return any(keyword.upper() in name_upper for keyword in OPTIONAL_HOLIDAY_KEYWORDS)


def classify_holiday(holiday_name):
    """
    Classify a holiday into a type (mandatory, optional, festival, exam_break, vacation, special)
    Returns: (type_key, type_info)
    
    Checks specific types first (festival, exam_break, vacation) before generic types (mandatory)
    """
    if not holiday_name:
        return "mandatory", HOLIDAY_TYPES["mandatory"]
    
    name_upper = holiday_name.upper()
    
    # Check for optional first (highest priority)
    if is_optional_holiday(holiday_name):
        return "optional", HOLIDAY_TYPES["optional"]
    
    # Check specific types in order of specificity (most specific first)
    # This ensures "Diwali Festival Holiday" is classified as festival, not just mandatory
    type_order = ["festival", "exam_break", "vacation", "special", "mandatory"]
    
    for type_key in type_order:
        type_info = HOLIDAY_TYPES.get(type_key, {})
        keywords = type_info.get("keywords", [])
        
        if any(keyword.upper() in name_upper for keyword in keywords):
            return type_key, type_info
    
    # Default to mandatory if no specific match
    return "mandatory", HOLIDAY_TYPES["mandatory"]


def affects_attendance(holiday_type):
    """Check if a holiday type affects attendance calculation"""
    if isinstance(holiday_type, str):
        type_info = HOLIDAY_TYPES.get(holiday_type, {})
        return type_info.get("affects_attendance", True)
    elif isinstance(holiday_type, dict):
        return holiday_type.get("affects_attendance", True)
    return True


def is_lab_class(subject_name):
    """Check if a class is a lab session (should count as 1 class regardless of duration)"""
    if not subject_name:
        return False
    subject_upper = subject_name.upper()
    return any(keyword.upper() in subject_upper for keyword in LAB_KEYWORDS)


def calculate_class_count(start_time, end_time, subject_name=None):
    """
    Calculate number of classes based on duration and class type
    
    Rules:
    - Lab classes: Always 1 class (regardless of duration)
    - Regular classes: 1 hour = 1 class, 2 hours = 2 classes, etc.
    
    Args:
        start_time: Start time as "HH:MM" (e.g., "09:00")
        end_time: End time as "HH:MM" (e.g., "10:00")
        subject_name: Subject name to detect if it's a lab
        
    Returns:
        int: Number of classes
    """
    try:
        # Parse times
        start_parts = start_time.split(':')
        end_parts = end_time.split(':')
        
        start_hour = int(start_parts[0])
        start_min = int(start_parts[1]) if len(start_parts) > 1 else 0
        
        end_hour = int(end_parts[0])
        end_min = int(end_parts[1]) if len(end_parts) > 1 else 0
        
        # Calculate duration in minutes
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        # Handle crossing midnight (unlikely in college but safe)
        if end_minutes < start_minutes:
            end_minutes += 24 * 60
        
        duration_minutes = end_minutes - start_minutes
        
        # If it's a lab, always return 1
        if subject_name and is_lab_class(subject_name):
            return 1
        
        # For regular classes: divide by 60 minutes per class, round up
        # So 1 hour = 1 class, 2 hours = 2 classes, 1.5 hours = 2 classes, etc.
        import math
        class_count = math.ceil(duration_minutes / 60)
        
        return max(1, class_count)  # At least 1 class
        
    except Exception as e:
        # If parsing fails, return 1 as default
        return 1
