from django.urls import path
from . import views

urlpatterns = [
    path('', views.parking_list, name='parking_list'),
    path('book/', views.quick_book, name='quick_book'),
    path('<int:pk>/book/', views.book_parking, name='book_parking'),
    path('<int:pk>/', views.parking_detail, name='parking_detail'),
    path('<int:pk>/slots/', views.slot_list, name='slot_list'),
    path('add/', views.add_parking, name='add_parking'),
    path('<int:pk>/edit/', views.edit_parking, name='edit_parking'),
    path('<int:pk>/delete/', views.delete_parking, name='delete_parking'),
    path('<int:pk>/add-slot/', views.add_slot, name='add_slot'),
    path('<int:pk>/slots/<int:slot_id>/toggle/', views.toggle_slot_status, name='toggle_slot_status'),
    # Legacy dashboard redirects
    path('owner/', views.ownerDashboardView, name='owner_dashboard_legacy'),
    path('user-legacy/', views.userDashboardView, name='user_dashboard_legacy'),
]