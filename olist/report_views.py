import json

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator
from common.api import PrivateResponseMixin

from .models import DatasetSnapshot
from .reports import count_report, execute_report, parameters, serializable


class ReportView(PrivateResponseMixin, APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, report_name):
        query = request.query_params
        try:
            params = parameters(
                start=query.get("start", "2016-09-01 00:00:00"),
                end=query.get("end", "2018-11-01 00:00:00"),
                min_units=serializers.IntegerField(min_value=1).run_validation(
                    query.get("min_units", 10)
                ),
                min_orders=serializers.IntegerField(min_value=2).run_validation(
                    query.get("min_orders", 2)
                ),
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        if not DatasetSnapshot.objects.filter(publication_status="COMPLETE").exists():
            return Response(
                {
                    "code": "historical_data_unavailable",
                    "detail": "A complete historical snapshot is required.",
                },
                status=409,
            )
        total = count_report(report_name, params)
        pagination = PageNumberPagination()
        pagination.paginate_queryset(range(total), request, view=self)
        rows = execute_report(
            report_name,
            params,
            limit=pagination.page.paginator.per_page,
            offset=pagination.page.start_index() - 1 if total else 0,
        )
        response = pagination.get_paginated_response(
            json.loads(json.dumps(rows, default=serializable))
        )
        response.data["data_origin"] = "OLIST_HISTORICAL"
        response.data["date_basis"] = "Source purchase calendar; time zone unspecified."
        return response
