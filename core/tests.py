from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LoginOtpFlowTests(TestCase):
	def setUp(self):
		self.user_model = get_user_model()
		self.user = self.user_model.objects.create_user(
			email='otp-user@example.com',
			password='StrongPass123!'
		)

	def test_login_redirects_to_otp_verify(self):
		response = self.client.post(reverse('login'), {
			'email': 'otp-user@example.com',
			'password': 'StrongPass123!',
		})
		self.assertRedirects(response, reverse('login_verify_otp'))
		session = self.client.session
		self.assertIn('pending_login_otp', session)

	def test_verify_otp_logs_user_in(self):
		self.client.post(reverse('login'), {
			'email': 'otp-user@example.com',
			'password': 'StrongPass123!',
		})
		otp = self.client.session.get('pending_login_otp')
		response = self.client.post(reverse('login_verify_otp'), {'otp': otp})
		self.assertEqual(response.status_code, 302)
		self.assertTrue('_auth_user_id' in self.client.session)
