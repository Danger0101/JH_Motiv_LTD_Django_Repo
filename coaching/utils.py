# coaching/utils.py

def coach_is_valid(user):
    """Helper: Checks if the user is authenticated and is a coach."""
    return user.is_authenticated and user.is_coach