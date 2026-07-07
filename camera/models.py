from django.db import models
import uuid

from users.models import User

class Camera(models.Model):
    id = models.BigAutoField(primary_key=True)
    # Must be using PostgreSQL 18+ for the native UUID7 support.
    public_camera_id = models.UUIDField(editable=False, unique=True, db_default=models.Func(function="uuidv7"))
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    location = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Camera at location {self.location} for user {self.owner.id}.'
