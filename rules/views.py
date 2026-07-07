from rest_framework.exceptions import PermissionDenied

from rules.models import Camera, Rule
from rules.serializers import RuleSerializer
from rest_framework import permissions, viewsets


class RuleViewSet(viewsets.ModelViewSet):
    serializer_class = RuleSerializer
    lookup_field = 'public_rule_id'
    permission_classes = [permissions.IsAuthenticated]

    def get_camera(self):
        camera = Camera.objects.filter(
            public_camera_id=self.kwargs['public_camera_id_public_camera_id'],
            owner=self.request.user
        ).first()

        if camera is None:
            raise PermissionDenied('Camera not found or does not belong to this user')
        return camera

    def get_queryset(self):
        return Rule.objects.filter(camera=self.get_camera())

    def perform_create(self, serializer):
        serializer.save(camera=self.get_camera(), owner=self.request.user)
