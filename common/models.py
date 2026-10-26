from django.db import models


class TimestampedModel(models.Model):
    data_origin = "SIMULATED_API"
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
