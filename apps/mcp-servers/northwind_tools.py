"""Live-data tools over the CAP service. Read-only. Two tools, each named after one business question.

There is deliberately no generic tool here (no 'run a query', no 'fetch an address'). The model can ask
only the two questions below, with checked inputs, and the CAP service decides which rows this user may see.
"""
from __future__ import annotations
import os, re
from urllib.parse import urlencode, quote
from datetime import date, datetime, timezone
import httpx
from identity import User

SERVICE_URL = os.environ.get("NORTHWIND_SERVICE_URL", "http://localhost:4004/odata/v4/northwind")


def lab_today() -> date:
    """The labs use a fixed 'today' (LAB_TODAY=2026-05-07) because the sample data ends in May 2026."""
    return date.fromisoformat(os.environ["LAB_TODAY"]) if os.environ.get("LAB_TODAY") else date.today()


def _client(user: User) -> httpx.AsyncClient:
    if user.bearer_token:                                   # on BTP: forward the user's own token
        return httpx.AsyncClient(headers={"Authorization": f"Bearer {user.bearer_token}"}, timeout=10)
    return httpx.AsyncClient(auth=user.backend_auth, timeout=10)   # local: mocked CAP user


def _url(path: str, params: dict) -> str:
    """OData wants spaces as %20. httpx would send '+', which the CAP parser rejects, so encode here."""
    return f"{SERVICE_URL}/{path}?{urlencode(params, quote_via=quote)}"


def _stamp() -> dict:
    return {"lab_today": lab_today().isoformat(), "data_read_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


async def get_order_status(user: User, order_id: int) -> dict:
    if not (10000 <= int(order_id) <= 99999):
        return {"found": False, "message": "An order number has five digits."}
    expand = ("Customer($select=CustomerID,CompanyName,Country),Employee($select=EmployeeID,FirstName,LastName,Title,Country),"
              "ShipVia,details($expand=product($select=ProductID,ProductName,UnitsInStock,UnitsOnOrder,Discontinued;"
              "$expand=Category($select=CategoryID,CategoryName)))")
    async with _client(user) as http:
        r = await http.get(_url(f"Orders({int(order_id)})", {"$expand": expand}))
    if r.status_code == 404:
        # Same message whether the order does not exist or belongs to another office: existence is not revealed.
        return {"found": False, "message": "No order with this number is visible to you."}
    r.raise_for_status()
    o = r.json()
    required = date.fromisoformat(o["RequiredDate"])
    return {
        "found": True, "order_id": o["OrderID"],
        "customer": {"id": o["Customer"]["CustomerID"], "name": o["Customer"]["CompanyName"], "country": o["Customer"]["Country"]},
        "salesperson": {"id": o["Employee"]["EmployeeID"], "name": f'{o["Employee"]["FirstName"]} {o["Employee"]["LastName"]}',
                        "title": o["Employee"]["Title"], "office_country": o["Employee"]["Country"]},
        "order_date": o["OrderDate"], "required_date": o["RequiredDate"], "shipped_date": o["ShippedDate"],
        "shipped": o["ShippedDate"] is not None,
        "days_until_required": (required - lab_today()).days,           # negative = overdue
        "carrier": {"id": o["ShipVia"]["ShipperID"], "name": o["ShipVia"]["CompanyName"]},
        "freight": float(o["Freight"]), "ship_country": o["ShipCountry"],
        "lines": [{"product_id": d["product"]["ProductID"], "product_name": d["product"]["ProductName"],
                   "category_id": d["product"]["Category"]["CategoryID"], "category": d["product"]["Category"]["CategoryName"],
                   "quantity": d["Quantity"], "discount": float(d["Discount"]),
                   "units_in_stock": d["product"]["UnitsInStock"], "units_on_order": d["product"]["UnitsOnOrder"],
                   "discontinued": d["product"]["Discontinued"]} for d in o["details"]],
        **_stamp(),
    }


async def get_product_availability(user: User, product: str) -> dict:
    product = str(product).strip()
    if not product or len(product) > 60 or not re.fullmatch(r"[\w\s\-'.&/()]+", product):
        return {"found": False, "message": "Give a product number or a product name of at most 60 characters."}
    expand = "Supplier($select=SupplierID,CompanyName,Country),Category($select=CategoryID,CategoryName)"
    if product.isdigit():
        params = {"$filter": f"ProductID eq {int(product)}", "$expand": expand}
    else:                                                    # the name goes into a string literal: double the quotes
        safe = product.lower().replace("'", "''")
        params = {"$filter": f"contains(tolower(ProductName),'{safe}')", "$expand": expand, "$top": "5"}
    async with _client(user) as http:
        r = await http.get(_url("Products", params))
    r.raise_for_status()
    rows = r.json()["value"]
    if not rows:
        return {"found": False, "message": "No product matches."}
    return {"found": True, "matches": [{
        "product_id": p["ProductID"], "product_name": p["ProductName"],
        "category_id": p["Category"]["CategoryID"], "category": p["Category"]["CategoryName"],
        "units_in_stock": p["UnitsInStock"], "units_on_order": p["UnitsOnOrder"], "reorder_level": p["ReorderLevel"],
        "discontinued": p["Discontinued"], "unit_price": float(p["UnitPrice"]),
        "supplier": {"id": p["Supplier"]["SupplierID"], "name": p["Supplier"]["CompanyName"], "country": p["Supplier"]["Country"]},
    } for p in rows], **_stamp()}
