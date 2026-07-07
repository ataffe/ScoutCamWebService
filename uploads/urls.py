from django.urls import path
from uploads.views import PresignedUploadUrl

app_name = 'uploads'

urlpatterns = [
    path('uploads/presign/<uuid:camera_id>', PresignedUploadUrl.as_view(), name='presigned_upload_url'),
]