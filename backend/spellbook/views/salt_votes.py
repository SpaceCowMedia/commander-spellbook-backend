from django.conf import settings
from django.db.models import Exists, FloatField, OuterRef
from django.db.models.functions import Cast, Coalesce, Greatest, Least, Power, Random
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_filters.filters import CharFilter
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from api_docs import SALT_VOTES_DESCRIPTION
from spellbook.models import PreSerializedSerializer, SaltVote, Variant, live_salt_annotations, salt_window_start
from spellbook.serializers import SaltVoteSerializer, VariantSerializer


class SaltVotePermissions(permissions.DjangoModelPermissionsOrAnonReadOnly):
    perms_map = permissions.DjangoModelPermissionsOrAnonReadOnly.perms_map | {
        'PUT': ['%(app_label)s.add_%(model_name)s', '%(app_label)s.change_%(model_name)s'],
    }


class SaltVoteFilterSet(FilterSet):
    variant = CharFilter(field_name='variant_id', label='Filters for the vote on the variant with the given id.')


class SaltVoteQueueParameters(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=50, default=10, help_text='Number of variants to return.')


class SaltVoteViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    __doc__ = SALT_VOTES_DESCRIPTION
    serializer_class = SaltVoteSerializer
    permission_classes = [SaltVotePermissions]
    filter_backends = [DjangoFilterBackend]
    filterset_class = SaltVoteFilterSet
    lookup_field = 'variant_id'
    lookup_url_kwarg = 'variant'

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return SaltVote.objects.none()
        return SaltVote.objects \
            .filter(user=self.request.user) \
            .annotate(**live_salt_annotations(salt_window_start())) \
            .order_by('-updated', 'variant_id')

    @extend_schema(responses={200: SaltVoteSerializer, 201: SaltVoteSerializer})
    def update(self, request: Request, *args, **kwargs):
        variant_id = self.kwargs[self.lookup_url_kwarg]
        if not Variant.objects.filter(pk=variant_id, status__in=Variant.public_statuses()).exists():
            raise NotFound
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, created = SaltVote.objects.update_or_create(user=request.user, variant_id=variant_id, defaults={'score': serializer.validated_data['score']})
        vote = self.get_queryset().get(variant_id=variant_id)
        return Response(self.get_serializer(vote).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(parameters=[SaltVoteQueueParameters], responses={200: VariantSerializer(many=True)})
    @action(detail=False, methods=['get'], pagination_class=None, filter_backends=[])
    def queue(self, request: Request):
        parameters = SaltVoteQueueParameters(data=request.query_params)
        parameters.is_valid(raise_exception=True)
        variants = Variant.serialized_objects.filter(status__in=Variant.public_statuses(), legal_commander=True, spoiler=False)
        if request.user.is_authenticated:
            variants = variants.exclude(Exists(SaltVote.objects.filter(user=request.user, variant_id=OuterRef('pk'), updated__gte=salt_window_start())))
        target = settings.SALT_VOTE_TARGET_COUNT
        boost = Power(Cast(Coalesce('popularity', 0), FloatField()) + 1.0, settings.SALT_VOTE_QUEUE_POPULARITY_EXPONENT)
        undersampling = 1.0 - Cast(Least('salt_vote_count', target), FloatField()) / target
        weight = Greatest(boost * undersampling, 1.0)
        # Efraimidis–Spirakis weighted sampling without replacement: https://doi.org/10.1016/j.ipl.2005.11.003
        drawn = variants.order_by(Power(Random(), 1.0 / weight).desc())[:parameters.validated_data['limit']]
        return Response(PreSerializedSerializer(drawn, many=True).data)
