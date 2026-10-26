import logging

from django.db import DatabaseError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from orders.exceptions import OrderConflict

logger = logging.getLogger(__name__)


def exception_handler(error, context):
    if isinstance(error, OrderConflict):
        return Response({"code": error.code, "detail": error.message}, status=409)
    if isinstance(error, DatabaseError):
        logger.error("Database operation failed; transaction outcome requires review.")
        return Response(
            {
                "code": "database_error",
                "detail": "The operation could not be completed. Check its status before retrying.",
            },
            status=500,
        )
    return drf_exception_handler(error, context)
