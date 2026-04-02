from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from Blackstick import settings

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('b/', include('booket.urls')),
    path('dashboard/', include('booket.dashboard.urls')),
    path('', include('booket.client.urls')),
]

if settings.USE_S3 != "1":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
