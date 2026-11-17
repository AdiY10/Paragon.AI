from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

@login_not_required
def health(request):
    return JsonResponse({'status': 'ok'})

def application(request):
    return HttpResponse('Paragon Radar · Application foundation')

@api_view(['GET'])
def session(request):
    return Response({'email': request.user.email, 'role': request.membership.role})
