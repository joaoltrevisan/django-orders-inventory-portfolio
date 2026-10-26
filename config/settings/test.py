from .base import *  # noqa: F403

# Public, test-only key. Never use this configuration for deployment.
SECRET_KEY = "test-only-independent-olist-case-study-not-a-deployment-secret"
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}  # noqa: F405
