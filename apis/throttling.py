from rest_framework.throttling import AnonRateThrottle


class AuthTrottle(AnonRateThrottle):
    scope = "auth"
