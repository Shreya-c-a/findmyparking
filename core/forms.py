from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, SetPasswordForm
from .models import User
from django import forms


class UserSignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'gender', 'mobile_number', 'role', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none text-sm transition'
            })


class UserLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput())


class PasswordResetRequestForm(PasswordResetForm):
    email = forms.EmailField(
        required=True,
        error_messages={
            'required': 'Please enter your email address.',
        },
        widget=forms.EmailInput(
            attrs={
                'placeholder': 'john@example.com',
                'class': 'w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none transition-all',
            }
        )
    )

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if not email:
            raise forms.ValidationError('Please enter your email address.')
        return email


class PasswordResetSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Enter new password',
                'class': 'w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none transition-all',
            }
        )
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Confirm new password',
                'class': 'w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none transition-all',
            }
        )
    )