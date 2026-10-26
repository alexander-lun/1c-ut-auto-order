import os
import uuid

import httpx
import pytest

STAND_URL = os.environ.get("STAND_URL", "http://127.0.0.1:8081/ut/hs/auto-order-stand")
DATE = "2030-03-31"


@pytest.fixture(scope="session")
def stand():
    auth = None
    if "STAND_USER" in os.environ:
        auth = (os.environ["STAND_USER"], os.environ.get("STAND_PASSWORD", ""))
    with httpx.Client(base_url=STAND_URL, timeout=600, auth=auth) as client:
        yield client


def short(name):
    """Имя без суффикса сценария: "Магазин 1A2B3C4D" -> "Магазин"."""
    return name.rsplit(" ", 1)[0] if name else name


class Scenario:
    def __init__(self, client, data):
        self.client = client
        self.uid = data["uid"]
        self.warehouses = data["warehouses"]

    def _post(self, path, warehouses, days):
        body = {"uid": self.uid, "date": DATE, "days": days, "warehouses": warehouses or self.warehouses}
        r = self.client.post(path, json=body)
        assert r.status_code == 200, r.text
        return r.json()

    def calculate(self, warehouses=None, days=30):
        """Строки расчета по ключу (склад, товар, характеристика) без суффиксов сценария."""
        rows = self._post("/calculate", warehouses, days)["rows"]
        return {(short(r["Склад"]), short(r["Номенклатура"]), r["Характеристика"]): r for r in rows}

    def orders(self, warehouses=None, days=30):
        return self._post("/orders", warehouses, days)["orders"]


@pytest.fixture
def scenario(stand):
    """Создает склады, товары, параметры пополнения и движения: scenario(warehouses=[...], items=[...], ...)."""

    def _scenario(**data):
        data = {"uid": uuid.uuid4().hex[:8].upper(), "date": DATE, **data}
        data["items"] = [i if isinstance(i, dict) else {"name": i} for i in data["items"]]
        r = stand.post("/scenario", json=data)
        assert r.status_code == 200, r.text
        return Scenario(stand, data)

    return _scenario
