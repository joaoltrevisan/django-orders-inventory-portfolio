import json

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator
from common.api import PrivateResponseMixin

from .models import DatasetSnapshot
from .reports import REPORTS, count_report, execute_report, parameters, serializable


class HistoricalReportResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = serializers.ListField(
        child=serializers.DictField(child=serializers.JSONField()),
        help_text="Report-specific columns; exact numeric money is serialized as strings.",
    )
    data_origin = serializers.ChoiceField(choices=["OLIST_HISTORICAL"])
    date_basis = serializers.CharField()


class ReportView(PrivateResponseMixin, APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        description=(
            "Administrator-only historical SQL report, page size 20. "
            "Sales use snapshot delivered status; source purchase timestamps have no verified "
            "time zone. See docs/stage-05/sql-portfolio.md for each result grain and NULL rules."
        ),
        parameters=[
            OpenApiParameter("report_name", str, OpenApiParameter.PATH, enum=REPORTS),
            OpenApiParameter(
                "start",
                str,
                description="Inclusive source timestamp: YYYY-MM-DD HH:MM:SS.",
                default="2016-09-01 00:00:00",
            ),
            OpenApiParameter(
                "end",
                str,
                description="Exclusive source timestamp; increasing interval up to ten years.",
                default="2018-11-01 00:00:00",
            ),
            OpenApiParameter(
                "min_units", int, description="Unit threshold, 1 to 1000000.", default=10
            ),
            OpenApiParameter(
                "min_orders", int, description="Repeat threshold, 2 to 1000000.", default=2
            ),
            OpenApiParameter("page", int, description="Page number, starting at 1."),
        ],
        responses={
            200: HistoricalReportResponseSerializer,
            400: OpenApiResponse(OpenApiTypes.OBJECT, description="Invalid report parameters."),
            401: OpenApiResponse(
                OpenApiTypes.OBJECT, description="Missing or invalid access token."
            ),
            403: OpenApiResponse(OpenApiTypes.OBJECT, description="Administrator access required."),
            404: OpenApiResponse(OpenApiTypes.OBJECT, description="Unknown report or page."),
            409: OpenApiResponse(
                OpenApiTypes.OBJECT, description="Complete historical snapshot unavailable."
            ),
        },
    )
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
