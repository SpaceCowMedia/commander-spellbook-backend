from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qsl
from rest_framework.serializers import CharField
from social_django.strategy import DjangoStrategy
from rest_framework_simplejwt.tokens import Token, BlacklistMixin, RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer as BaseTokenObtainPairSerializer


class LoginCode(BlacklistMixin, Token):
    token_type = 'login'
    lifetime = timedelta(seconds=30)

    @property
    def refresh_token(self) -> RefreshToken:
        refresh = RefreshToken()
        no_copy = refresh.no_copy_claims
        for claim, value in self.payload.items():
            if claim in no_copy:
                continue
            refresh[claim] = value
        return refresh


class TokenObtainPairSerializer(BaseTokenObtainPairSerializer):
    refresh = CharField(read_only=True)
    access = CharField(read_only=True)
    code_param = 'code'
    code = False

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        data = kwargs.get('data', {})
        if self.code_param in data:
            self.fields.clear()
            self.fields[self.code_param] = CharField(write_only=True)
            self.code = True
        else:
            self.fields[self.code_param] = CharField(write_only=True, required=False)
            for field in self.fields.values():
                field.required = False

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        if not self.code:
            return super().validate(attrs)
        login_code = attrs[self.code_param]
        login_code = LoginCode(token=login_code)
        login_code.blacklist()
        refresh = login_code.refresh_token
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        return data


class SimpleJwtDjangoStrategy(DjangoStrategy):
    session_key = 'code'
    login_code = None

    def authenticate(self, backend, *args, **kwargs):
        user = super().authenticate(backend, *args, **kwargs)
        if user is not None and self.session_pop(self.session_key) is not None:
            self.login_code = str(LoginCode.for_user(user))
        return user

    def redirect(self, url):
        if self.login_code:
            scheme, netloc, path, query_string, fragment = urlsplit(url)
            query_params = parse_qsl(query_string)
            query_params.append(('code', self.login_code))
            query_string = urlencode(query_params)
            url = urlunsplit((scheme, netloc, path, query_string, fragment))
        return super().redirect(url)
