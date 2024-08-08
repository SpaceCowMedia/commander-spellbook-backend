from django.urls import include, path, re_path
from common.hybridrouter import HybridRouter
from . import views

router = HybridRouter()
router.register(r'variants', views.VariantViewSet, basename='variants')
router.register(r'features', views.FeatureViewSet, basename='features')
router.register(r'cards', views.CardViewSet, basename='cards')
router.register(r'templates', views.TemplateViewSet, basename='templates')
router.register(r'variant-suggestions', views.VariantSuggestionViewSet, basename='variant-suggestions')
router.register(r'variant-aliases', views.VariantAliasViewSet, basename='variant-aliases')
router.add_api_view(r'find-my-combos', re_path(r'find-my-combos', views.FindMyCombosView.as_view(), name='find-my-combos'))

urlpatterns = [
    path('', include(router.urls))
]
