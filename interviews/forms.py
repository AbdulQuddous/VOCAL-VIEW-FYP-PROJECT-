from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re
from .models import UserProfile, JobRole


class UserRegistrationForm(UserCreationForm):
    """Extended user registration form"""
    
    username = forms.CharField(
        min_length=2,
        max_length=100
    )
    def clean_username(self):
        username = self.cleaned_data.get('username')

        if len(username) < 2:
            raise ValidationError("Username must contain at least 2 characters.")

        if len(username) > 100:
            raise ValidationError("Username cannot exceed 100 characters.")

        return username

    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=200, required=False)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'full_name']

    def clean_password1(self):
        password = self.cleaned_data.get('password1')

        if len(password) < 8 or len(password) > 20:
            raise ValidationError("Password must be between 8 and 20 characters.")

        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter.")

        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter.")

        if not re.search(r'[\W_]', password):
            raise ValidationError("Password must contain at least one special character.")

        return password
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class InterviewConfigForm(forms.Form):
    """Interview configuration form"""
    job_role = forms.ModelChoiceField(
        queryset=JobRole.objects.all(),
        required=True,
        label="Select Job Role"
    )
    
    duration = forms.IntegerField(
        min_value=5,
        max_value=15,
        initial=15,
        label="Interview Duration (minutes)"
    )