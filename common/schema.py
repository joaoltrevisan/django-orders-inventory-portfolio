from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class DatabaseJWTScheme(SimpleJWTScheme):
    target_class = "accounts.authentication.DatabaseJWTAuthentication"
