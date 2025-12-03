from django.db import models

class Fact(models.Model):
    statistic_description = models.TextField(blank=True, null=True)
    source_title = models.CharField(max_length=100, blank=True, null=True)
    source_link = models.URLField(max_length=200, blank=True, null=True)

    def __str__(self):
        return self.statistic_description if self.statistic_description else "Fact"