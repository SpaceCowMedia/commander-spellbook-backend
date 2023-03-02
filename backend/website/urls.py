from django.urls import include, path
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'properties', views.WebsitePropertyViewSet, basename='properties')

urlpatterns = [
    path('', include(router.urls))
]
