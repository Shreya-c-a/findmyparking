from django.urls import path
from django.urls import reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .forms import PasswordResetRequestForm, PasswordResetSetPasswordForm

urlpatterns = [
    path('', views.home, name='home'),
    path('help-center/', views.help_center_view, name='help_center'),
    path('brand/logos/', views.logo_showcase_view, name='logo_showcase'),
    path('signup/', views.userSignupView, name='signup'),
    path('login/', views.userLoginView, name='login'),
    path('login/admin/', views.adminLoginView, name='admin_login'),
    path('login/verify-otp/', views.login_verify_otp_view, name='login_verify_otp'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='auth/password_reset.html',
            email_template_name='auth/password_reset_email.txt',
            subject_template_name='auth/password_reset_subject.txt',
            form_class=PasswordResetRequestForm,
            success_url=reverse_lazy('password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='auth/password_reset_done.html'
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='auth/password_reset_confirm.html',
            form_class=PasswordResetSetPasswordForm,
            success_url=reverse_lazy('password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='auth/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.user_dashboard_view, name='user_dashboard'),
    path('dashboard/admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('dashboard/owner/', views.owner_analytics_dashboard, name='owner_analytics_dashboard'),
    # Analytics redirects to consolidated dashboards
    path('analytics/', views.admin_dashboard_view, name='analytics_dashboard'),
    path('analytics/owner/', views.owner_analytics_dashboard, name='owner_analytics_dashboard_legacy'),
]