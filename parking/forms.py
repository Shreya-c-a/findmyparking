from django import forms
from .models import ParkingLot, ParkingSlot


class ParkingLotForm(forms.ModelForm):
    class Meta:
        model = ParkingLot
        fields = ['name', 'location', 'latitude', 'longitude', 'total_slots']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none text-sm',
                'placeholder': 'Parking Lot Name'
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none text-sm',
                'placeholder': 'Full Address'
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none text-sm',
                'placeholder': '23.022500',
                'step': '0.000001',
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none text-sm',
                'placeholder': '72.571400',
                'step': '0.000001',
            }),
            'total_slots': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none text-sm',
                'placeholder': '50',
                'min': 1,
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        total_slots = cleaned_data.get('total_slots')
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')

        if total_slots is not None and total_slots <= 0:
            self.add_error('total_slots', 'Total slots must be greater than 0.')

        if latitude is not None and not (-90 <= float(latitude) <= 90):
            self.add_error('latitude', 'Latitude must be between -90 and 90.')

        if longitude is not None and not (-180 <= float(longitude) <= 180):
            self.add_error('longitude', 'Longitude must be between -180 and 180.')

        # Enforce that coordinates must both be provided (not synthetic/empty)
        has_lat = latitude is not None and latitude != ''
        has_lon = longitude is not None and longitude != ''
        if has_lat != has_lon:
            if has_lat:
                self.add_error('longitude', 'Please provide both latitude and longitude.')
            else:
                self.add_error('latitude', 'Please provide both latitude and longitude.')

        if self.instance.pk and total_slots is not None:
            current_slots = ParkingSlot.objects.filter(parking_lot=self.instance).count()
            if total_slots < current_slots:
                self.add_error(
                    'total_slots',
                    f'Total slots cannot be less than existing slot records ({current_slots}).'
                )

        return cleaned_data


class ParkingSlotForm(forms.ModelForm):
    class Meta:
        model = ParkingSlot
        fields = ['parking_lot', 'slot_number', 'slot_type', 'status']
        widgets = {
            'parking_lot': forms.Select(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none text-sm bg-white'
            }),
            'slot_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none text-sm',
                'placeholder': 'A-01'
            }),
            'slot_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none text-sm bg-white'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none text-sm bg-white'
            }),
        }
