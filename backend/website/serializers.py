from rest_framework import serializers
from .models import WebsiteProperty


class WebsitePropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteProperty
        fields = ['key', 'value']
