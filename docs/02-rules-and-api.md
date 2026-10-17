# Paso 3 — Motor de reglas y API

## Motor de reglas (`app/services/rules.py`)

Funciones puras: reciben la factura, el proveedor, la política activa y lo gastado en el periodo,
y devuelven el resultado. No tocan la base de datos, así que se prueban sin Postgres.

| Regla | Severidad | Falla cuando |
|---|---|---|
| `vendor_allowed` | hard | `vendors.is_allowed = false` |
| `active_policy` | soft | No hay política activa |
| `currency_allowed` | hard | La moneda no está en `allowed_currencies` |
| `max_amount_per_invoice` | hard | `amount > max_amount_per_invoice` |
| `period_budget` | hard | `gastado + amount > period_budget` |
| `require_human_above` | soft | `amount > require_human_above` |

**Resultado:** si falla alguna regla hard, la factura queda `blocked`; si no, pero falla alguna
soft, queda `escalated`; si no falla ninguna, `approved`. Siempre se evalúan todas las reglas y
se guardan en `decisions.rules_evaluated`, para que el frontend pueda mostrarlas.

**Gastado en el periodo** = suma de facturas `approved`/`paid` creadas desde el inicio del mes
(`monthly`) o del lunes (`weekly`), en UTC. En el MVP se asume una sola moneda base.

**Duplicados:** no es una regla del motor. La API responde `409` antes de guardar la factura,
y además la BD lo impide con `UNIQUE (vendor_id, invoice_number)`.

## Agente (`app/services/agent.py`)

- `evaluate_invoice`: reúne vendor, política y gasto; aplica las reglas; guarda una `Decision`
  (`decided_by='agent'`) y actualiza `invoices.status` en la misma transacción.
- `review_invoice`: decisión humana sobre una factura `escalated` (`decided_by='human'`,
  sin volver a aplicar reglas).

## Endpoints

Documentación interactiva en `http://localhost:8000/docs`.

| Método | Ruta | Qué hace |
|---|---|---|
| GET / POST | `/vendors` | Listar / crear proveedor |
| GET / PATCH | `/vendors/{id}` | Ver / editar (p. ej. `is_allowed`) |
| GET / POST | `/policies` | Listar / crear (crear una activa desactiva la anterior) |
| GET | `/policies/active` | Política activa |
| GET | `/policies/active/budget` | Presupuesto, gastado y restante del periodo |
| POST | `/policies/{id}/activate` | Volver a activar una política anterior |
| GET | `/invoices?status=&vendor_id=` | Listar facturas |
| POST | `/invoices` | Ingresar factura → el agente decide al instante |
| GET | `/invoices/{id}` | Detalle con proveedor e historial de decisiones |
| POST | `/invoices/{id}/evaluate` | Reevaluar (`pending`, `escalated` o `blocked`) |
| POST | `/invoices/{id}/review` | Decisión humana (`approved`/`blocked`) sobre una `escalated` |
| GET | `/decisions?outcome=&decided_by=` | Log de decisiones |
| GET | `/decisions/{id}` | Detalle de una decisión |

Los montos se devuelven como número en JSON.

### Ejemplo

```http
POST /invoices
{"invoice_number": "INV-2", "vendor_id": 1, "amount": 2000, "currency": "USD", "due_date": "2026-11-30"}
```

```json
{
  "id": 2, "status": "escalated", "amount": 2000.0, "...": "...",
  "decisions": [{
    "outcome": "escalated",
    "decided_by": "agent",
    "explanation": "Escalada a revisión humana: 2.000,00 supera el umbral de revisión 1.000,00.",
    "rules_evaluated": [
      {"rule": "vendor_allowed", "passed": true, "severity": "hard", "detail": "ACME está autorizado"},
      {"rule": "require_human_above", "passed": false, "severity": "soft", "detail": "2.000,00 supera el umbral de revisión 1.000,00"}
    ]
  }]
}
```
