"""backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/dev/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from common.hybridrouter import HybridRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from spellbook.urls import router as spellbook_router
from website.urls import router as website_router
from . import views

admin.site.site_header = f'Spellbook Admin Panel {settings.VERSION}'
admin.site.site_title = f'Spellbook Admin {settings.VERSION}'
admin.site.index_title = 'Spellbook Admin Index'

router = HybridRouter()
router.register_router(spellbook_router)
router.register_router(website_router)
router.register(r'users', views.UserViewSet, basename='users')

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)),
    # Authentication
    path('', include('social_django.urls', namespace='social')),
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Admin
    path('admin/', admin.site.urls),
    # OpenApi
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if 'debug_toolbar' in settings.INSTALLED_APPS:
    urlpatterns.append(path('__debug__/', include('debug_toolbar.urls')))
