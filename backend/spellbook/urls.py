from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views
from website.urls import router as website_router

router = DefaultRouter()
router.register(r'variants', views.VariantViewSet, basename='variants')
router.register(r'features', views.FeatureViewSet, basename='features')
router.register(r'combos', views.ComboViewSet, basename='combos')
router.register(r'cards', views.CardViewSet, basename='cards')
router.register(r'templates', views.TemplateViewSet, basename='templates')
router.registry.extend(website_router.registry)

urlpatterns = [
    path('', include(router.urls))
]
