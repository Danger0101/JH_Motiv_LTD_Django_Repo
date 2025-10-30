# coaching/api_views/offerings.py

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError 
from django.core.exceptions import ValidationError
import json
from ..models import CoachOffering
from ..utils import coach_is_valid # Import the helper


@login_required
@require_http_methods(["GET", "POST"])
def coach_offerings_list_create(request):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)
    
    coach = request.user
    
    if request.method == 'GET':
        offerings = CoachOffering.objects.filter(coach=coach).order_by('name')
        
        # HTMX FIX: Return HTML fragment, not raw JSON
        return render(request, 'coaching/partials/offerings_list_fragment.html', {'offerings': offerings})

    elif request.method == 'POST':
        try:
            data = request.POST 
            
            if not all([data.get('name'), data.get('slug'), data.get('duration_minutes')]):
                return JsonResponse({"error": "Missing required fields."}, status=400)
            
            if int(data['duration_minutes']) <= 0:
                return JsonResponse({"error": "Duration must be positive."}, status=400)

            CoachOffering.objects.create(
                coach=coach,
                name=data['name'],
                slug=data['slug'],
                description=data.get('description', ''),
                duration_minutes=data['duration_minutes'],
                price=data.get('price', 0.00),
                is_active=data.get('is_active', 'off') == 'on'
            )
            
            response = HttpResponse(status=201)
            response['HX-Trigger'] = 'offering-updated'
            return response
        
        except IntegrityError:
            return JsonResponse({"error": "An offering with that slug already exists for this coach."}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Creation failed: {e}"}, status=400)


@login_required
@require_http_methods(["GET", "PUT", "PATCH", "DELETE"])
@csrf_exempt 
def coach_offerings_detail(request, offering_id):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)

    offering = get_object_or_404(CoachOffering, pk=offering_id, coach=request.user)

    if request.method == 'GET':
        data = {"id": offering.id, "name": offering.name, "slug": offering.slug, 
                "duration_minutes": offering.duration_minutes, "price": str(offering.price), 
                "is_active": offering.is_active}
        return JsonResponse(data, status=200)

    elif request.method in ['PUT', 'PATCH']:
        data = json.loads(request.body)
        
        for key, value in data.items():
            if key in ['name', 'slug', 'description', 'duration_minutes', 'price', 'is_active']:
                setattr(offering, key, value)
        
        try:
            offering.full_clean()
            offering.save()
            
            response = JsonResponse({"success": True, "message": "Offering updated."}, status=200)
            response['HX-Trigger'] = 'offering-updated'
            return response
        
        except (ValidationError, IntegrityError) as e:
            error_msg = getattr(e, 'message_dict', str(e))
            return JsonResponse({"error": error_msg}, status=400)


    elif request.method == 'DELETE':
        offering.delete()
        response = HttpResponse(status=200)
        response['HX-Trigger'] = 'offering-updated'
        return response