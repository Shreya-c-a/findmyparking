from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from parking.models import User as ParkingUser, ParkingLot, ParkingSlot, Reservation, Payment
from parking.models import Admin as ParkingAdmin
from parking.pricing import calculate_commission_split


class ReservationCancelTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.core_user = user_model.objects.create_user(
			email='cancel-user@example.com',
			password='StrongPass123!'
		)
		self.parking_user = ParkingUser.objects.create(
			full_name='Cancel User',
			email='cancel-user@example.com',
			password_hash='django_auth',
			role='USER',
			status='ACTIVE',
		)
		self.lot = ParkingLot.objects.create(
			name='Test Lot',
			location='Ahmedabad',
			total_slots=10,
			available_slots=9,
		)
		self.slot = ParkingSlot.objects.create(
			parking_lot=self.lot,
			slot_number='S-001',
			slot_type='REGULAR',
			status='RESERVED',
		)
		self.reservation = Reservation.objects.create(
			user=self.parking_user,
			slot=self.slot,
			start_time=timezone.now() + timedelta(hours=1),
			end_time=timezone.now() + timedelta(hours=2),
			reservation_type='HOURLY',
			reservation_code='TEST-CANCEL-001',
			status='ACTIVE',
		)
		self.client.force_login(self.core_user)

	def test_cancel_requires_post(self):
		response = self.client.get(reverse('cancel_reservation', args=[self.reservation.pk]))
		self.assertEqual(response.status_code, 302)
		self.reservation.refresh_from_db()
		self.assertEqual(self.reservation.status, 'ACTIVE')

	def test_cancel_via_post(self):
		response = self.client.post(reverse('cancel_reservation', args=[self.reservation.pk]))
		self.assertEqual(response.status_code, 302)
		self.reservation.refresh_from_db()
		self.slot.refresh_from_db()
		self.assertEqual(self.reservation.status, 'CANCELLED')
		self.assertEqual(self.slot.status, 'AVAILABLE')


class ParkingListSortTests(TestCase):
	def setUp(self):
		ParkingLot.objects.create(name='Beta Lot', location='Zone B', total_slots=10, available_slots=2)
		ParkingLot.objects.create(name='Alpha Lot', location='Zone A', total_slots=10, available_slots=8)

	def test_sort_by_name(self):
		response = self.client.get(reverse('parking_list'), {'sort': 'name'})
		self.assertEqual(response.status_code, 200)
		lots = list(response.context['parking_lots'])
		self.assertEqual(lots[0].name, 'Alpha Lot')


class QRGateScannerTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.owner_user = user_model.objects.create_user(
			email='owner@example.com',
			password='OwnerPass123!',
			role='owner',
		)
		self.client.force_login(self.owner_user)

		self.parking_user = ParkingUser.objects.create(
			full_name='Scanner User',
			email='scanner-user@example.com',
			password_hash='django_auth',
			role='USER',
			status='ACTIVE',
		)
		self.lot = ParkingLot.objects.create(
			name='Gate Test Lot',
			location='Ahmedabad',
			total_slots=10,
			available_slots=9,
		)
		self.slot = ParkingSlot.objects.create(
			parking_lot=self.lot,
			slot_number='S-010',
			slot_type='REGULAR',
			status='RESERVED',
		)
		self.reservation = Reservation.objects.create(
			user=self.parking_user,
			slot=self.slot,
			start_time=timezone.now() - timedelta(minutes=10),
			end_time=timezone.now() + timedelta(hours=1),
			reservation_type='HOURLY',
			reservation_code='FMP-SCAN123',
			status='ACTIVE',
		)
		Payment.objects.create(
			reservation=self.reservation,
			amount=120,
			payment_method='UPI',
			payment_status='SUCCESS',
		)

	def test_entry_scan_marks_slot_occupied(self):
		response = self.client.post(reverse('qr_gate_scanner'), {
			'reservation_code': self.reservation.reservation_code,
			'scan_action': 'entry',
		})
		self.assertEqual(response.status_code, 200)

		self.reservation.refresh_from_db()
		self.slot.refresh_from_db()
		self.assertIsNotNone(self.reservation.checked_in_at)
		self.assertEqual(self.slot.status, 'OCCUPIED')

	def test_exit_scan_completes_reservation(self):
		self.client.post(reverse('qr_gate_scanner'), {
			'reservation_code': self.reservation.reservation_code,
			'scan_action': 'entry',
		})

		response = self.client.post(reverse('qr_gate_scanner'), {
			'reservation_code': self.reservation.reservation_code,
			'scan_action': 'exit',
		})
		self.assertEqual(response.status_code, 200)

		self.reservation.refresh_from_db()
		self.slot.refresh_from_db()
		self.assertEqual(self.reservation.status, 'COMPLETED')
		self.assertIsNotNone(self.reservation.checked_out_at)
		self.assertEqual(self.slot.status, 'AVAILABLE')


class OwnerSlotManagementTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.owner_user = user_model.objects.create_user(
			email='slot-owner@example.com',
			password='OwnerPass123!',
			role='owner',
		)
		self.client.force_login(self.owner_user)

		self.parking_owner = ParkingUser.objects.create(
			full_name='Slot Owner',
			email='slot-owner@example.com',
			password_hash='django_auth',
			role='USER',
			status='ACTIVE',
		)
		self.owner_admin = ParkingAdmin.objects.create(user=self.parking_owner, access_level='STANDARD')

		self.lot = ParkingLot.objects.create(
			name='Owner Lot',
			location='Ahmedabad',
			total_slots=1,
			available_slots=1,
			created_by=self.owner_admin,
		)
		self.slot = ParkingSlot.objects.create(
			parking_lot=self.lot,
			slot_number='S-001',
			slot_type='REGULAR',
			status='AVAILABLE',
		)

	def test_bulk_add_slots(self):
		response = self.client.post(reverse('add_slot', args=[self.lot.pk]), {
			'slot_number': 'IGNORE',
			'slot_type': 'REGULAR',
			'status': 'AVAILABLE',
			'bulk_count': '3',
			'slot_prefix': 'B',
		})
		self.assertEqual(response.status_code, 302)
		self.assertEqual(ParkingSlot.objects.filter(parking_lot=self.lot).count(), 4)

	def test_toggle_slot_status(self):
		response = self.client.post(reverse('toggle_slot_status', args=[self.lot.pk, self.slot.pk]))
		self.assertEqual(response.status_code, 302)
		self.slot.refresh_from_db()
		self.assertEqual(self.slot.status, 'DISABLED')


class CommissionSplitTests(TestCase):
	def test_calculate_commission_split(self):
		owner_earning, platform_fee = calculate_commission_split(500, 90)
		self.assertEqual(owner_earning, 450.0)
		self.assertEqual(platform_fee, 50.0)
