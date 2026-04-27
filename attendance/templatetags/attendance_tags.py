from django import template


register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def ordinal(value):
    """Convert a number to its ordinal representation (1st, 2nd, 3rd, 4th)"""
    try:
        value = int(value)
        if value == 1:
            return '1st'
        elif value == 2:
            return '2nd'
        elif value == 3:
            return '3rd'
        elif value == 4:
            return '4th'
        else:
            return str(value)
    except (ValueError, TypeError):
        return str(value)

@register.filter
def filter_sem(subjects, semester):
    """Filter subjects by semester string"""
    if not subjects:
        return []
    return [s for s in subjects if str(s.semester) == str(semester)]

@register.filter
def split(value, arg):
    return value.split(arg)