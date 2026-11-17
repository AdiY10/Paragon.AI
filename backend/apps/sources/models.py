from django.db import models


class SourceDefinition(models.Model):
    id = models.CharField(primary_key=True, max_length=6)
    name = models.CharField(max_length=160)
    provider = models.CharField(max_length=160)
    purpose = models.TextField()
    coverage = models.TextField()
    documentation_url = models.URLField()
    licence = models.TextField()
    attribution = models.TextField()
    cadence = models.CharField(max_length=32)
    stale_after_days = models.PositiveSmallIntegerField(null=True, blank=True)
    privacy_note = models.TextField()
    adapter_version = models.CharField(max_length=32, default='unimplemented')
    catalog_version = models.PositiveIntegerField()

    class Meta:
        ordering = ['id']
        constraints = [models.CheckConstraint(condition=models.Q(id__regex=r'^SRC-\d{2}$'), name='source_identifier_valid')]
