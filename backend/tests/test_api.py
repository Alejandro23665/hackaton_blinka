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
    assert len(approved["decisions"][0]["rules_evaluated"]) == 6
    assert approved["raw_data"]["invoice_number"] == "INV-1"

    escalated = create_invoice(client, acme, "INV-2", 2000).json()
    assert escalated["status"] == "escalated"

    blocked = create_invoice(client, shady, "S-1", 100).json()
    assert blocked["status"] == "blocked"
    assert "no está autorizado" in blocked["decisions"][0]["explanation"]

    # Duplicado -> 409
    assert create_invoice(client, acme, "INV-1", 800).status_code == 409

    # Revisión humana aprueba la escalada
    reviewed = client.post(
        f"/invoices/{escalated['id']}/review",
        json={"outcome": "approved", "explanation": "Contrato anual firmado"},
    ).json()
    assert reviewed["status"] == "approved"
    assert [d["decided_by"] for d in reviewed["decisions"]] == ["agent", "human"]

    # Ya aprobada: no se puede revisar ni reevaluar
    assert client.post(
        f"/invoices/{escalated['id']}/review", json={"outcome": "blocked", "explanation": "x"}
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
