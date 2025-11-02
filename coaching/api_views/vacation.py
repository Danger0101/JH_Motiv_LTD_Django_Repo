# coaching/api_views/vacation.py

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import json
import datetime
from ..models import CoachVacationBlock, CoachingSession, RescheduleRequest
from ..utils import coach_is_valid

@login_required
@require_http_methods(["GET", "POST"])
def coach_vacation_blocks(request):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)
    
    coach = request.user
    
    if request.method == 'GET':
        blocks = CoachVacationBlock.objects.filter(coach=coach).order_by('start_date')
        return render(request, 'coaching/partials/_vacation_blocks_list.html', {'vacation_blocks': blocks})

    elif request.method == 'POST':
        try:
            data = request.POST
            start_date = datetime.date.fromisoformat(data['start_date'])
            end_date = datetime.date.fromisoformat(data['end_date'])
            reason = data.get('reason', '')
            override_allowed = data.get('override_allowed') == 'on'

            if start_date > end_date:
                raise ValueError("Start date cannot be after end date.")
            if end_date < timezone.now().date():
                raise ValueError("Cannot set a vacation block in the past.")

            vacation_block = CoachVacationBlock.objects.create(
                coach=coach, 
                start_date=start_date, 
                end_date=end_date, 
                reason=reason,
                override_allowed=override_allowed
            )

            # Find clashing sessions
            clashing_sessions = CoachingSession.objects.filter(
                coach=coach,
                start_time__date__range=(start_date, end_date),
                status='BOOKED'
            )

            for session in clashing_sessions:
                session.status = 'PENDING'
                session.save()
                RescheduleRequest.objects.create(session=session)

            response = HttpResponse(status=201)
            response['HX-Trigger'] = 'vacation-block-updated'
            return response
        
        except Exception as e:
            return HttpResponse(f"Error: {e}", status=400)


@login_required
@require_http_methods(["DELETE"])
def coach_vacation_block_detail(request, block_id):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)

    get_object_or_404(CoachVacationBlock, pk=block_id, coach=request.user).delete()

    response = HttpResponse(status=200)
    response['HX-Trigger'] = 'block-deleted'
    return response