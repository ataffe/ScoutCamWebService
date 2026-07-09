from django.urls import path
from device.views import PresignedUploadUrl

app_name = 'device'

urlpatterns = [
    path('device/presign/<uuid:camera_id>', PresignedUploadUrl.as_view(), name='presigned_upload_url'),
]