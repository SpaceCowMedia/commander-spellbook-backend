from .template_serializer import TemplateSerializer


class TemplateDetailSerializer(TemplateSerializer):
    class Meta(TemplateSerializer.Meta):
        fields = [
            *TemplateSerializer.Meta.fields,
            'variant_count',
        ]
