import math
from rest_framework import serializers
from .models import Location,LocationRevision

class StrictInputMixin:
    def to_internal_value(self,data):
        if isinstance(data,dict):
            forbidden=set(data)-{name for name,field in self.fields.items() if not field.read_only}
            if forbidden:raise serializers.ValidationError({'detail':'Unsupported input fields','fields':sorted(forbidden)})
        return super().to_internal_value(data)

class RevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model=LocationRevision
        fields=['id','number','lat','lon','method','matched_address','confirmed','context','actor_id','created_at']

class LocationSerializer(serializers.ModelSerializer):
    current_revision=RevisionSerializer(read_only=True)
    attention=serializers.SerializerMethodField()
    key_numbers=serializers.SerializerMethodField()
    unconfirmed_tenants=serializers.SerializerMethodField()
    class Meta:
        model=Location
        fields=['id','seed_id','name','address','city','state','status','asset_type','ring_preset',
            'gla_sqft','notes','confirmed','confirmed_at','origin','source_url','source_context',
            'version','analysis_version','current_revision','created_at','updated_at','attention','screening',
            'key_numbers','unconfirmed_tenants']
    def get_key_numbers(self,obj):
        # From the LocationMetrics snapshot (prefetched in lists); never computed here.
        from django.core.exceptions import ObjectDoesNotExist
        try:row=obj.metrics_snapshot
        except ObjectDoesNotExist:return {}
        if row.analysis_version!=obj.analysis_version:return {}
        return {k:(row.values.get(k) or {}).get('value') for k in ('population','median_household_income','aadt')
            if (row.values.get(k) or {}).get('value') is not None}
    def get_unconfirmed_tenants(self,obj):
        return getattr(obj,'unconfirmed_tenant_count',None)
    def get_attention(self,obj):
        # FR-20: highest active signal severity (High, Watch) or Clear.
        from apps.insights.signals import cached_attention
        return cached_attention(obj)

class CreateSerializer(StrictInputMixin,serializers.Serializer):
    name=serializers.CharField(max_length=200)
    address=serializers.CharField(max_length=500)
    city=serializers.CharField(max_length=120,required=False,allow_blank=True)
    state=serializers.RegexField(r'^[A-Z]{2}$',required=False,allow_blank=True)
    status=serializers.ChoiceField(choices=Location.Status.choices,default='candidate')
    asset_type=serializers.ChoiceField(choices=Location.AssetType.choices,default='other')

class UpdateSerializer(StrictInputMixin,serializers.Serializer):
    expected_version=serializers.IntegerField(min_value=1)
    name=serializers.CharField(max_length=200,required=False)
    address=serializers.CharField(max_length=500,required=False)
    city=serializers.CharField(max_length=120,required=False,allow_blank=True)
    state=serializers.RegexField(r'^[A-Z]{2}$',required=False,allow_blank=True)
    status=serializers.ChoiceField(choices=Location.Status.choices,required=False)
    asset_type=serializers.ChoiceField(choices=Location.AssetType.choices,required=False)
    ring_preset=serializers.ChoiceField(choices=['1/3/5','3/5/10'],required=False)
    gla_sqft=serializers.IntegerField(min_value=1,required=False,allow_null=True)
    notes=serializers.CharField(required=False,allow_blank=True,max_length=20000)

class ConfirmationSerializer(StrictInputMixin,serializers.Serializer):
    expected_version=serializers.IntegerField(min_value=1)

class CoordinateField(serializers.FloatField):
    def to_internal_value(self,data):
        if type(data) is bool:raise serializers.ValidationError('Coordinates must be finite numbers')
        value=super().to_internal_value(data)
        if not math.isfinite(value):raise serializers.ValidationError('Coordinates must be finite numbers')
        return value

class PinSerializer(ConfirmationSerializer):
    lat=CoordinateField(min_value=-90,max_value=90)
    lon=CoordinateField(min_value=-180,max_value=180)
    confirmed=serializers.BooleanField(default=False)

class SearchSerializer(StrictInputMixin,serializers.Serializer):
    q=serializers.CharField(max_length=200)
    status=serializers.ChoiceField(choices=[*Location.Status.values,'all'],required=False)
    state=serializers.CharField(max_length=2,required=False)
    asset_type=serializers.ChoiceField(choices=Location.AssetType.choices,required=False)

class GeocodeAcceptSerializer(ConfirmationSerializer):
    candidate_index=serializers.IntegerField(min_value=0,max_value=19)
