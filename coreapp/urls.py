from django.urls import path, include
from .views import (current_user, UserList,
                    LinkBankAccount, GetAuth,
                    TransactionViewSet,
                    GetUserStoreVisit,
                    TransactionCategoryViewSet,
                    SignupViewSet
                    )
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('transactions', TransactionViewSet, basename='transactions')
router.register('signup', SignupViewSet, basename='signup')
router.register('transaction-category', TransactionCategoryViewSet, basename='transaction-category')

urlpatterns = [
    path('current_user/', current_user),
    path('users/', UserList.as_view()),
    path('link-bank-account/', LinkBankAccount.as_view()),
    path('get-auth/', GetAuth.as_view()),
    path('stores-visited/', GetUserStoreVisit.as_view()),
    path('', include(router.urls))
]

