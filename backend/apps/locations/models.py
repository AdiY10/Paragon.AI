import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from apps.sources.models import ImmutableQuerySet


class Location(models.Model):
    class Status(models.TextChoices):
        OWNED='owned','Owned'
        CANDIDATE='candidate','Candidate'
        ARCHIVED='archived','Archived'
    class AssetType(models.TextChoices):
        RETAIL_CENTER='retail_center','Retail center'
        SINGLE_TENANT='single_tenant_retail','Single-tenant retail'
        OFFICE='office','Office'
        MIXED_USE='mixed_use','Mixed-use'
        OTHER='other','Other'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    seed_id=models.CharField(max_length=3,null=True,blank=True,unique=True)
    name=models.CharField(max_length=200)
    address=models.CharField(max_length=500)
    city=models.CharField(max_length=120,blank=True)
    state=models.CharField(max_length=2,blank=True)
    status=models.CharField(max_length=16,choices=Status.choices,default=Status.CANDIDATE)
    asset_type=models.CharField(max_length=32,choices=AssetType.choices,default=AssetType.OTHER)
    ring_preset=models.CharField(max_length=8,choices=[('1/3/5','1/3/5 miles'),('3/5/10','3/5/10 miles')],default='1/3/5')
    gla_sqft=models.PositiveIntegerField(null=True,blank=True,validators=[MinValueValidator(1)])
    notes=models.TextField(blank=True)
    confirmed=models.BooleanField(default=False)
    confirmed_at=models.DateTimeField(null=True,blank=True)
    confirmed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='+')
    origin=models.CharField(max_length=16,choices=[('public_seed','Public seed'),('user','User-provided')],default='user')
    source_url=models.URLField(max_length=2048,blank=True)
    source_context=models.JSONField(default=dict,blank=True)
    seed_batch=models.ForeignKey("SeedImportBatch",null=True,blank=True,on_delete=models.PROTECT,related_name="locations")
    version=models.PositiveIntegerField(default=1)
    analysis_version=models.PositiveIntegerField(default=1)
    current_revision=models.ForeignKey('LocationRevision',null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='+')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['name','id']
        constraints=[models.CheckConstraint(condition=models.Q(gla_sqft__isnull=True)|models.Q(gla_sqft__gt=0),name='location_gla_positive'),
            models.CheckConstraint(condition=models.Q(confirmed=False)|models.Q(confirmed_at__isnull=False),name='location_confirmation_dated')]
    def clean(self):
        if self.current_revision_id and self.current_revision.location_id!=self.pk:
            raise ValidationError('Current pin revision belongs to a different location')


class LocationRevision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    location=models.ForeignKey(Location,on_delete=models.PROTECT,related_name='revisions')
    number=models.PositiveIntegerField()
    lat=models.FloatField(null=True,blank=True)
    lon=models.FloatField(null=True,blank=True)
    method=models.CharField(max_length=32,choices=[(v,v) for v in ['unplaced','seed_reference','census_exact','census_non_exact','census_interpolated','nominatim','manual']])
    matched_address=models.CharField(max_length=500,blank=True)
    confirmed=models.BooleanField(default=False)
    context=models.JSONField(default=dict)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True)
    objects=ImmutableQuerySet.as_manager()
    class Meta:
        ordering=['number']
        constraints=[models.UniqueConstraint(fields=['location','number'],name='location_revision_number_unique'),
            models.CheckConstraint(condition=(models.Q(lat__isnull=True)&models.Q(lon__isnull=True))|(models.Q(lat__isnull=False)&models.Q(lon__isnull=False)&models.Q(lat__gte=-90,lat__lte=90,lon__gte=-180,lon__lte=180)),name='location_revision_coordinates_valid')]
    def save(self,*args,**kwargs):
        if not self._state.adding:raise ValueError('Pin revision history is immutable')
        super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValueError('Pin revision history cannot be deleted')


class LocationAuditEvent(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    location=models.ForeignKey(Location,on_delete=models.PROTECT,related_name='audit_events')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    action=models.CharField(max_length=32)
    before=models.JSONField(default=dict)
    after=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['created_at','id']


class SeedImportBatch(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    sha256=models.CharField(max_length=64,unique=True)
    source_as_of=models.DateField()
    imported_at=models.DateTimeField(auto_now_add=True)
    rows=models.PositiveIntegerField()
    created_locations=models.PositiveIntegerField()
    objects=ImmutableQuerySet.as_manager()
    def save(self,*args,**kwargs):
        if not self._state.adding:raise ValueError('Seed import history is immutable')
        super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValueError('Seed import history cannot be deleted')


class GeocodeLookup(models.Model):
    """Immutable private preview; accepting it is a separate pin revision."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    location=models.ForeignKey(Location,on_delete=models.PROTECT,related_name='geocode_lookups')
    requested_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    requested_version=models.PositiveIntegerField()
    address_hash=models.CharField(max_length=64)
    snapshot=models.ForeignKey('sources.SourceSnapshot',on_delete=models.PROTECT)
    status=models.CharField(max_length=16,choices=[('matched','Matched'),('ambiguous','Ambiguous'),('no_match','No match')])
    candidates=models.JSONField()
    benchmark=models.JSONField()
    vintage=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
    expires_at=models.DateTimeField()
    checked_at=models.DateTimeField()
    objects=ImmutableQuerySet.as_manager()
    class Meta:
        ordering=['-created_at','id']
        constraints=[models.UniqueConstraint(fields=['location','requested_by','requested_version','snapshot','checked_at'],name='location_geocode_preview_unique')]
        indexes=[models.Index(fields=['location','address_hash','expires_at'])]
    def save(self,*args,**kwargs):
        if not self._state.adding:raise ValueError('Geocode lookup evidence is immutable')
        super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValueError('Geocode lookup evidence cannot be deleted')
