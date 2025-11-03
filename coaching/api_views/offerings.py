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
        # This view now ONLY handles the "My Offerings" tab.
        # It shows offerings the coach is part of.
        offerings = CoachOffering.objects.filter(coaches=coach).prefetch_related('pre_session_questions').order_by('name')
        return render(request, 'coaching/partials/coach/_my_offerings_list.html', {'offerings': offerings})

    elif request.method == 'POST':
        try:
            data = request.POST 
            offering_id = data.get('offering_id')
            
            # Prepare data for create or update
            offering_data = {
                'name': data.get('name'),
                'description': data.get('description', ''),
                'price': data.get('price', 0.00),
                'credits_granted': data.get('credits_granted', 1),
                'duration_months': data.get('duration_months', 3),
                'is_active': data.get('is_active') == 'on',
                'is_full_day': data.get('is_full_day') == 'on',
                'duration_minutes': data.get('duration_minutes') if data.get('duration_minutes') else None,
                'terms_and_conditions': data.get('terms_and_conditions', ''),
            }

            if offering_id: # This is an UPDATE
                offering = get_object_or_404(CoachOffering, pk=offering_id, coaches=coach)
                for key, value in offering_data.items():
                    setattr(offering, key, value)
                offering.full_clean()
                offering.save()
            else: # This is a CREATE
                offering = CoachOffering(**offering_data)
                offering.full_clean()
                offering.save()
                offering.coaches.add(coach)

            # Handle Pre-session Questions
            question_texts = request.POST.getlist('pre_session_questions')
            offering.pre_session_questions.all().delete() # Simple approach: delete and re-create
            for i, text in enumerate(question_texts):
                if text.strip():
                    PreSessionQuestion.objects.create(offering=offering, text=text, order=i)

            # After saving, re-render the form to show the updated state
            offerings = CoachOffering.objects.filter(coaches=coach).prefetch_related('pre_session_questions').order_by('name')
            return render(request, 'coaching/partials/coach/_my_offerings_list.html', {'offerings': offerings, 'success_message': 'Offering saved successfully!'})
        
        except IntegrityError:
            return HttpResponse("An offering with that name already exists (slug must be unique).", status=400)
        except ValidationError as e:
            # Convert validation error to a user-friendly message
            error_message = ". ".join(e.messages)
            return HttpResponse(error_message, status=400)
        except Exception as e:
            return HttpResponse(f"An unexpected error occurred: {e}", status=400)


@login_required
@require_http_methods(["GET", "PUT", "PATCH", "DELETE"])
@csrf_exempt 
def coach_offerings_detail(request, offering_id):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)

    offering = get_object_or_404(CoachOffering, pk=offering_id, coaches=request.user)

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

@login_required
@require_http_methods(["POST"])
def add_coach_to_offering(request, offering_id):
    """Allows a coach to add themselves to an offering."""
    if not coach_is_valid(request.user):
        return HttpResponse("Unauthorized", status=403)

    offering = get_object_or_404(CoachOffering, id=offering_id)
    offering.coaches.add(request.user)
    
    # This response is for HTMX to replace the entire "All Offerings" list
    # We re-run the logic from the all_offerings_list_view to get the updated lists
    # Fetch ALL offerings, not just active ones, so coaches can see and rejoin inactive ones.
    all_offerings = CoachOffering.objects.prefetch_related('coaches').order_by('name')
    
    # Separate offerings into two lists based on the coach's participation
    joined_offerings = all_offerings.filter(coaches=request.user)
    not_joined_offerings = all_offerings.exclude(coaches=request.user)

    context = {'joined_offerings': joined_offerings, 'not_joined_offerings': not_joined_offerings}
    return render(request, 'coaching/partials/coach/_all_offerings_list.html', context)


@login_required
@require_http_methods(["GET"])
def all_offerings_list_view(request):
    """
    Renders a list of ALL active offerings, allowing a coach to see which ones
    they can join or leave.
    """
    if not coach_is_valid(request.user):
        return HttpResponse("Unauthorized", status=403)
    
    # Fetch ALL offerings, not just active ones, so coaches can see and rejoin inactive ones.
    all_offerings = CoachOffering.objects.prefetch_related('coaches').order_by('name')
    
    # Separate offerings into two lists based on the coach's participation
    joined_offerings = all_offerings.filter(coaches=request.user)
    not_joined_offerings = all_offerings.exclude(coaches=request.user)

    context = {'joined_offerings': joined_offerings, 'not_joined_offerings': not_joined_offerings}
    
    return render(request, 'coaching/partials/coach/_all_offerings_list.html', context)

@login_required
@require_http_methods(["POST"])
def remove_coach_from_offering(request, offering_id):
    """Allows a coach to remove themselves from an offering."""
    if not coach_is_valid(request.user):
        return HttpResponse("Unauthorized", status=403)

    offering = get_object_or_404(CoachOffering, id=offering_id)
    offering.coaches.remove(request.user)

    # This response is for HTMX to replace the entire "All Offerings" list
    # We re-run the logic from the all_offerings_list_view to get the updated lists
    # Fetch ALL offerings, not just active ones, so coaches can see and rejoin inactive ones.
    all_offerings = CoachOffering.objects.prefetch_related('coaches').order_by('name')
    
    # Separate offerings into two lists based on the coach's participation
    joined_offerings = all_offerings.filter(coaches=request.user)
    not_joined_offerings = all_offerings.exclude(coaches=request.user)

    context = {'joined_offerings': joined_offerings, 'not_joined_offerings': not_joined_offerings}
    return render(request, 'coaching/partials/coach/_all_offerings_list.html', context)