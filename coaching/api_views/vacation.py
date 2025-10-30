# coaching/api_views/vacation.py

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import json
import datetime
from ..models import CoachVacationBlock
from ..utils import coach_is_valid # Import the helper


@login_required
@require_http_methods(["GET", "POST"])
def coach_vacation_blocks(request):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)

    coach = request.user

    if request.method == 'GET':
        blocks = CoachVacationBlock.objects.filter(
            coach=coach,
            end_date__gte=timezone.now().date()
        ).order_by('start_date')
        
        return render(request, 'coaching/partials/vacation_block_list_fragment.html', {'blocks': blocks})

    elif request.method == 'POST':
        try:
            data = request.POST if request.content_type == 'application/x-www-form-urlencoded' else json.loads(request.body)
            
            start_date = datetime.date.fromisoformat(data.get('start_date'))
            end_date = datetime.date.fromisoformat(data.get('end_date'))
            
            if start_date > end_date:
                return HttpResponse('Start date cannot be after end date.', status=400)
            if end_date < timezone.now().date():
                return HttpResponse('Cannot block dates in the past.', status=400)

            CoachVacationBlock.objects.create(
                coach=coach, start_date=start_date, end_date=end_date, reason=data.get('reason', '')
            )
            
            response = HttpResponse(status=201)
            response['HX-Trigger'] = 'block-added'
            return response

        except Exception as e:
            return HttpResponse(f"Error processing block: {e}", status=400)


@login_required
@require_http_methods(["DELETE"])
def coach_vacation_block_detail(request, block_id):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)

    get_object_or_404(CoachVacationBlock, pk=block_id, coach=request.user).delete()

    response = HttpResponse(status=200)
    response['HX-Trigger'] = 'block-deleted'
    return response