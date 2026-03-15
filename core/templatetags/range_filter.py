"""Custom template filters for range-based iteration in templates."""

from django import template

register = template.Library()

@register.filter
def times(number):
    return range(number)
