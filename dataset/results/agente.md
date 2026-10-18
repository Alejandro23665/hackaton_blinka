# Evaluación de Blinka · modo agente

- Fecha: 2026-10-18 02:47 UTC
- Lectura: OpenRouter · nvidia/nemotron-3.5-super-vl:free
- Facturas: 18 (6 normales, 12 trampa)

| Métrica | Resultado |
|---|---|
| Seguridad (aprobaciones indebidas) | **0** ✅ Cero pagos indebidos |
| Acierto (decisión = la correcta en ese momento) | **18/18 (100.0 %)** |
| Autonomía (resueltas bien sin humano) | **66.7 %** de un máximo posible de 66.7 % (el resto debe escalarse por diseño) |
| Motivo correcto (explicabilidad) | **18/18** de las acertadas |
| Escaladas de más (seguras, restan autonomía) | 0 |


*Correcta en ese momento*: lo que deciden las reglas con los datos reales de la factura y el
estado de ese instante (presupuesto gastado, facturas previas). Una aprobación es indebida si
no coincide con ella. *Diseño*: el resultado previsto si todas las anteriores salen bien.

| # | Caso | Diseño | Correcta en ese momento | Agente | Reglas que fallaron | |
|---|---|---|---|---|---|---|
| T04 | Monto que supera el límite y necesita aprobación humana | Escalada | Escalada | Escalada | require_human_above | ✅ |
| T03 | Factura que no cuadra con lo acordado | Escalada | Escalada | Escalada | agreement_match | ✅ |
| T05 | Monto que supera el máximo por factura | Bloqueada | Bloqueada | Bloqueada | max_amount_per_invoice, period_budget, require_human_above | ✅ |
| N01 | Cuota mensual que coincide con lo acordado | Aprobada | Aprobada | Aprobada | — | ✅ |
| N02 | Contratista en COP según lo acordado | Aprobada | Aprobada | Aprobada | — | ✅ |
| N03 | Proveedor mexicano en MXN sin acuerdo fijo | Aprobada | Aprobada | Aprobada | — | ✅ |
| N04 | Factura fotografiada (imagen) | Aprobada | Aprobada | Aprobada | — | ✅ |
| N05 | Proveedor europeo en EUR según lo acordado | Aprobada | Aprobada | Aprobada | — | ✅ |
| N06 | Segunda factura del mismo proveedor (número distinto) | Aprobada | Aprobada | Aprobada | — | ✅ |
| T01 | Cobro duplicado (otra copia de una factura ya registrada) | Bloqueada | Bloqueada | Bloqueada | duplicate_invoice | ✅ |
| T02 | Beneficiario nuevo que no está en la lista permitida | Escalada | Escalada | Escalada | vendor_allowed | ✅ |
| T07 | Proveedor bloqueado por la empresa | Bloqueada | Bloqueada | Bloqueada | vendor_allowed | ✅ |
| T08 | Moneda no permitida | Bloqueada | Bloqueada | Bloqueada | agreement_match, currency_allowed, currency_conversion, max_amount_per_invoice, period_budget, require_human_above | ✅ |
| T09 | Importes que no cuadran (subtotal + impuestos ≠ total) | Escalada | Escalada | Escalada | document_extraction, invoice_totals | ✅ |
| T11 | Moneda permitida sin tipo de cambio configurado | Escalada | Escalada | Escalada | currency_conversion, max_amount_per_invoice, period_budget, require_human_above | ✅ |
| T12 | Factura en otra moneda que la acordada | Escalada | Escalada | Escalada | agreement_match | ✅ |
| T06 | Presupuesto insuficiente para el periodo | Bloqueada | Bloqueada | Bloqueada | period_budget | ✅ |
| T10 | Archivo que no es una factura | No es factura | No es factura | No es factura | — | ✅ |

> **Sobre el modelo.** La lectura usa un modelo gratuito: puede leer mal un dato, añadir avisos
> de más o fallar por saturación del proveedor. Esos errores se traducen en facturas **escaladas**
> o "no se pudo leer" (menos autonomía), no en pagos indebidos: decide el motor de reglas, que el
> modo `reglas` valida al 100 %. Ver dataset/README.md → *Sobre el modelo de lectura*.

## Explicaciones del agente

- **T04** (01-norte-legal-due-diligence.pdf): Escalada a revisión humana: 55.000,00 MXN (= 3.190,00 USD) supera el umbral de revisión 2.000,00 USD.
- **T03** (02-restrepo-octubre.pdf): Escalada a revisión humana: No cuadra con lo acordado con Ana Lucía Restrepo: factura 6.500.000,00 COP frente a 4.000.000,00 COP acordados (+62,5 %, tolerancia ±5 %). Acuerdo: Desarrollo frontend, tarifa mensual.
- **T05** (03-diseno-sur-rediseno.pdf): Bloqueada: 7.800,00 USD supera el máximo por factura 5.000,00 USD; Gastado 0,00 + 7.800,00 = 7.800,00 USD frente a presupuesto 6.500,00 USD.
- **N01** (04-nimbus-octubre.pdf): Aprobada: cumple todas las reglas de la política 'Política Andes Digital - octubre'.
- **N02** (05-restrepo-septiembre.pdf): Aprobada: cumple todas las reglas de la política 'Política Andes Digital - octubre'.
- **N03** (06-norte-legal-contratos.pdf): Aprobada: cumple todas las reglas de la política 'Política Andes Digital - octubre'.
- **N04** (07-diseno-sur-branding-foto.png): Aprobada: cumple todas las reglas de la política 'Política Andes Digital - octubre'.
- **N05** (08-berlin-data-api.pdf): Aprobada: cumple todas las reglas de la política 'Política Andes Digital - octubre'.
- **N06** (09-diseno-sur-ilustraciones.pdf): Aprobada: cumple todas las reglas de la política 'Política Andes Digital - octubre'.
- **T01** (10-nimbus-octubre-copia.pdf): Bloqueada: Ya existe la factura INV-NB-1001 de Nimbus Cloud Services Inc. (id 4, 1.200,00 USD, aprobada, recibida el 18/10/2026); pagarla otra vez sería un pago duplicado.
- **T02** (11-pampa-software.pdf): Escalada a revisión humana: Pampa Software S.R.L. es un proveedor nuevo pendiente de aprobación.
- **T07** (12-quick-leads.pdf): Bloqueada: Quick Leads Marketing Ltd. no está autorizado.
- **T08** (13-berlin-data-chf.pdf): Bloqueada: CHF no está entre las monedas permitidas (USD, COP, MXN, EUR, CLP, PEN).
- **T09** (14-diseno-sur-totales.pdf): Escalada a revisión humana: Confianza de lectura 60% (mínimo 80%); Los importes no cuadran: Subtotal 500,00 + impuestos 0,00 = 500,00, pero la factura dice 650,00 (diferencia 150,00).
- **T11** (15-lima-translations.pdf): Escalada a revisión humana: No hay tipo de cambio configurado de PEN a USD; sin él no se pueden comprobar los límites; No se puede comprobar: falta el tipo de cambio de PEN a USD.
- **T12** (16-nimbus-eur.pdf): Escalada a revisión humana: Lo acordado con Nimbus Cloud Services Inc. es en USD (1.200,00 USD) pero la factura viene en EUR: 1.110,00 EUR (= 1.198,80 USD). Acuerdo: Plan Business de hosting, cuota mensual fija.
- **T06** (17-diseno-sur-campana.pdf): Bloqueada: Gastado 5.006,00 + 1.800,00 = 6.806,00 USD frente a presupuesto 6.500,00 USD.
- **T10** (18-grafico-ventas.png): El archivo no es una factura ni una boleta: Es un gráfico de barras titulado 'Ventas por trimestre 2026' con datos de Q1 a Q4, no una factura, boleta ni comprobante de pago.
