"""Isolated, repeatable local rehearsals. No credentials or PayPal requests."""
from pathlib import Path
from uuid import uuid4
from paypal import PayPal, PaymentPreflightError


class OfflinePayPal(PayPal):
    def __init__(self, return_base):
        self.return_base = return_base
        self.client_id = self.secret = ""

    def _json(self, *args, **kwargs):
        raise PaymentPreflightError("本地演练不连接 PayPal。请使用本地演练操作。")


def new_demo_database(runtime):
    directory = Path(runtime) / "demo-sessions"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / ("demo-" + uuid4().hex + ".sqlite")
