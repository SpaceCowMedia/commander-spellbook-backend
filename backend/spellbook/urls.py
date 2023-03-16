from django.urls import include, path, re_path
from .hybridrouter import HybridRouter
from . import views
from website.urls import router as website_router

router = HybridRouter()
router.register(r'variants', views.VariantViewSet, basename='variants')
router.register(r'features', views.FeatureViewSet, basename='features')
router.register(r'combos', views.ComboViewSet, basename='combos')
router.register(r'cards', views.CardViewSet, basename='cards')
router.register(r'templates', views.TemplateViewSet, basename='templates')
router.add_api_view(r'find-my-combos', re_path(r'find-my-combos', views.find_my_combos, name='find-my-combos'))
router.registry.extend(website_router.registry)

urlpatterns = [
    path('', include(router.urls))
]
