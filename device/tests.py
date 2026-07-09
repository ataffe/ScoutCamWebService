import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User

CAMERA_ID = uuid.uuid4()
PRESIGN_URL = reverse('device:presigned_upload_url', kwargs={'camera_id': CAMERA_ID})

AWS_SETTINGS = {
    'AWS_REGION': 'us-east-1',
    'AWS_IMG_UPLOAD_BUCKET': 'test-bucket',
    'AWS_ENDPOINT_URL': None,
    'AWS_ACCESS_KEY_ID': 'test',
    'AWS_SECRET_ACCESS_KEY': 'test',
    'ENVIRONMENT': 'test',
    'DEV_IP': '127.0.0.1',
}


def make_user(username, email, password='StrongPass123!'):
    return User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name='Test',
        last_name='User',
    )


@override_settings(**AWS_SETTINGS)
class PresignedUploadUrlTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user('testuser', 'test@example.com')
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')

    def _mock_s3(self, presigned_url='https://s3.example.com/presigned'):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = presigned_url
        return mock_s3

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        self.assertEqual(response.status_code, 401)

    def test_jpeg_returns_200_with_expected_fields(self):
        with patch('device.views.boto3.client', return_value=self._mock_s3()):
            response = self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('url', data)
        self.assertIn('key', data)
        self.assertEqual(data['expires_in'], 300)

    def test_png_returns_200(self):
        with patch('device.views.boto3.client', return_value=self._mock_s3()):
            response = self.client.post(PRESIGN_URL, data={'content-type': 'image/png'}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_default_content_type_is_jpeg(self):
        with patch('device.views.boto3.client', return_value=self._mock_s3()):
            response = self.client.post(PRESIGN_URL, data={}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['key'].endswith('.jpeg'))

    def test_invalid_content_type_returns_400(self):
        response = self.client.post(PRESIGN_URL, data={'content-type': 'image/gif'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_key_contains_camera_id(self):
        with patch('device.views.boto3.client', return_value=self._mock_s3()):
            response = self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        self.assertIn(str(CAMERA_ID), response.json()['key'])

    def test_jpeg_key_has_jpeg_extension(self):
        with patch('device.views.boto3.client', return_value=self._mock_s3()):
            response = self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        self.assertTrue(response.json()['key'].endswith('.jpeg'))

    def test_png_key_has_png_extension(self):
        with patch('device.views.boto3.client', return_value=self._mock_s3()):
            response = self.client.post(PRESIGN_URL, data={'content-type': 'image/png'}, format='json')
        self.assertTrue(response.json()['key'].endswith('.png'))

    def test_key_has_device_prefix(self):
        with patch('device.views.boto3.client', return_value=self._mock_s3()):
            response = self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        self.assertTrue(response.json()['key'].startswith('device/'))

    def test_presigned_url_returned_from_s3(self):
        expected_url = 'https://s3.example.com/my-presigned-url'
        with patch('device.views.boto3.client', return_value=self._mock_s3(expected_url)):
            response = self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        self.assertEqual(response.json()['url'], expected_url)

    def test_boto3_called_with_correct_region(self):
        mock_s3 = self._mock_s3()
        with patch('device.views.boto3.client', return_value=mock_s3) as mock_client:
            self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        mock_client.assert_called_once()
        _, kwargs = mock_client.call_args
        self.assertEqual(kwargs['region_name'], 'us-east-1')

    def test_boto3_generate_presigned_url_called_with_correct_bucket(self):
        mock_s3 = self._mock_s3()
        with patch('device.views.boto3.client', return_value=mock_s3):
            self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        call_kwargs = mock_s3.generate_presigned_url.call_args
        self.assertEqual(call_kwargs.kwargs['Params']['Bucket'], 'test-bucket')

    def test_generate_presigned_url_expires_in_300(self):
        mock_s3 = self._mock_s3()
        with patch('device.views.boto3.client', return_value=mock_s3):
            self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        call_kwargs = mock_s3.generate_presigned_url.call_args
        self.assertEqual(call_kwargs.kwargs['ExpiresIn'], 300)

    def test_boto3_called_with_credentials_and_endpoint(self):
        mock_s3 = self._mock_s3()
        with patch('device.views.boto3.client', return_value=mock_s3) as mock_client:
            self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        _, kwargs = mock_client.call_args
        self.assertEqual(kwargs['endpoint_url'], None)
        self.assertEqual(kwargs['aws_access_key_id'], 'test')
        self.assertEqual(kwargs['aws_secret_access_key'], 'test')

    @override_settings(ENVIRONMENT='dev', DEV_IP='10.0.0.5')
    def test_dev_environment_replaces_localhost_with_dev_ip(self):
        with patch('device.views.boto3.client', return_value=self._mock_s3('http://localhost:9000/presigned')):
            response = self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        self.assertEqual(response.json()['url'], 'http://10.0.0.5:9000/presigned')

    def test_non_dev_environment_does_not_replace_localhost(self):
        with patch('device.views.boto3.client', return_value=self._mock_s3('http://localhost:9000/presigned')):
            response = self.client.post(PRESIGN_URL, data={'content-type': 'image/jpeg'}, format='json')
        self.assertEqual(response.json()['url'], 'http://localhost:9000/presigned')
