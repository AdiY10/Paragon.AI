from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import SourceDefinition
from .health import health_payload

@api_view(['GET'])
def source_list(request):
    fields = ['id','name','provider','purpose','coverage','documentation_url','licence','attribution','cadence','stale_after_days','privacy_note','adapter_version','catalog_version']
    result=[]
    for source in SourceDefinition.objects.prefetch_related('health_scopes__latest_snapshot'):
        item={field:getattr(source,field) for field in fields}
        scopes=[health_payload(scope) for scope in source.health_scopes.all()]
        statuses={scope['status'] for scope in scopes}
        item['status']=next((s for s in ['Failing','Stale','Not checked','OK'] if s in statuses),'Not checked')
        item['health_scopes']=scopes
        result.append(item)
    return Response(result)
