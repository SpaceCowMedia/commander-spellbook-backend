from django.urls import include, path
from common.hybridrouter import HybridRouter
from . import views

router = HybridRouter()
router.register(r'properties', views.WebsitePropertyViewSet, basename='properties')
router.add_api_view(r'card-list-from-url', path('card-list-from-url', views.card_list_from_url, name='card-list-from-url'))

urlpatterns = [
    path('', include(router.urls))
]
