"""Clasificación PDF-readiness por talento (READY / REVIEW / HOLD) sobre data corregida.

READ-ONLY. Reproduce la clasificación de talentos para reporte PDF usando las
definiciones corregidas de Fase 9.8 (cobranza vencida = solo columna 'Cobrar'
saneada; 'Enviar encuesta' y 'Otros pendientes' fuera).

Rúbrica (documentada, aplicada de forma consistente):
  - HOLD   : cobranza vencida severa (> $500K) — datos tan distorsionados que el PDF
             sería engañoso. Bajo la data inflada previa, esto marcaba exactamente a
             Mariana, DSW y Emicanico.
  - REVIEW : cobranza vencida moderada (>0 y <= $500K), o >=1 deal ganado en $0, o
             aparece en un par de duplicados.
  - READY  : datos limpios (incluye talentos sin campañas problemáticas).

Imprime, por talento, la categoría con definición VIEJA (overdue inflado
ejecucion+cobranza) vs NUEVA (corregida) para visibilizar los movimientos.

Uso: PYTHONPATH=. .venv/bin/python scripts/clasificacion_talentos.py
"""
import sqlite3
from collections import Counter
from datetime import date, timedelta

TODAY = date(2026, 7, 2)
CUT_180 = TODAY - timedelta(days=180)
DUP_THRESHOLD_DAYS = 14

con = sqlite3.connect("seg.db")
con.row_factory = sqlite3.Row
cur = con.cursor()


def pd(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


TAL = {r["id"]: r["name"] for r in cur.execute("SELECT id,name FROM talents")}

# --- señales por talento ---
won_count = {}
zero_deals = {}
for r in cur.execute("SELECT talent_id, value FROM deals WHERE status='won'"):
    tid = r["talent_id"]
    won_count[tid] = won_count.get(tid, 0) + 1
    if (r["value"] or 0) == 0:
        zero_deals[tid] = zero_deals.get(tid, 0) + 1

old_overdue = {}   # ejecucion+cobranza <hoy (definición inflada previa)
new_overdue = {}   # cobranza-only saneada (definición 9.8b)
for r in cur.execute(
    "SELECT t.list_state, t.collection_date, d.value, d.add_time, d.talent_id "
    "FROM trello_cards t JOIN deals d ON d.id=t.deal_id WHERE d.status='won'"
):
    cd = pd(r["collection_date"])
    ad = pd(r["add_time"])
    tid = r["talent_id"]
    v = r["value"] or 0
    if not cd or cd >= TODAY:
        continue
    if r["list_state"] in ("ejecucion", "cobranza"):
        old_overdue[tid] = old_overdue.get(tid, 0) + v
    if r["list_state"] == "cobranza" and not (ad and cd < ad) and v > 0 and cd >= CUT_180:
        new_overdue[tid] = new_overdue.get(tid, 0) + v

# duplicados (umbral 14 días add_time) → talentos involucrados
won_rows = list(cur.execute(
    "SELECT pipedrive_id,title,value,talent_id,won_time,add_time FROM deals WHERE status='won'"))
groups = {}
for d in won_rows:
    k = (d["title"].strip().lower(), d["talent_id"] if d["talent_id"] is not None else -1, d["value"])
    groups.setdefault(k, []).append(d)
dup_talents = set()
for k, m in groups.items():
    if len(m) < 2:
        continue
    m = sorted(m, key=lambda x: (pd(x["won_time"]) or date.max, x["pipedrive_id"]))
    oa = pd(m[0]["add_time"])
    for dup in m[1:]:
        da = pd(dup["add_time"])
        if oa and da and abs((da - oa).days) > DUP_THRESHOLD_DAYS:
            continue
        dup_talents.add(m[0]["talent_id"])


HOLD_OVERDUE = 500_000


def classify(tid, overdue_map):
    z = zero_deals.get(tid, 0)
    overdue = overdue_map.get(tid, 0)
    if overdue > HOLD_OVERDUE:
        return "HOLD"
    if overdue > 0 or z >= 1 or tid in dup_talents:
        return "REVIEW"
    return "READY"


# --- reporte por talento (solo talentos reales, no el bucket SIN TALENTO) ---
rows = []
for tid, name in TAL.items():
    old_cat = classify(tid, old_overdue)
    new_cat = classify(tid, new_overdue)
    rows.append((name, won_count.get(tid, 0), zero_deals.get(tid, 0),
                 old_overdue.get(tid, 0), new_overdue.get(tid, 0), old_cat, new_cat))

rows.sort(key=lambda r: (r[6] != r[5], -r[4]))  # movers first, then by new_overdue

print(f"{'talento':24s} won z0  old_over     new_over    OLD -> NEW")
for name, wc, z, oo, no, oc, nc in rows:
    flag = "  <-- cambia" if oc != nc else ""
    print(f"{name[:24]:24s} {wc:3d} {z:2d}  {oo:>10,.0f}  {no:>10,.0f}   {oc:6s}->{nc:6s}{flag}")

old_dist = Counter(r[5] for r in rows)
new_dist = Counter(r[6] for r in rows)
print(f"\nDistribución OLD: {dict(old_dist)}")
print(f"Distribución NEW: {dict(new_dist)}")
con.close()
