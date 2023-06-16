from rest_framework.pagination import LimitOffsetPagination


class CustomPagination(LimitOffsetPagination):
    max_limit = 100
