from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Allows accessing a dictionary or list item by a variable key/index in templates.
    """
    return dictionary[key]

