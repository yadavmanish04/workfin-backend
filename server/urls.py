from django.contrib import admin
from django.urls import path, include

import server.admin

from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.permissions import AllowAny
from django.conf import settings  
from django.conf.urls.static import static  



schema_view = get_schema_view(
    openapi.Info(
        title="Workfina API ",
        default_version='v1',
        description="Workfina API documentation",
    ),
    public=True,
    permission_classes=[AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.authentication.urls')),
    path('api/candidates/', include('apps.candidates.urls')),
    path('api/recruiters/', include('apps.recruiters.urls')),
    path('api/wallet/', include('apps.wallet.urls')),
    path('api/banner/', include('apps.banners.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/app-version/', include('apps.app_version.urls')),
    path('api/content/', include('apps.dashboard_text_message.urls')),
    path('api/ranking/', include('apps.ranking.urls')),

    path('api/subscriptions/', include('apps.subscriptions.urls')),

    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)