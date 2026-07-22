import hashlib
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient

from users.models import User
from camera.models import Camera
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

DEVICE_ID = '1234567890ABCDEF'

def make_user(username, email, password='StrongPass123!', first_name='Test', last_name='User'):
    return User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )

class CameraTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user('alice', 'alice@example.com', first_name='Alice', last_name='Smith')
        self.other_user = make_user('bob', 'bob@example.com', first_name='Bob', last_name='Jones')
        self.authenticate(user=self.user)
        self.camera = Camera.objects.create(owner=self.user, location='Front door')
    
    def get_jwt_token(self, user):
        """Helper to generate a JWT token for a given user."""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def authenticate(self, user):
        """Helper to set the JWT token on the client."""
        token = self.get_jwt_token(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_list_cameras_returns_only_owned(self):
        Camera.objects.create(owner=self.other_user, location='Garage')
        response = self.client.get(reverse('camera:camera-list'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['location'], 'Front door')

    def test_create_camera_returns_201_and_persists(self):
        payload = {'location': 'Back yard'}
        response = self.client.post(reverse('camera:camera-list'), data=payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Camera.objects.filter(location='Back yard', owner=self.user).exists())

    def test_create_camera_missing_required_fields_returns_400(self):
        response = self.client.post(reverse('camera:camera-list'), data={}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_get_camera_returns_correct_data(self):
        response = self.client.get(
            reverse('camera:camera-detail', kwargs={'public_camera_id': self.camera.public_camera_id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['location'], 'Front door')

    def test_get_other_users_camera_returns_404(self):
        other_camera = Camera.objects.create(owner=self.other_user, location='Garage')
        response = self.client.get(
            reverse('camera:camera-detail', kwargs={'public_camera_id': other_camera.public_camera_id})
        )
        self.assertEqual(response.status_code, 404)

    def test_update_camera_location(self):
        response = self.client.patch(
            reverse('camera:camera-detail', kwargs={'public_camera_id': self.camera.public_camera_id}),
            data={'location': 'Side gate'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.camera.refresh_from_db()
        self.assertEqual(self.camera.location, 'Side gate')

    def test_delete_camera_returns_204_and_removes_record(self):
        response = self.client.delete(
            reverse('camera:camera-detail', kwargs={'public_camera_id': self.camera.public_camera_id})
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Camera.objects.filter(pk=self.camera.pk).exists())

    def test_unauthenticated_access_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse('camera:camera-list'))
        self.assertEqual(response.status_code, 401)

    def test_list_returns_empty_when_user_has_no_cameras(self):
        Camera.objects.filter(owner=self.user).delete()
        response = self.client.get(reverse('camera:camera-list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_create_response_includes_public_camera_id(self):
        payload = {'location': 'Driveway'}
        response = self.client.post(reverse('camera:camera-list'), data=payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('public_camera_id', response.json())

    def test_create_ignores_owner_in_payload(self):
        payload = {'location': 'Lobby', 'owner': self.other_user.pk}
        response = self.client.post(reverse('camera:camera-list'), data=payload, format='json')
        self.assertEqual(response.status_code, 201)
        camera = Camera.objects.get(location='Lobby')
        self.assertEqual(camera.owner, self.user)

    def test_update_other_users_camera_returns_404(self):
        other_camera = Camera.objects.create(owner=self.other_user, location='Garage')
        response = self.client.patch(
            reverse('camera:camera-detail', kwargs={'public_camera_id': other_camera.public_camera_id}),
            data={'location': 'Hacked'},
            format='json',
        )
        self.assertEqual(response.status_code, 404)
        other_camera.refresh_from_db()
        self.assertEqual(other_camera.location, 'Garage')

    def test_delete_other_users_camera_returns_404(self):
        other_camera = Camera.objects.create(owner=self.other_user, location='Garage')
        response = self.client.delete(
            reverse('camera:camera-detail', kwargs={'public_camera_id': other_camera.public_camera_id})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Camera.objects.filter(pk=other_camera.pk).exists())

    def test_location_exceeds_max_length_returns_400(self):
        payload = {'location': 'A' * 101}
        response = self.client.post(reverse('camera:camera-list'), data=payload, format='json')
        self.assertEqual(response.status_code, 400)


class CameraProvisioningFlowTests(TestCase):
    """Covers the provision -> register -> claim device onboarding pipeline."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='alice', email='alice@example.com', password='StrongPass123!',
            first_name='Alice', last_name='Smith',
        )

    def authenticate(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def provision(self, device_id=DEVICE_ID):
        return self.client.post(reverse('camera:create_camera'), data={'device_id': device_id}, format='json')

    def register(self, device_id, claim_token):
        return self.client.post(
            reverse('camera:register_camera'),
            data={'device_id': device_id, 'claim_token': claim_token},
            format='json',
        )

    def claim(self, device_token, location='Front door'):
        return self.client.post(
            reverse('camera:claim_camera'),
            data={'device_token': device_token, 'location': location},
            format='json',
        )

    # --- Provision ---

    def test_provision_camera_returns_201_and_claim_token(self):
        response = self.provision()
        self.assertEqual(response.status_code, 201)
        claim_token = response.json()['claim_token']
        self.assertTrue(claim_token.startswith(f'{DEVICE_ID}_'))
        camera = Camera.objects.get(device_id=DEVICE_ID)
        self.assertFalse(camera.claimed)
        self.assertIsNone(camera.owner)
        self.assertEqual(
            camera.claim_token_hash,
            hashlib.sha256(claim_token.encode('utf-8')).hexdigest(),
        )

    def test_provision_camera_invalid_device_id_length_returns_400(self):
        response = self.provision(device_id='tooshort')
        self.assertEqual(response.status_code, 400)

    def test_provision_duplicate_device_id_returns_409(self):
        self.provision()
        response = self.provision()
        self.assertEqual(response.status_code, 409)

    # --- Register ---

    def test_register_camera_returns_201_and_device_token(self):
        claim_token = self.provision().json()['claim_token']
        response = self.register(DEVICE_ID, claim_token)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['device_token'].startswith(f'{DEVICE_ID}_'))
        self.assertIn('public_camera_id', data)
        camera = Camera.objects.get(device_id=DEVICE_ID)
        self.assertEqual(
            camera.device_token_hash,
            hashlib.sha256(data['device_token'].encode('utf-8')).hexdigest(),
        )

    def test_register_camera_invalid_claim_token_returns_400(self):
        self.provision()
        response = self.register(DEVICE_ID, 'x' * 32)
        self.assertEqual(response.status_code, 400)
        camera = Camera.objects.get(device_id=DEVICE_ID)
        self.assertEqual(camera.device_token_hash, '')

    def test_register_unknown_device_returns_404(self):
        response = self.register('nonexistent12345', 'x' * 32)
        self.assertEqual(response.status_code, 404)

    def test_register_claim_token_is_single_use(self):
        claim_token = self.provision().json()['claim_token']
        first = self.register(DEVICE_ID, claim_token)
        self.assertEqual(first.status_code, 201)
        second = self.register(DEVICE_ID, claim_token)
        self.assertEqual(second.status_code, 400)

    # --- Claim ---

    def test_claim_camera_requires_authentication_returns_401(self):
        response = self.claim('irrelevant_token')
        self.assertEqual(response.status_code, 401)

    def test_claim_camera_returns_200_and_sets_owner(self):
        claim_token = self.provision().json()['claim_token']
        device_token = self.register(DEVICE_ID, claim_token).json()['device_token']

        self.authenticate(self.user)
        response = self.claim(device_token, location='Back yard')
        self.assertEqual(response.status_code, 200)

        camera = Camera.objects.get(device_id=DEVICE_ID)
        self.assertEqual(camera.owner, self.user)
        self.assertTrue(camera.claimed)
        self.assertIsNotNone(camera.claimed_at)
        self.assertEqual(camera.location, 'Back yard')

    def test_claim_camera_with_invalid_token_returns_400_and_does_not_claim(self):
        claim_token = self.provision().json()['claim_token']
        self.register(DEVICE_ID, claim_token)

        self.authenticate(self.user)
        # Correct device_id prefix, but a forged/incorrect secret.
        forged_token = f'{DEVICE_ID}_not-the-real-secret'
        response = self.claim(forged_token)
        self.assertEqual(response.status_code, 400)

        camera = Camera.objects.get(device_id=DEVICE_ID)
        self.assertIsNone(camera.owner)
        self.assertFalse(camera.claimed)

    def test_claim_unknown_device_returns_404(self):
        self.authenticate(self.user)
        response = self.claim('nonexistent12345_somesecret')
        self.assertEqual(response.status_code, 404)

    def test_claim_already_claimed_camera_returns_400(self):
        claim_token = self.provision().json()['claim_token']
        device_token = self.register(DEVICE_ID, claim_token).json()['device_token']

        self.authenticate(self.user)
        self.claim(device_token)

        other_user = User.objects.create_user(
            username='bob', email='bob@example.com', password='StrongPass123!',
            first_name='Bob', last_name='Jones',
        )
        self.authenticate(other_user)
        response = self.claim(device_token)
        self.assertEqual(response.status_code, 400)
        camera = Camera.objects.get(device_id=DEVICE_ID)
        self.assertEqual(camera.owner, self.user)


class PresignedUploadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='alice', email='alice@example.com', password='StrongPass123!',
            first_name='Alice', last_name='Smith',
        )
        self.other_user = User.objects.create_user(
            username='bob', email='bob@example.com', password='StrongPass123!',
            first_name='Bob', last_name='Jones',
        )
        self.camera = Camera.objects.create(owner=self.user, location='Front door')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def presign(self, camera_id, content_type='image/jpeg'):
        return self.client.post(
            reverse('camera:presigned_upload', kwargs={'public_camera_id': camera_id}),
            data={'content_type': content_type},
            format='json',
        )

    @patch('camera.views.boto3.client')
    def test_presigned_upload_returns_url_for_owned_camera(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = 'https://example.com/presigned'
        mock_boto_client.return_value = mock_s3

        response = self.presign(self.camera.public_camera_id)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['url'], 'https://example.com/presigned')
        self.assertTrue(data['key'].startswith(f'device/{self.camera.public_camera_id}/'))
        self.assertTrue(data['key'].endswith('.jpeg'))
        self.assertEqual(data['expires_in'], 300)

        _, kwargs = mock_s3.generate_presigned_url.call_args
        self.assertEqual(kwargs['Params']['ContentType'], 'image/jpeg')

    def test_presigned_upload_rejects_unsupported_content_type(self):
        response = self.presign(self.camera.public_camera_id, content_type='text/plain')
        self.assertEqual(response.status_code, 400)

    def test_presigned_upload_other_users_camera_returns_404(self):
        other_camera = Camera.objects.create(owner=self.other_user, location='Garage')
        response = self.presign(other_camera.public_camera_id)
        self.assertEqual(response.status_code, 404)

    def test_presigned_upload_unknown_camera_returns_404(self):
        response = self.presign('019f87a0-b11b-7f64-b1c5-ae28cc33aa89')
        self.assertEqual(response.status_code, 404)

    def test_presigned_upload_requires_authentication_returns_401(self):
        self.client.credentials()
        response = self.presign(self.camera.public_camera_id)
        self.assertEqual(response.status_code, 401)
