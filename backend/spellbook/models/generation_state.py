from django.db import models


class VariantGenerationFingerprints(models.Model):
    '''
    Stores the input fingerprints of every entity involved in variant generation,
    as computed during the last successful generation run.
    Used by incremental generation to detect which entities changed since then.
    There is one row per entity kind, holding a mapping of entity id to fingerprint hash.
    '''
    id: int
    kind = models.CharField(max_length=32, unique=True, blank=False, help_text='Entity kind these fingerprints belong to')
    fingerprints = models.JSONField(help_text='Mapping of entity id to input fingerprint hash')
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = 'variant generation fingerprints'
        verbose_name_plural = 'variant generation fingerprints'
        default_manager_name = 'objects'

    def __str__(self):
        return f'Fingerprints for {self.kind}'
