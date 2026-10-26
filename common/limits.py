from decimal import Decimal

MAX_UNIT_PRICE = Decimal("99999999.99")
MAX_ORDER_TOTAL = Decimal("99999999999999.99")
MAX_ITEM_QUANTITY = 9999
MAX_ORDER_ITEMS = 100
MAX_STOCK_QUANTITY = 2147483647
SKU_PATTERN = r"^[A-Z0-9][A-Z0-9._-]{0,63}$"
BRAZILIAN_STATES = (
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
)
