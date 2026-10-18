# Paso 3 — Motor de reglas y API

## Motor de reglas (`app/services/rules.py`)

Funciones puras: reciben la factura, el proveedor, la política activa y lo gastado en el periodo,
y devuelven el resultado. No tocan la base de datos, así que se prueban sin Postgres.

| Regla | Severidad | Falla cuando |
|---|---|---|
| `vendor_allowed` | hard | `vendors.is_allowed = false` (soft si es un proveedor nuevo pendiente) |
| `duplicate_invoice` | hard | Ya existe otra factura anterior del mismo proveedor con el mismo número |
| `agreement_match` | soft | El proveedor tiene un monto acordado y la factura se desvía más que la tolerancia, o viene en otra moneda |
| `invoice_totals` | soft | (Facturas subidas) subtotal + impuestos ≠ total, con margen de 0,05 o 0,1 % |
| `active_policy` | soft | No hay política activa |
| `currency_allowed` | hard | La moneda no está en `allowed_currencies` |
| `currency_conversion` | soft | No hay tipo de cambio para llevar la factura a la moneda base |
| `max_amount_per_invoice` | hard | monto **convertido** > `max_amount_per_invoice` |
| `period_budget` | hard | gastado + monto convertido > `period_budget` (soft si no se puede calcular) |
| `require_human_above` | soft | monto **convertido** > `require_human_above` |

**Resultado:** si falla alguna regla hard, la factura queda `blocked`; si no, pero falla alguna
soft, queda `escalated`; si no falla ninguna, `approved`. Siempre se evalúan todas las reglas y
se guardan en `decisions.rules_evaluated`, para que el frontend pueda mostrarlas.

**Monedas.** Cada política tiene una `base_currency` (por defecto USD) en la que se expresan sus
límites y su presupuesto. La empresa define tipos de cambio en `/exchange-rates` como "1 unidad =
X USD" (USD es la moneda pivote). Antes de aplicar límites, cada factura se convierte a la moneda
base y la conversión queda escrita en la decisión (p. ej. `4.900,00 GBP (= 6.223,00 USD)`).
Si falta el tipo de cambio, esas reglas quedan "no comprobables" y la factura se **escala**:
el agente nunca aprueba algo que no puede verificar.

**Gastado en el periodo** = suma, convertida a la moneda base, de las facturas `approved`/`paid`
creadas desde el inicio del mes (`monthly`) o del lunes (`weekly`), en UTC, con los tipos de
cambio vigentes. Si alguna está en una moneda sin tipo de cambio, el presupuesto no se puede
comprobar y la nueva factura se escala.

**Lo acordado:** cada proveedor puede tener `agreed_amount`, `agreed_currency`,
`agreement_tolerance_pct` (5 % por defecto) y `agreement_notes`. Sin acuerdo la regla no aplica.
Si hay acuerdo, el monto se compara (convertido si hace falta) y el detalle indica lo acordado,
lo facturado y el % de desvío. Es *soft*: una diferencia puede ser legítima, así que decide una persona.

**Duplicados:** la factura duplicada se guarda igualmente (migración `0003` quitó el `UNIQUE`)
y el agente la **bloquea** con la regla `duplicate_invoice`, explicando cuál es la original
(id, importe, estado y fecha). La original nunca se marca como duplicada: solo las posteriores.

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
| DELETE | `/vendors/{id}` | Eliminar; `409` si tiene facturas (hay que bloquearlo en su lugar) |
| GET / POST | `/policies` | Listar / crear (crear una activa desactiva la anterior) |
| GET | `/policies/active` | Política activa |
| GET | `/policies/active/budget` | Presupuesto, gastado y restante del periodo |
| POST | `/policies/{id}/activate` | Volver a activar una política anterior |
| DELETE | `/policies/{id}` | Eliminar; sus decisiones conservan reglas y explicación (`policy_id` queda en null) |
| GET | `/exchange-rates` | Tipos de cambio configurados |
| PUT | `/exchange-rates/{moneda}` | Crear/actualizar `{"usd_per_unit": 1.08}` |
| DELETE | `/exchange-rates/{moneda}` | Eliminar (`409` si es la moneda base de una política) |
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
