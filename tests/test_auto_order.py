"""Расчет потребности и создание заказов на тестовых данных УТ 11.

У каждого теста свои склады, товары и поставщик (имена с суффиксом сценария), поэтому данные не смешиваются.
Дата расчета 31.03.2030, продажи - за 30 дней (02.03-31.03).
"""

import pytest

from conftest import short

# Страховой запас 5 дней, заказ еще на 10 дней: при расходе 2 шт./день точка заказа 10, целевой запас 30
SETTINGS = {"safety": 5, "days": 10, "supplier": True}
SALES_2_PER_DAY = {"qty": 60, "days_ago": 3}


def setting(item, warehouse="Магазин", **extra):
    return {"warehouse": warehouse, "item": item, **SETTINGS, **extra}


def sale(item, warehouse="Магазин", **extra):
    return {"warehouse": warehouse, "item": item, **SALES_2_PER_DAY, **extra}


def stock(item, qty, warehouse="Магазин", **extra):
    return {"warehouse": warehouse, "item": item, "qty": qty, **extra}


def test_reorder_up_to_target_stock(scenario):
    sc = scenario(
        warehouses=["Магазин"],
        items=["Чай", "Кофе", "Сахар"],
        settings=[setting("Чай"), setting("Кофе"), setting("Сахар")],
        stock=[stock("Чай", 10), stock("Кофе", 11), stock("Сахар", 15, reserved=5)],
        sales=[sale("Чай"), sale("Кофе"), sale("Сахар")],
    )
    rows = sc.calculate()

    tea = rows[("Магазин", "Чай", "")]
    assert (tea["Продано"], tea["СреднийРасход"], tea["ТочкаЗаказа"], tea["ЦелевойЗапас"]) == (60, 2, 10, 30)
    assert (tea["Остаток"], tea["Потребность"], tea["КЗаказу"]) == (10, 20, 20)
    # выше точки заказа - не заказываем
    coffee = rows[("Магазин", "Кофе", "")]
    assert coffee["КЗаказу"] == 0
    assert "выше точки заказа" in coffee["Пояснение"]
    # зарезервированное (к отгрузке) не считается доступным: 15 - 5 = 10
    sugar = rows[("Магазин", "Сахар", "")]
    assert (sugar["Остаток"], sugar["КЗаказу"]) == (10, 20)


def test_multiple_and_minimal_lot(scenario):
    sc = scenario(
        warehouses=["Магазин"],
        items=["Кратно6", "Партия50", "Партия50Кратно6"],
        settings=[
            setting("Кратно6", multiple=6),
            setting("Партия50", min_lot=50),
            setting("Партия50Кратно6", min_lot=50, multiple=6),
        ],
        stock=[stock("Кратно6", 10), stock("Партия50", 10), stock("Партия50Кратно6", 10)],
        sales=[sale("Кратно6"), sale("Партия50"), sale("Партия50Кратно6")],
    )
    rows = sc.calculate()

    # потребность везде 20
    assert rows[("Магазин", "Кратно6", "")]["КЗаказу"] == 24
    assert rows[("Магазин", "Партия50", "")]["КЗаказу"] == 50
    assert rows[("Магазин", "Партия50Кратно6", "")]["КЗаказу"] == 54
    assert all(r["Потребность"] == 20 for r in rows.values())


def test_goods_in_transit_and_draft_orders(scenario):
    sc = scenario(
        warehouses=["Магазин", "Склад"],
        items=["ВПути", "Черновик", "Мало"],
        settings=[setting("ВПути"), setting("Черновик"), setting("Мало")],
        sales=[sale("ВПути"), sale("Черновик"), sale("Мало")],
        supplier_orders=[
            {"warehouse": "Магазин", "item": "ВПути", "qty": 15},
            {"warehouse": "Магазин", "item": "Мало", "qty": 5},
        ],
        transfer_orders=[{"from": "Склад", "to": "Магазин", "item": "ВПути", "qty": 10}],
        drafts=[{"warehouse": "Магазин", "item": "Черновик", "qty": 20}],
    )
    rows = sc.calculate(warehouses=["Магазин"])

    # заказано поставщику 15 + перемещение 10 = 25 > точки заказа 10
    in_transit = rows[("Магазин", "ВПути", "")]
    assert (in_transit["ВПути"], in_transit["КЗаказу"]) == (25, 0)
    # непроведенный заказ поставщику учитывается - повторно не заказываем
    draft = rows[("Магазин", "Черновик", "")]
    assert (draft["ВЗаказах"], draft["КЗаказу"]) == (20, 0)
    # в пути 5 - ниже точки заказа: дозаказ до 30
    low = rows[("Магазин", "Мало", "")]
    assert (low["ВПути"], low["КЗаказу"]) == (5, 25)


def test_sales_analysis_period(scenario):
    sc = scenario(
        warehouses=["Магазин"],
        items=["Товар"],
        settings=[setting("Товар")],
        # 29 дней назад - первый день периода, 30 дней назад - уже за его границей
        sales=[sale("Товар", qty=30, days_ago=29), sale("Товар", qty=30, days_ago=30)],
    )
    assert sc.calculate()[("Магазин", "Товар", "")]["Продано"] == 30
    assert sc.calculate(days=31)[("Магазин", "Товар", "")]["Продано"] == 60


def test_minimal_stock_without_sales(scenario):
    sc = scenario(
        warehouses=["Магазин"],
        items=["Выкладка", "Неходовой"],
        settings=[setting("Выкладка", min_stock=4), setting("Неходовой")],
        stock=[stock("Выкладка", 1)],
    )
    rows = sc.calculate()

    assert rows[("Магазин", "Выкладка", "")]["КЗаказу"] == 3
    slow = rows[("Магазин", "Неходовой", "")]
    assert slow["КЗаказу"] == 0
    assert "Нет продаж" in slow["Пояснение"]


def test_characteristics_are_calculated_separately(scenario):
    sc = scenario(
        warehouses=["Магазин"],
        items=[{"name": "Кроссовки", "characteristics": ["38", "39"]}],
        settings=[setting("Кроссовки")],
        sales=[sale("Кроссовки", characteristic="38"), sale("Кроссовки", characteristic="39", qty=30)],
        stock=[stock("Кроссовки", 4, characteristic="39")],
    )
    rows = sc.calculate()

    assert rows[("Магазин", "Кроссовки", "38")]["КЗаказу"] == 30
    # 1 шт./день: точка заказа 5, целевой запас 15, остаток 4
    assert rows[("Магазин", "Кроссовки", "39")]["КЗаказу"] == 11
    assert len(rows) == 2


def test_transfer_limited_by_source_stock(scenario):
    stores = ["Магазин1", "Магазин2"]
    sc = scenario(
        warehouses=["Центральный", *stores],
        items=["Товар"],
        settings=[setting("Товар", w, supplier=False, source="Центральный") for w in stores],
        stock=[stock("Товар", 30, "Центральный"), *[stock("Товар", 10, w) for w in stores]],
        sales=[sale("Товар", w) for w in stores],
    )
    rows = sc.calculate(warehouses=stores)

    # нужно 20 + 20, на центральном складе 30: первому магазину 20, второму остаток 10
    assert rows[("Магазин1", "Товар", "")]["КЗаказу"] == 20
    second = rows[("Магазин2", "Товар", "")]
    assert (second["Потребность"], second["КЗаказу"]) == (20, 10)
    assert "Ограничено свободным остатком" in second["Пояснение"]


def test_create_orders(scenario):
    sc = scenario(
        warehouses=["Центральный", "Магазин1", "Магазин2"],
        items=["Чай", "Кофе"],
        settings=[
            setting("Чай", "Магазин1"),
            setting("Кофе", "Магазин1"),
            setting("Чай", "Магазин2", supplier=False, source="Центральный"),
        ],
        stock=[stock("Чай", 100, "Центральный"), stock("Кофе", 50, "Магазин1")],
        sales=[sale("Чай", "Магазин1"), sale("Кофе", "Магазин1"), sale("Чай", "Магазин2")],
    )
    stores = ["Магазин1", "Магазин2"]
    orders = {o["type"]: o for o in sc.orders(warehouses=stores)}

    assert set(orders) == {"ЗаказПоставщику", "ЗаказНаПеремещение"}
    purchase = orders["ЗаказПоставщику"]
    assert not purchase["posted"]
    assert (short(purchase["partner"]), short(purchase["warehouse"])) == ("Поставщик", "Магазин1")
    assert purchase["status"] == "На согласовании"
    # кофе выше точки заказа - в заказ не попал
    assert [(short(line["item"]), line["qty"]) for line in purchase["lines"]] == [("Чай", 30)]
    assert "автозаказом" in purchase["comment"]

    transfer = orders["ЗаказНаПеремещение"]
    assert not transfer["posted"]
    assert (short(transfer["from"]), short(transfer["warehouse"])) == ("Центральный", "Магазин2")
    assert [(short(line["item"]), line["qty"]) for line in transfer["lines"]] == [("Чай", 30)]

    # повторный запуск (как регламентное задание) не создает дублей: созданные заказы уже в доступном запасе
    rows = sc.calculate(warehouses=stores)
    assert all(r["КЗаказу"] == 0 for r in rows.values())
    assert sc.orders(warehouses=stores) == []


@pytest.mark.parametrize("days", [0, -1])
def test_wrong_analysis_period(stand, days):
    r = stand.post("/calculate", json={"uid": "X", "date": "2030-03-31", "days": days, "warehouses": []})
    assert r.status_code == 500
    assert "дней анализа" in r.json()["error"]
