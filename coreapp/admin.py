from django.contrib import admin
from .models import PlaidItem, Transaction, TransactionCategory, StoreName
# Register your models here.


admin.site.register(PlaidItem)
admin.site.register(Transaction)
admin.site.register(TransactionCategory)
admin.site.register(StoreName)
