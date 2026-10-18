"""Tests de extremo a extremo de la API. Requieren TEST_DATABASE_URL (Postgres)."""

POLICY = {
    "name": "Base",
    "max_amount_per_invoice": 5000,
    "period_budget": 6000,
    "require_human_above": 1000,
    "allowed_currencies": ["usd"],
}


def create_vendor(client, name="ACME", is_allowed=True) -> int:
    response = client.post("/vendors", json={"name": name, "is_allowed": is_allowed})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_invoice(client, vendor_id, number, amount, currency="USD"):
    return client.post(
        "/invoices",
        json={
            "invoice_number": number,
            "vendor_id": vendor_id,
            "amount": amount,
            "currency": currency,
            "due_date": "2026-11-30",
        },
    )


def test_full_flow(client):
    assert client.post("/policies", json=POLICY).status_code == 201
    acme = create_vendor(client)
    shady = create_vendor(client, "Shady", is_allowed=False)

    approved = create_invoice(client, acme, "INV-1", 800).json()
    assert approved["status"] == "approved"
    assert approved["amount"] == 800
    assert approved["decisions"][0]["decided_by"] == "agent"
    assert len(approved["decisions"][0]["rules_evaluated"]) == 9
    assert approved["raw_data"]["invoice_number"] == "INV-1"

    escalated = create_invoice(client, acme, "INV-2", 2000).json()
    assert escalated["status"] == "escalated"

    blocked = create_invoice(client, shady, "S-1", 100).json()
    assert blocked["status"] == "blocked"
    assert "no está autorizado" in blocked["decisions"][0]["explanation"]

    # Duplicado -> se registra y el agente lo bloquea explicando el motivo
    duplicate = create_invoice(client, acme, "INV-1", 800)
    assert duplicate.status_code == 201
    dup = duplicate.json()
    assert dup["status"] == "blocked"
    assert "Ya existe la factura INV-1" in dup["decisions"][0]["explanation"]
    assert f"id {approved['id']}" in dup["decisions"][0]["explanation"]

    # Revisión humana aprueba la escalada
    reviewed = client.post(
        f"/invoices/{escalated['id']}/review",
        json={"outcome": "approved", "explanation": "Contrato anual firmado", "reviewer": "Laura Gómez"},
    ).json()
    assert reviewed["status"] == "approved"
    assert [d["decided_by"] for d in reviewed["decisions"]] == ["agent", "human"]

    # Ya aprobada: no se puede revisar ni reevaluar
    assert client.post(
        f"/invoices/{escalated['id']}/review", json={"outcome": "blocked", "explanation": "x", "reviewer": "Laura"}
    ).status_code == 409
    assert client.post(f"/invoices/{escalated['id']}/evaluate").status_code == 409

    # Presupuesto: 800 + 2000 gastados de 6000
    budget = client.get("/policies/active/budget").json()
    assert budget["spent"] == 2800
    assert budget["remaining"] == 3200

    # 900 cabe y no requiere humano; luego 3700 + 2500 supera el presupuesto -> bloqueada
    assert create_invoice(client, acme, "INV-3", 900).json()["status"] == "approved"
    over = create_invoice(client, acme, "INV-4", 2500).json()
    assert over["status"] == "blocked"
    assert any(
        r["rule"] == "period_budget" and not r["passed"]
        for r in over["decisions"][0]["rules_evaluated"]
    )

    # Autorizar al proveedor y reevaluar la bloqueada
    client.patch(f"/vendors/{shady}", json={"is_allowed": True})
    reeval = client.post(f"/invoices/{blocked['id']}/evaluate").json()
    assert reeval["status"] == "approved"
    assert len(reeval["decisions"]) == 2

    assert len(client.get("/invoices", params={"status": "approved"}).json()) == 4
    assert len(client.get("/decisions", params={"decided_by": "human"}).json()) == 1


def test_no_active_policy_escalates(client):
    acme = create_vendor(client)
    assert create_invoice(client, acme, "INV-1", 10).json()["status"] == "escalated"
    assert client.get("/policies/active").status_code == 404


def test_new_policy_replaces_active_one(client):
    first = client.post("/policies", json=POLICY).json()
    second = client.post("/policies", json={**POLICY, "name": "Estricta"}).json()
    policies = {p["id"]: p for p in client.get("/policies").json()}
    assert not policies[first["id"]]["is_active"]
    assert policies[second["id"]]["is_active"]
    assert second["allowed_currencies"] == ["USD"]

    client.post(f"/policies/{first['id']}/activate")
    assert client.get("/policies/active").json()["id"] == first["id"]


def test_validation_errors(client):
    bad_policy = {**POLICY, "require_human_above": 9000}
    assert client.post("/policies", json=bad_policy).status_code == 422
    assert create_invoice(client, 999, "X", 10).status_code == 422
    acme = create_vendor(client)
    assert create_invoice(client, acme, "X", -5).status_code == 422
    assert client.post("/vendors", json={"name": "ACME"}).status_code == 409


def test_delete_vendor_and_policy(client):
    policy = client.post("/policies", json=POLICY).json()
    acme = create_vendor(client)
    unused = create_vendor(client, "Sin facturas")
    invoice = create_invoice(client, acme, "INV-1", 100).json()

    # Proveedor sin facturas: se elimina
    assert client.delete(f"/vendors/{unused}").status_code == 204
    assert client.get(f"/vendors/{unused}").status_code == 404
    # Proveedor con facturas: se protege el historial
    response = client.delete(f"/vendors/{acme}")
    assert response.status_code == 409
    assert "bloquéalo" in response.json()["detail"]

    # Política usada en decisiones: se elimina y las decisiones conservan su explicación
    assert client.delete(f"/policies/{policy['id']}").status_code == 204
    assert client.get("/policies").json() == []
    assert client.get("/policies/active").status_code == 404
    decision = client.get(f"/invoices/{invoice['id']}").json()["decisions"][0]
    assert decision["policy_id"] is None
    assert decision["explanation"].startswith("Aprobada")

    assert client.delete("/policies/999").status_code == 404
    assert client.delete("/vendors/999").status_code == 404


def test_multi_currency_limits_budget_and_rates(client):
    # Sin tipo de cambio no se puede usar EUR como moneda base
    response = client.post("/policies", json={**POLICY, "base_currency": "EUR"})
    assert response.status_code == 422
    assert "tipo de cambio de EUR" in response.json()["detail"]

    assert client.put("/exchange-rates/gbp", json={"usd_per_unit": 1.27}).json()["currency"] == "GBP"
    assert client.put("/exchange-rates/USD", json={"usd_per_unit": 2}).status_code == 422
    assert client.put("/exchange-rates/GBP", json={"usd_per_unit": 0}).status_code == 422

    client.post("/policies", json={**POLICY, "allowed_currencies": ["USD", "GBP", "MXN"]})
    acme = create_vendor(client)

    # 4.900 GBP = 6.223 USD > máximo 5.000 USD -> bloqueada (antes se aprobaba por error)
    over = create_invoice(client, acme, "GB-1", 4900, "GBP").json()
    assert over["status"] == "blocked"
    assert "6.223,00 USD" in over["decisions"][0]["explanation"]

    # 700 GBP = 889 USD -> aprobada; el presupuesto se suma convertido
    assert create_invoice(client, acme, "GB-2", 700, "GBP").json()["status"] == "approved"
    assert create_invoice(client, acme, "US-1", 100, "USD").json()["status"] == "approved"
    budget = client.get("/policies/active/budget").json()
    assert budget["base_currency"] == "USD"
    assert budget["spent"] == 989.0  # 889 + 100
    assert budget["missing_rates"] == []

    # Moneda permitida pero sin tipo de cambio -> escalada, nunca aprobada
    mxn = create_invoice(client, acme, "MX-1", 10, "MXN").json()
    assert mxn["status"] == "escalated"

    # El tipo de cambio de la moneda base de una política no se puede borrar
    client.put("/exchange-rates/EUR", json={"usd_per_unit": 1.08})
    client.post("/policies", json={**POLICY, "name": "Euro", "base_currency": "EUR"})
    assert client.delete("/exchange-rates/EUR").status_code == 409
    assert client.delete("/exchange-rates/GBP").status_code == 204
    assert [r["currency"] for r in client.get("/exchange-rates").json()] == ["EUR"]


def test_vendor_agreement_is_saved_and_applied(client):
    client.post("/policies", json={**POLICY, "require_human_above": 3000})
    # Monto sin moneda -> 422 con mensaje claro
    assert client.post("/vendors", json={"name": "X", "agreed_amount": 100}).status_code == 422

    vendor = client.post(
        "/vendors",
        json={"name": "Ana Pérez", "agreed_amount": 1200, "agreed_currency": "usd", "agreement_notes": "Tarifa mensual"},
    ).json()
    assert vendor["agreed_currency"] == "USD" and vendor["agreement_tolerance_pct"] == 5.0

    assert create_invoice(client, vendor["id"], "AP-1", 1230).json()["status"] == "approved"
    off = create_invoice(client, vendor["id"], "AP-2", 1900).json()
    assert off["status"] == "escalated"
    assert "No cuadra con lo acordado" in off["decisions"][0]["explanation"]

    # Cambiar solo la tolerancia; dejar el monto sin moneda -> 422; quitar el acuerdo
    assert client.patch(f"/vendors/{vendor['id']}", json={"agreement_tolerance_pct": 60}).json()["agreement_tolerance_pct"] == 60.0
    assert client.patch(f"/vendors/{vendor['id']}", json={"agreed_currency": None}).status_code == 422
    cleared = client.patch(f"/vendors/{vendor['id']}", json={"agreed_amount": None, "agreed_currency": None}).json()
    assert cleared["agreed_amount"] is None


def test_delete_invoice_unless_approved(client):
    client.post("/policies", json=POLICY)
    acme = create_vendor(client)
    approved = create_invoice(client, acme, "OK-1", 100).json()
    shady = create_vendor(client, "Shady", is_allowed=False)
    blocked = create_invoice(client, shady, "BAD-1", 100).json()
    assert blocked["status"] == "blocked"

    response = client.delete(f"/invoices/{approved['id']}")
    assert response.status_code == 409 and "aprobada" in response.json()["detail"]

    assert client.delete(f"/invoices/{blocked['id']}").status_code == 204
    assert client.get(f"/invoices/{blocked['id']}").status_code == 404
    assert all(d["invoice_id"] != blocked["id"] for d in client.get("/decisions").json())
    # Sin facturas, el proveedor ya se puede eliminar
    assert client.delete(f"/vendors/{shady}").status_code == 204
    assert client.delete("/invoices/999").status_code == 404


def test_vendor_tax_id_is_normalized_and_unique(client):
    vendor = client.post("/vendors", json={"name": "Acme", "tax_id": "20-123 456.789"}).json()
    assert vendor["tax_id"] == "20123456789"  # igual que lo normaliza el agente al leer facturas
    response = client.post("/vendors", json={"name": "Otra", "tax_id": "20123456789"})
    assert response.status_code == 409 and "Acme" in response.json()["detail"]
    other = client.post("/vendors", json={"name": "Otra"}).json()
    assert client.patch(f"/vendors/{other['id']}", json={"tax_id": "20.123.456.789"}).status_code == 409


def test_review_requires_reviewer_and_log_exports_csv(client):
    client.post("/policies", json=POLICY)
    acme = create_vendor(client)
    escalated = create_invoice(client, acme, "BIG-1", 2000).json()
    create_invoice(client, acme, "OK-1", 100)
    assert escalated["status"] == "escalated"

    # Sin nombre de quien revisa no se acepta la decisión
    no_name = client.post(f"/invoices/{escalated['id']}/review", json={"outcome": "approved", "explanation": "ok"})
    assert no_name.status_code == 422
    blank = client.post(f"/invoices/{escalated['id']}/review", json={"outcome": "approved", "explanation": "ok", "reviewer": "  "})
    assert blank.status_code == 422
    reviewed = client.post(
        f"/invoices/{escalated['id']}/review",
        json={"outcome": "approved", "explanation": "Pago trimestral pactado", "reviewer": "Laura Gómez"},
    ).json()
    assert reviewed["decisions"][-1]["reviewer"] == "Laura Gómez"

    log = client.get("/decisions/log").json()
    assert len(log) == 3
    assert log[0]["decided_by"] == "human" and log[0]["reviewer"] == "Laura Gómez"
    assert log[0]["vendor_name"] == "ACME" and log[0]["invoice_number"] == "BIG-1"
    agent_escalation = next(r for r in log if r["decided_by"] == "agent" and r["outcome"] == "escalated")
    assert agent_escalation["failed_rules"] == ["require_human_above"]
    assert agent_escalation["policy_name"] == "Base"
    assert [r["invoice_number"] for r in client.get("/decisions/log", params={"q": "ok-1"}).json()] == ["OK-1"]
    assert len(client.get("/decisions/log", params={"decided_by": "human"}).json()) == 1

    csv_response = client.get("/decisions/export.csv", params={"outcome": "escalated"})
    assert csv_response.status_code == 200
    assert "attachment" in csv_response.headers["content-disposition"]
    body = csv_response.content.decode("utf-8")
    assert body.startswith("\ufeffFecha;Factura;Proveedor")
    lines = body.strip().splitlines()
    assert len(lines) == 2 and "BIG-1" in lines[1] and "Umbral de revisión humana" in lines[1] and "2000,00" in lines[1]
