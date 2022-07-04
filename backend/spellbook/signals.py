from django.db.models.signals import m2m_changed, post_delete
from django.dispatch import receiver
from .models import Card, Feature, Combo
