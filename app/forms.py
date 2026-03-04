from django import forms
from .models import CustomUser, Farmer
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

class FarmerRegistrationForm(forms.ModelForm):
    """
    Form for farmers to register their plot details and contact information.
    Uses device GPS for coordinates and requires administrative location (sub-county/ward).
    """
    class Meta:
        model = Farmer
        fields = ['fname', 'lname', 'phone', 'email', 'county', 'sub_county', 'ward', 'lat', 'long', 'crop_type']
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
            'county': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'County will be auto-detected from GPS',
                'required': False,
                'readonly': True
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
            'crop_type': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            })
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
