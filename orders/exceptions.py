class OrderConflict(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class OrderIntegrityConflict(OrderConflict):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(
            "integrity_conflict",
            "Operational history is inconsistent; administrator review is required.",
        )
