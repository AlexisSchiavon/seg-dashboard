# Hallazgos — Fase 5 (para discutir en fase posterior)

Hallazgos descubiertos durante Fase 5 que **NO** se arreglan en esta fase (fuera de
alcance). Documentados para priorizar después.

---

## H-01 — "Sin talento asignado": 45% de los deals sin mapear a un talento

**Severidad**: alta (distorsiona ranking y la lectura de "a quién pertenece el negocio").
**Estado**: no resuelto — requiere decisión de producto + posible limpieza en Pipedrive.

### Datos (post re-sync full, 25-jun-2026, 484 deals)

| Métrica | Valor |
|---------|-------|
| Total deals | 484 ($53,990,266) |
| **Sin talento asignado** | **219 deals ($14,467,500)** |
| % del conteo | **45.2%** |
| % del valor | 26.8% |

### Causa raíz (desglosada con evidencia)

La resolución de talento ocurre en `app/sync/jobs.py`: un deal se mapea a un talento
solo si tiene un **producto de Pipedrive** cuyo `product_id` está en `TalentProduct`
(vía `MANUAL_PRODUCT_MATCHES` / `match_talent_products.py`). Desglose de los 219:

1. **196 deals (89%) NO tienen ningún producto adjunto en Pipedrive.**
   Causa dominante: higiene de datos del equipo de ventas — el deal nunca recibió
   un producto, así que es imposible resolver el talento. Esto NO es un bug del
   dashboard; es un proceso aguas arriba en el CRM.

2. **23 deals (11%) cargan un producto que existe en Pipedrive pero está sin mapear**
   (no tiene entrada en `MANUAL_PRODUCT_MATCHES` ni `TalentProduct`). Top productos:

   | Producto Pipedrive | Deals | Valor | Tipo |
   |--------------------|------:|------:|------|
   | Arq Juve | 4 | $2,100,000 | ¿marca/proyecto, no talento del roster? |
   | Roster | 10 | $195,000 | genérico (no es un talento individual) |
   | Talent Agency | 2 | $95,000 | genérico (la agencia, no un talento) |
   | Calixto Serna | 1 | $350,000 | talento NO en el roster de 21 |
   | Alfredo Larin | 2 | $330,000 | talento NO en el roster |
   | Sebastian | 2 | $225,000 | talento NO en el roster |
   | Doc Fitness | 1 | $164,000 | ¿typo/duplicado de "Dr Fitness" del roster? |
   | maria | 1 | $25,000 | nombre incompleto |

### Preguntas a resolver con Luis (fase posterior)

1. Los 196 deals sin producto: ¿se espera que el equipo adjunte producto siempre?
   ¿Hay un subconjunto que legítimamente no corresponde a ningún talento (ej. servicios
   de la agencia)? → define si "Sin talento" debe seguir existiendo como bucket o
   reducirse con disciplina de captura en Pipedrive.
2. Productos genéricos (Roster, Talent Agency, Arq Juve): ¿son talentos, marcas, o
   líneas de negocio? ¿Deben mapearse a un talento, a un nuevo "talento" agregado, o
   excluirse explícitamente?
3. Talentos fuera del roster (Calixto Serna, Alfredo Larin, Sebastian): ¿son talentos
   activos que faltan en `seed_talents.TALENT_NAMES`? Si sí, agregarlos recupera esos
   deals automáticamente (mismo patrón que la fusión 5.2).
4. "Doc Fitness" vs "Dr Fitness" del roster: confirmar si es el mismo talento mal
   escrito en Pipedrive (típico caso de near-duplicate).

### Esfuerzo estimado de remediación (no-Fase-5)

- Agregar talentos faltantes a `TALENT_NAMES` + `MANUAL_PRODUCT_MATCHES`: ~1h, recupera
  los ~6 deals de talentos fuera de roster.
- Decisión de producto sobre genéricos y deals-sin-producto: requiere reunión con Luis.
- No hay fix de código "rápido" que resuelva el grueso (196 deals sin producto) — es
  proceso/captura en Pipedrive.

---

## H-02 (menor / cosmético) — Los tiles de "Flujo de dinero" no reconcilian visualmente

**Severidad**: baja (cosmético). **Estado**: no resuelto (no es bug de cálculo).

`formatMXN` redondea cada tile de forma independiente a 1 decimal en millones, por lo
que restar los valores **mostrados** no da el valor **mostrado** de "Pendiente":

- Campañas firmadas: $4,660,000 → se muestra **$4.7M**
- Cobrado: $2,130,000 → se muestra **$2.1M**
- Pendiente: $4,660,000 − $2,130,000 = $2,530,000 → se muestra **$2.5M**

`$4.7M − $2.1M = $2.6M` (con valores redondeados) ≠ `$2.5M` (cálculo exacto redondeado).
La fórmula es correcta: `pendiente = max(0, firmadas_won − cobrado)`, sin lógica oculta.

**Opción futura** (si molesta al cliente): mostrar más precisión en estos tiles (ej.
`$4.66M`) o una nota "valores redondeados". No urgente.
