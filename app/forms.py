from django import forms
from .models import CustomUser, Farmer, Farm
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

class CustomAuthenticationForm(AuthenticationForm):
    """
    Custom authentication form that uses email instead of username.
    """
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email',
            'autocomplete': 'email'
        }),
        help_text='Enter the email address associated with your account.'
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password'
        }),
        help_text='Enter your password.'
    )

    def clean(self):
        """
        Validate that email exists in the database.
        """
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        
        if username:
            try:
                CustomUser.objects.get(email=username)
            except CustomUser.DoesNotExist:
                raise forms.ValidationError("No account found with this email address.")
        
        return cleaned_data

class CustomUserCreationForm(UserCreationForm):
    """
    Custom user creation form for sign-up using email and password.
    """
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email',
            'autocomplete': 'email'
        }),
        help_text='We\'ll use this email to log you in. Make sure it\'s valid and unique.'
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a strong password',
            'autocomplete': 'new-password'
        }),
        help_text='Your password must be at least 8 characters long and cannot be too similar to your email.'
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password'
        }),
        help_text='Enter the same password as before for verification.'
    )

    class Meta:
        model = CustomUser
        fields = ("email", "password1", "password2")

    def clean_email(self):
        """
        Validate that the email is unique.
        """
        email = self.cleaned_data.get('email')
        if email and CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        """
        Validate that passwords match.
        """
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Passwords do not match.")
        
        return cleaned_data

    def save(self, commit=True):
        """
        Save the user with the email as the primary identifier.
        """
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]  # Set username as email for compatibility
        if commit:
            user.save()
        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove autofocus from email field
        self.fields['email'].widget.attrs.pop('autofocus', None)
        # Add more descriptive help text for password requirements
        self.fields['password1'].help_text = 'Your password must contain at least 8 characters.'

class FarmerProfileForm(forms.ModelForm):
    """
    Form for farmers to register/edit their personal details.
    """
    class Meta:
        model = Farmer
        fields = ['fname', 'lname', 'phone', 'email']
        widgets = {
            'fname': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your first name',
                'required': True
            }),
            'lname': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your last name',
                'required': True
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+254712345678 or 0712345678',
                'required': False
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your.email@example.com',
                'required': False
            }),
        }

    def clean(self):
        """
        Validate that at least phone number or email is provided.
        """
        cleaned_data = super().clean()
        phone = cleaned_data.get('phone')
        email = cleaned_data.get('email')
        
        # At least one of phone or email must be provided
        if not phone and not email:
            raise forms.ValidationError(
                "Please provide either a phone number or an email address (or both)."
            )
        
        return cleaned_data


class FarmRegistrationForm(forms.ModelForm):
    """
    Form for farms to register/edit farm details including location and crop type.
    Uses device GPS for coordinates and requires administrative location (sub-county/ward).
    """
    class Meta:
        model = Farm
        fields = ['farm_name', 'crop_type', 'farm_size', 'county', 'sub_county', 'ward', 'lat', 'long']
        widgets = {
            'farm_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Main Farm, North Field (optional)',
                'required': False
            }),
            'crop_type': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'farm_size': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter farm size in acres',
                'step': 'any',
                'required': True,
                'min': '0'
            }),
            'county': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'County (auto-detected from GPS, editable)',
                'required': False,
            }),
            'sub_county': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Kasipul, Muhoroni',
                'required': True
            }),
            'ward': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Kabar, Chemase',
                'required': True
            }),
            'lat': forms.NumberInput(attrs={
                'type': 'hidden',
                'id': 'lat-field',
                'step': 'any',
                'required': False,
            }),
            'long': forms.NumberInput(attrs={
                'type': 'hidden',
                'id': 'long-field',
                'step': 'any',
                'required': False,
            }),
        }

    def clean(self):
        """
        Validate that farm_size is provided and positive.
        """
        cleaned_data = super().clean()
        farm_size = cleaned_data.get('farm_size')
        
        if farm_size is None or farm_size <= 0:
            raise forms.ValidationError("Farm size must be greater than 0 acres.")
        
        return cleaned_data


# Keep the old form name for backward compatibility during transition
FarmerRegistrationForm = FarmRegistrationForm
class EmailVerificationForm(forms.Form):
    """
    Form for users to enter the 6-digit verification code sent to their email.
    """
    verification_code = forms.CharField(
        label="Verification Code",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
            'autocomplete': 'off',
            'maxlength': '6',
            'style': 'font-size: 2rem; letter-spacing: 0.5rem; font-weight: bold;'
        }),
        help_text='Enter the 6-digit code sent to your email address.'
    )
    
    def clean_verification_code(self):
        """
        Validate that the code contains only digits.
        """
        code = self.cleaned_data.get('verification_code')
        if code and not code.isdigit():
            raise forms.ValidationError("Verification code must contain only numbers.")
        return code

class PhoneAuthenticationForm(forms.Form):
    """
    Form for phone-based authentication.
    Users enter their phone number to sign in or sign up.
    """
    phone = forms.CharField(
        label="Phone Number",
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+254712345678 or 0712345678',
            'autocomplete': 'tel',
            'inputmode': 'tel',
            'pattern': r'^\+?1?\d{9,15}$'
        }),
        help_text='Enter your phone number in international format (+254...) or local format (07...).'
    )
    
    def clean_phone(self):
        """
        Validate that the phone number has the correct format.
        """
        phone = self.cleaned_data.get('phone')
        if phone:
            if not phone.replace('+', '').replace('0', '').isdigit():
                raise forms.ValidationError("Phone number must contain only digits, optional +, and 0 prefix.")
            if not (9 <= len(phone.replace('+', '').lstrip('0')) <= 15):
                raise forms.ValidationError("Phone number must be between 9 and 15 digits.")
        return phone


class PhoneVerificationForm(forms.Form):
    """
    Form for users to enter the 6-digit verification code sent to their phone.
    """
    verification_code = forms.CharField(
        label="Verification Code",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
            'autocomplete': 'off',
            'maxlength': '6',
            'style': 'font-size: 2rem; letter-spacing: 0.5rem; font-weight: bold;'
        }),
        help_text='Enter the 6-digit code sent to your phone number.'
    )
    
    def clean_verification_code(self):
        """
        Validate that the code contains only digits.
        """
        code = self.cleaned_data.get('verification_code')
        if code and not code.isdigit():
            raise forms.ValidationError("Verification code must contain only numbers.")
        return code