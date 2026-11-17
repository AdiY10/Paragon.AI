from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import SourceDefinition

@api_view(['GET'])
def source_list(request):
    fields = ['id','name','provider','purpose','coverage','documentation_url','licence','attribution','cadence','stale_after_days','privacy_note','adapter_version','catalog_version']
    return Response(list(SourceDefinition.objects.values(*fields)))
