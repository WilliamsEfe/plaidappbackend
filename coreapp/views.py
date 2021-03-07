from django.http import HttpResponseRedirect
from django.contrib.auth.models import User
from rest_framework import permissions, status, viewsets, authentication
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import (UserSerializer,
                          UserSerializerWithToken,
                          LinkBankAccountSerializer,
                          TransactionSerializer,
                          TransactionCategorySerializer)
from plaid import Client
from .models import PlaidItem, Transaction, TransactionCategory, StoreName
from django.conf import settings
import datetime
from django.utils import timezone
from django.db.models import Q
from .pagination import Pagination

client = Client(
        client_id=settings.PLAID_CLIENT_ID,
        secret=settings.PLAID_SECRET,
        public_key=settings.PLAID_PUBLIC_KEY,
        environment=settings.PLAID_ENV
    )


@api_view(['GET'])
def current_user(request):
    """
    Determine the current user by their token, and return their data
    """

    serializer = UserSerializer(request.user)
    return Response(serializer.data)


class UserList(APIView):
    """
    Create a new user. It's called 'UserList' because normally we'd have a get
    method here too, for retrieving a list of all User objects.
    """

    permission_classes = (permissions.AllowAny,)

    def post(self, request, format=None):
        serializer = UserSerializerWithToken(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LinkBankAccount(APIView):

    def get(self, request):
        response = []
        items = PlaidItem.objects.all()
        for item in items:
            res = {
                'item_id': item.item_id,
                'user_id': item.user.pk,
                'username': item.user.username,
                'access_token': item.access_token,
                'request_id': item.request_id
            }
            response.append(res)

        return Response(response, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = LinkBankAccountSerializer(data=request.data)
        if serializer.is_valid():

            res = client.Item.public_token.exchange(serializer.data['public_token'])
            user = request.user

            item = PlaidItem.objects.create(
                item_id=res['item_id'],
                access_token=res['access_token'],
                request_id=res['request_id'],
                user=user
            )
            # save all transactions for the item
            response = client.Transactions.get(item.access_token, start_date='1990-01-01',
                                               end_date=str(datetime.date.today()))
            transactions = response['transactions']

            while len(transactions) < response['total_transactions']:
                response = client.Transactions.get(item.access_token, start_date='1990-01-01',
                                                   end_date=str(datetime.date.today()),
                                                   offset=len(transactions)
                                                   )
                transactions.extend(response['transactions'])
            for transaction in transactions:
                needed_categories = ['Fast Food', 'Coffee Shop', 'Restaurant', 'Food and Drink']
                needed = False
                category_set = set(transaction['category'])
                for cat in needed_categories:
                    if cat in category_set:
                        needed = True
                if (not Transaction.objects.filter(transaction_id=transaction['transaction_id']).first())\
                        and needed:

                    transaction_obj = Transaction.objects.create(
                        item=item,
                        transaction_id=transaction['transaction_id'],
                        account_id=transaction['account_id'],
                        amount=transaction['amount'],
                        iso_currency_code=transaction['iso_currency_code'],
                        date=transaction['date'],
                        address=transaction['location']['address'],
                        city=transaction['location']['city'],
                        region=transaction['location']['region'],
                        postal_code=transaction['location']['postal_code'],
                        country=transaction['location']['country'],
                        latitude=transaction['location']['lat'],
                        longitude=transaction['location']['lon'],
                        # store_name=store_name,
                        payment_channel=transaction['payment_channel']
                    )
                    store_name = StoreName.objects.get_or_create(name=transaction['name'])
                    for category in transaction['category']:
                        if category in needed_categories:
                            category_obj = TransactionCategory.objects.get_or_create(
                                title=category
                            )[0]
                            transaction_obj.categories.add(category_obj)
                            store_name[0].categories.add(category_obj)
                    store_name[0].save()
                    transaction_obj.store_name = store_name[0]
                    transaction_obj.save()
            # web hook
            client.Item.webhook.update(item.access_token,
                                       'http://localhost:8000/core/transactions/')
            response = {
                'message': 'bank linked successful'
            }
            return Response(response, status=status.HTTP_201_CREATED)

        else:
            return Response(serializer.errors)


class GetAuth(APIView):
    def post(self, request):
        auth_responses = []
        user = User.objects.first()
        if request.user.is_authenticated:
            # user = request.user
            pass
        items = PlaidItem.objects.filter(user=user)
        for item in items:
            auth_response = client.Auth.get(item.access_token)
            auth_responses = auth_responses + auth_response['accounts']
        return Response({
            'accounts': auth_responses
        }, status=status.HTTP_200_OK)


class TransactionViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = TransactionSerializer
    pagination_class = Pagination

    def get_queryset(self):
        month = self.request.GET.get("month")
        month_options = ["this_month", "last_month", "3months", "12months", "all"]

        # query
        category = self.request.GET.get("category")
        date = self.request.GET.get("date")
        q = self.request.GET.get("q")
        queryset = Transaction.objects.all()
        if q:
            queryset = queryset.filter(item__user__username=q)
        if category:
            queryset = queryset.filter(categories=int(category))
        if month and month == "this month":
            year_ = timezone.now().year
            month_ = timezone.now().month
            queryset = queryset.filter(date__gte=datetime.date(year_, month_, 1))
        if month and month == "last month":
            queryset = queryset.filter(date__gte=(timezone.now()+datetime.timedelta(weeks=-4)))
        if month and month == "3months":
            queryset = queryset.filter(date__gte=(timezone.now() + datetime.timedelta(weeks=-12)))
        if month and month == "12months":
            queryset = queryset.filter(date__gte=(timezone.now() + datetime.timedelta(weeks=-52)))
        return queryset


class TransactionWebHook(APIView):

    def post(self, request):
        webhook_type = request.data.get("webhook_type")
        webhook_code = request.data.get("webhook_code")
        item_id = request.data.get("item_id")
        new_transaction = request.data.get("new_transaction")

        if webhook_type and (webhook_type == 'TRANSACTIONS'):
            if webhook_code and (webhook_code == 'DEFAULT_UPDATE'):
                item_obj = PlaidItem.objects.get(
                    item_id=item_id
                )

                response = client.Transactions.get(item_obj.access_token,
                                                   start_date=datetime.date.today(),
                                                   end_date=str(datetime.date.today()))
                transactions = response['transactions']
                while len(transactions) < response['total_transactions']:
                    response = client.Transactions.get(item_obj.access_token,
                                                       start_date=datetime.date.today(),
                                                       end_date=str(datetime.date.today()),
                                                       offset=len(transactions)
                                                       )
                    transactions.extend(response['transactions'])

                for transaction in transactions:
                    if not Transaction.objects.filter(transaction_id=transaction['transaction_id']).first():

                        transaction_obj = Transaction.objects.create(
                            item=item_obj,
                            transaction_id=transaction['transaction_id'],
                            account_id=transaction['account_id'],
                            amount=transaction['amount'],
                            iso_currency_code=transaction['iso_currency_code'],
                            date=transaction['date'],
                            address=transaction['location']['address'],
                            city=transaction['location']['city'],
                            region=transaction['location']['region'],
                            postal_code=transaction['location']['postal_code'],
                            country=transaction['location']['country'],
                            latitude=transaction['location']['lat'],
                            longitude=transaction['location']['lon'],
                            # store_name=store_name,
                            payment_channel=transaction['payment_channel']
                        )
                        store_name = StoreName.objects.get_or_create(name=transaction['name'])
                        for category in transaction['category']:
                            category_obj = TransactionCategory.objects.get_or_create(
                                title=category
                            )[0]
                            transaction_obj.categories.add(category_obj)
                            store_name.categories.add(category_obj)
                        store_name.save()
                        transaction_obj.store_name = store_name
                        transaction_obj.save()

            if webhook_code and (webhook_code == 'TRANSACTIONS_REMOVED'):
                removed_transactions = request.data.get("removed_transactions")
                for transaction in removed_transactions:
                    try:
                        t = Transaction.objects.get(transaction_id=transaction)
                        t.delete()
                    except:
                        pass

        return Response({"message": "successfully performed updates on transaction"}, status=status.HTTP_200_OK)


class GetUserStoreVisit(APIView):

    def get(self, request):
        user = request.user

        stores = StoreName.objects.all()
        if request.GET.get("all"):
            stores = StoreName.objects.all()[:10]
        if request.GET.get("username"):
            user_obj = User.objects.filter(username=request.GET.get("username")).first()
            if user_obj:
                stores = StoreName.objects.filter(transaction__item__user=user_obj).distinct()
            else:
                stores = []
        if request.GET.get("category"):
            category = TransactionCategory.objects.filter(pk=int(request.GET.get("category")))
            if category:
                stores = stores.filter(categories__in=category)

            else:
                return Response({"message": "invalid category"}, status=status.HTTP_400_BAD_REQUEST)
        response = []
        for store in stores:
            visit_count = store.transaction_set.count()
            if request.GET.get("username"):
                visit_count = store.transaction_set.\
                    filter(item__user__username=request.GET.get("username")).count()
            res = {
                "id": store.pk,
                "name": store.name,
                "visit_count": visit_count,
                "categories": [cat.title for cat in store.categories.all()]
            }
            response.append(res)
        response = sorted(response, key=lambda x: x['visit_count'], reverse=True)
        return Response(response, status=status.HTTP_200_OK)


class TransactionCategoryViewSet(viewsets.ModelViewSet):
    permissions_classes = (permissions.AllowAny,)
    serializer_class = TransactionCategorySerializer


    def get_queryset(self):
        queryset = TransactionCategory.objects.all()

        return queryset


class SignupViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserSerializer
    queryset = User.objects.all()
