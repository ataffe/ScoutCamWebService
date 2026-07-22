from rest_framework_nested import routers
from django.urls import path

from camera.views import (
    CameraViewSet,
    PresignedUploadView,
    ProvisionCameraView,
    CameraRegistrationView,
    CameraClaimView,
)

app_name = 'camera'

camera_router = routers.DefaultRouter()
camera_router.register(r'cameras', CameraViewSet, basename='camera')

urlpatterns = [
    # These must come before the router's URLs: the router's detail route
    # (cameras/<public_camera_id>/) is greedy and would otherwise swallow
    # cameras/provision/, cameras/register/, and cameras/claim/ as lookups.
    path('cameras/presign/<uuid:public_camera_id>/', PresignedUploadView.as_view(), name='presigned_upload'),
    path('cameras/provision/', ProvisionCameraView.as_view(), name='create_camera'),
    path('cameras/register/', CameraRegistrationView.as_view(), name='register_camera'),
    path('cameras/claim/', CameraClaimView.as_view(), name='claim_camera'),
    *camera_router.urls,
]