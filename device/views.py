import uuid
import boto3
import logging

from botocore.config import Config
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

ALLOWED_TYPES = {"image/jpeg", "image/png"}
logger = logging.getLogger(__name__)

class PresignedUploadUrl(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, camera_id):
        logger.info(f'Generating a presigned url for user: {request.user.public_user_id}')
        content_type = request.data.get('content-type', 'image/jpeg')
        if content_type not in ALLOWED_TYPES:
            return Response({'detail': 'Unsupported content type'}, status=status.HTTP_400_BAD_REQUEST)

        image_format = 'jpeg' if content_type == 'image/jpeg' else 'png'
        img_key = f'device/{camera_id}/{uuid.uuid4()}.{image_format}'
        s3 = boto3.client(
            's3',
            region_name=settings.AWS_REGION,
            endpoint_url=settings.AWS_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4'))

        url = s3.generate_presigned_url(
            ClientMethod='put_object',
            Params={'Bucket': settings.AWS_IMG_UPLOAD_BUCKET, 'Key': img_key, 'ContentType': content_type},
            ExpiresIn=300
        )

        if settings.ENVIRONMENT == 'dev':
            url = url.replace('localhost', settings.DEV_IP)

        return Response({'url': url, 'key': img_key, 'expires_in': 300})

