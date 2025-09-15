from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.core.exceptions import ValidationError

from .forms import BusinessRegistrationForm, BusinessLoginForm, ProfileUpdateForm
from .models import BusinessUser


class BusinessLoginView(LoginView):
    """Custom login view for business users"""
    form_class = BusinessLoginForm
    template_name = 'users/login.html'
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        remember_me = form.cleaned_data.get('remember_me')
        if remember_me:
            self.request.session.set_expiry(1209600)  # 2 weeks
        else:
            self.request.session.set_expiry(0)  # Browser close
        
        messages.success(self.request, f'Welcome back, {form.get_user().get_full_business_name()}!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Invalid username/email or password. Please try again.')
        return super().form_invalid(form)


@csrf_protect
def register_view(request):
    """Registration view for business users"""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        form = BusinessRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                
                # Log the user in automatically after registration
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password1')
                user = authenticate(username=username, password=password)
                
                if user:
                    login(request, user)
                    messages.success(
                        request, 
                        f'Welcome to Neuro, {user.get_full_business_name()}! Your account has been created successfully.'
                    )
                    return redirect('dashboard:home')
                    
            except ValidationError as e:
                messages.error(request, f'Registration failed: {e.message}')
            except Exception as e:
                messages.error(request, 'An error occurred during registration. Please try again.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.replace("_", " ").title()}: {error}')
    else:
        form = BusinessRegistrationForm()
    
    return render(request, 'users/register.html', {'form': form})


@login_required
def logout_view(request):
    """Logout view"""
    business_name = request.user.get_full_business_name()
    logout(request)
    messages.success(request, f'You have been successfully logged out. See you again soon!')
    return redirect('users:login')


@login_required
def profile_view(request):
    """User profile view and update"""
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            # Check if profile is complete
            if user.is_profile_complete():
                user.profile_completed = True
            user.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('users:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProfileUpdateForm(instance=request.user)
    
    context = {
        'form': form,
        'user': request.user,
        'profile_completion': _get_profile_completion_percentage(request.user)
    }
    return render(request, 'users/profile.html', context)


@login_required
def dashboard_redirect(request):
    """Redirect to appropriate dashboard based on user status"""
    user = request.user
    
    # Check if onboarding is needed
    if not user.onboarding_completed:
        return redirect('users:onboarding')
    
    # Redirect to main dashboard
    return redirect('dashboard:home')


@login_required
def onboarding_view(request):
    """Onboarding flow for new users"""
    if request.user.onboarding_completed:
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        # Handle onboarding completion
        user = request.user
        
        # Mark onboarding as completed
        user.onboarding_completed = True
        
        # Check if profile is complete
        if user.is_profile_complete():
            user.profile_completed = True
            
        user.save()
        
        messages.success(request, 'Welcome to Neuro! Let\'s start building your AI-powered marketing campaigns.')
        return redirect('dashboard:home')
    
    context = {
        'user': request.user,
        'features': [
            {
                'name': 'Neuro-Ads Engine',
                'description': 'AI generates and optimizes campaigns across Google, Meta, and LinkedIn',
                'enabled': request.user.neuro_ads_enabled
            },
            {
                'name': 'Omni-Social Pulse',
                'description': 'Automated content creation and social media management',
                'enabled': request.user.omni_social_enabled
            },
            {
                'name': 'Predictive Email Cortex',
                'description': 'AI-powered email marketing and lead nurturing',
                'enabled': request.user.email_cortex_enabled
            }
        ]
    }
    
    return render(request, 'users/onboarding.html', context)


def _get_profile_completion_percentage(user):
    """Calculate profile completion percentage"""
    total_fields = 7  # business_name, industry, company_size, website, phone_number, business_type, email
    completed_fields = 0
    
    if user.email:
        completed_fields += 1
    if user.business_name:
        completed_fields += 1
    if user.industry:
        completed_fields += 1
    if user.company_size:
        completed_fields += 1
    if user.website:
        completed_fields += 1
    if user.phone_number:
        completed_fields += 1
    if user.business_type:
        completed_fields += 1
    
    return int((completed_fields / total_fields) * 100)


# AJAX views for dynamic functionality
def check_username_availability(request):
    """AJAX view to check username availability"""
    username = request.GET.get('username', '')
    
    if len(username) < 3:
        return JsonResponse({'available': False, 'message': 'Username must be at least 3 characters long'})
    
    available = not BusinessUser.objects.filter(username=username).exists()
    message = 'Username is available' if available else 'Username is already taken'
    
    return JsonResponse({'available': available, 'message': message})


def check_email_availability(request):
    """AJAX view to check email availability"""
    email = request.GET.get('email', '')
    
    if not email:
        return JsonResponse({'available': False, 'message': 'Please enter an email'})
    
    available = not BusinessUser.objects.filter(email=email).exists()
    message = 'Email is available' if available else 'Email is already registered'
    
    return JsonResponse({'available': available, 'message': message})
