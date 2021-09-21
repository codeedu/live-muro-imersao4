from django.db import models
from django.utils.translation import gettext_lazy as _

class Payment(models.Model):
    order_id = models.CharField(max_length=255)
    client_name = models.CharField(max_length=255)
    product_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)