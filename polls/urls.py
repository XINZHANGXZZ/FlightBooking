"""
Convert URLs
"""
from django.urls import path

from . import views

# Set app_name so that different apps' urls can be used in html
app_name = 'polls'
urlpatterns = [
    # path('', views.IndexView.as_view(), name='index'),
    path('', views.index, name='index'),
    # path('<int:pk>/', views.DetailView.as_view(), name='detail'),
    # path('<int:question_id>/', views.detail, name='detail'),
    # path('<int:question_id>/results/', views.results, name='results'),
    # path('<int:pk>/results/', views.ResultsView.as_view(), name='results'),
    # path('<int:question_id>/vote/', views.vote, name='vote'),
    path('search', views.search, name='search'),
    path('customer', views.customer, name='customer'),
    path('manager', views.manager, name="manager")
]
