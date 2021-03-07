from datetime import date

from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from django.contrib.auth.models import User
from .models import PlaidItem, Transaction, TransactionCategory
from django.utils import timezone


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('username', 'email', 'password')
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = User(
            email=validated_data['email'],
            username=validated_data['username']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class UserSerializerWithToken(serializers.ModelSerializer):
    email = serializers.CharField(max_length=30)
    token = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True)

    def get_token(self, obj):
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

        payload = jwt_payload_handler(obj)
        token = jwt_encode_handler(payload)
        return token

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        #email = validated_data('email')

        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
            email = validated_data.get('email', instance.email)
        instance.save()
        return instance

    class Meta:
        model = User
        fields = ('token', 'username', 'password', 'email')


class LinkBankAccountSerializer(serializers.Serializer):
    public_token = serializers.CharField(max_length=200)


class PlaidItemSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    class Meta:
        fields = '__all__'
        model = PlaidItem

    def get_username(self, obj):
        return obj.user.username


class TransactionSerializer(serializers.ModelSerializer):
    cats = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    store_title = serializers.SerializerMethodField()
    time_since = serializers.SerializerMethodField()

    class Meta:
        fields = '__all__'
        model = Transaction

    def get_username(self, obj):
        return obj.item.user.username

    def get_cats(self, obj):
        categories = [
            {"id": category.pk, "title": category.title} for category in obj.categories.all()
        ]
        return categories

    def get_store_title(self, obj):
        if obj.store_name:
            return obj.store_name.name
        return ''

    def get_time_since(self, obj):
        return (date(timezone.now().year, timezone.now().month, timezone.now().day) - obj.date).days


class TransactionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = TransactionCategory

