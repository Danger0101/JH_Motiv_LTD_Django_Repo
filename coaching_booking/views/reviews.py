from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import ClientOfferingEnrollment, CoachReview
from ..forms import CoachReviewForm

@login_required
def submit_coach_review(request, enrollment_id):
    enrollment = get_object_or_404(ClientOfferingEnrollment, id=enrollment_id, client=request.user)
    
    # Ensure only completed enrollments can be reviewed
    if not enrollment.is_complete:
        messages.error(request, "You can only review completed programs.")
        return redirect('accounts:account_profile')

    # Check for existing review to allow editing
    try:
        review = enrollment.review
    except CoachReview.DoesNotExist:
        review = None

    if request.method == 'POST':
        form = CoachReviewForm(request.POST, instance=review)
        if form.is_valid():
            review = form.save(commit=False)
            review.enrollment = enrollment
            review.client = request.user
            review.coach = enrollment.coach
            review.save()
            messages.success(request, "Review submitted successfully.")
            return redirect('accounts:account_profile')
    else:
        form = CoachReviewForm(instance=review)

    return render(request, 'coaching_booking/review_form.html', {
        'form': form, 
        'enrollment': enrollment
    })