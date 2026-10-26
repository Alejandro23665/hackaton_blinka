"""Métricas de uso de la IA y de rendimiento (de llamadas_ia y documentos_procesados)."""
from datetime import timedelta

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import settings

router = APIRouter(prefix="/metricas", tags=["métricas"])

COLUMNS = ("rut_proveedor", "folio", "fecha", "firma", "total_neto", "iva", "impuestos", "total")

# Día local (zona horaria del negocio) de un instante
DAY = "(({col}) AT TIME ZONE :tz)::date"


def _rows(session, sql: str, **params) -> list[dict]:
    return [dict(row._mapping) for row in session.execute(text(sql), {"tz": settings.TIMEZONE, **params})]


def _number(value) -> float:
    return float(value or 0)


@router.get("")
def metrics(session: SessionDep, dias: int = Query(30, ge=1, le=366, description="Últimos N días, incluido hoy")):
    today = session.execute(text("SELECT (now() AT TIME ZONE :tz)::date"), {"tz": settings.TIMEZONE}).scalar_one()
    since = today - timedelta(days=dias - 1)
    calls_day = DAY.format(col="creado_en")
    in_period = f"{calls_day} >= :since"

    # --- Uso de IA ---
    calls_by_day = {
        r["fecha"]: r
        for r in _rows(
            session,
            f"""SELECT {calls_day} AS fecha, count(*) AS llamadas, sum(tokens_entrada) AS tokens_entrada,
                       sum(tokens_salida) AS tokens_salida, sum(costo_usd) AS costo_usd
                FROM llamadas_ia WHERE {in_period} GROUP BY 1""",
            since=since,
        )
    }
    by_stage = _rows(
        session,
        f"""SELECT etapa, count(*) AS llamadas, sum(tokens_entrada) AS tokens_entrada,
                   sum(tokens_salida) AS tokens_salida, sum(costo_usd) AS costo_usd
            FROM llamadas_ia WHERE {in_period} GROUP BY etapa ORDER BY etapa""",
        since=since,
    )
    # Documentos leídos por la IA en el periodo (los que tienen llamadas registradas)
    read_documents = session.execute(
        text(f"SELECT count(DISTINCT id_documento) FROM llamadas_ia WHERE id_documento IS NOT NULL AND {in_period}"),
        {"tz": settings.TIMEZONE, "since": since},
    ).scalar_one()
    outcomes = {
        r["resultado"]: r["n"]
        for r in _rows(session, f"SELECT resultado, count(*) AS n FROM llamadas_ia WHERE {in_period} GROUP BY 1", since=since)
    }
    (wait,) = _rows(
        session,
        f"""SELECT count(*) AS tandas, avg(espera) AS promedio, max(espera) AS maxima
            FROM (SELECT id_tanda, max(espera_s) AS espera FROM llamadas_ia
                  WHERE id_tanda IS NOT NULL AND {in_period} GROUP BY id_tanda) t""",
        since=since,
    )

    # --- Rendimiento de la IA (documentos registrados en el periodo) ---
    docs_day = DAY.format(col="creado_en")
    (docs,) = _rows(
        session,
        f"""SELECT count(*) AS documentos,
                   count(*) FILTER (WHERE observaciones = 'LEGIBLE' AND revisado_en IS NULL) AS sin_intervencion,
                   count(*) FILTER (WHERE revisado_en IS NOT NULL) AS revisados,
                   count(*) FILTER (WHERE requiere_revision) AS pendientes,
                   count(*) FILTER (WHERE requiere_revision AND observaciones = 'NO_LEGIBLE') AS pendientes_no_legibles,
                   count(*) FILTER (WHERE requiere_revision AND observaciones = 'DESCUADRE') AS pendientes_descuadre
            FROM documentos_procesados WHERE {docs_day} >= :since""",
        since=since,
    )
    fields = {
        r["campo"]: r
        for r in _rows(
            session,
            f"""SELECT campo, sum(falta) AS faltante, sum(duda) AS dudoso FROM (
                    SELECT unnest(campos_faltantes) AS campo, 1 AS falta, 0 AS duda
                    FROM documentos_procesados WHERE {docs_day} >= :since
                    UNION ALL
                    SELECT unnest(campos_dudosos), 0, 1 FROM documentos_procesados WHERE {docs_day} >= :since
                ) t GROUP BY campo""",
            since=since,
        )
    }
    docs_by_day = {
        r["fecha"]: r["documentos"]
        for r in _rows(
            session,
            f"SELECT {docs_day} AS fecha, count(*) AS documentos FROM documentos_procesados WHERE {docs_day} >= :since GROUP BY 1",
            since=since,
        )
    }

    days = [since + timedelta(days=n) for n in range(dias)]
    total_calls = sum(outcomes.values())
    cost = sum(_number(r["costo_usd"]) for r in calls_by_day.values())
    return {
        "periodo": {"desde": since, "hasta": today, "dias": dias},
        "uso": {
            "llamadas": total_calls,
            "tokens_entrada": sum(int(r["tokens_entrada"] or 0) for r in calls_by_day.values()),
            "tokens_salida": sum(int(r["tokens_salida"] or 0) for r in calls_by_day.values()),
            "costo_usd": round(cost, 6),
            # Todo lo gastado (clasificación incluida) entre los documentos que la IA leyó y guardó
            "documentos_leidos": read_documents,
            "costo_por_documento_usd": round(cost / read_documents, 6) if read_documents else None,
            "modelo": settings.AI_MODEL,
            "por_etapa": [
                {**r, "tokens_entrada": int(r["tokens_entrada"] or 0), "tokens_salida": int(r["tokens_salida"] or 0),
                 "costo_usd": _number(r["costo_usd"])}
                for r in by_stage
            ],
            "por_dia": [
                {
                    "fecha": day,
                    "tokens_entrada": int((calls_by_day.get(day) or {}).get("tokens_entrada") or 0),
                    "tokens_salida": int((calls_by_day.get(day) or {}).get("tokens_salida") or 0),
                    "costo_usd": _number((calls_by_day.get(day) or {}).get("costo_usd")),
                }
                for day in days
            ],
        },
        "ia": {
            **docs,
            "campos": sorted(
                (
                    {"campo": c, "faltante": int(fields[c]["faltante"]), "dudoso": int(fields[c]["dudoso"])}
                    for c in COLUMNS if c in fields
                ),
                key=lambda f: -(f["faltante"] + f["dudoso"]),
            ),
        },
        "sistema": {
            "por_dia": [{"fecha": day, "documentos": docs_by_day.get(day, 0)} for day in days],
            "tandas": wait["tandas"],
            "espera_promedio_s": round(_number(wait["promedio"]), 1) if wait["tandas"] else None,
            "espera_maxima_s": round(_number(wait["maxima"]), 1) if wait["tandas"] else None,
            "resultados": {k: outcomes.get(k, 0) for k in ("OK", "ERROR", "RECHAZO", "FORMATO")},
            "tasa_error": round((total_calls - outcomes.get("OK", 0)) / total_calls, 4) if total_calls else None,
        },
    }
