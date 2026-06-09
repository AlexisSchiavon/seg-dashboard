# SEG Talent Intelligence Dashboard

## What This Is

Una plataforma web de inteligencia comercial para Santillán Entertainment Group (agencia de talentos/influencers en México, 21 talentos actuales). Consolida en un solo dashboard los datos de Pipedrive (CRM/funnel comercial), Google Sheets (leads entrantes por Gmail) y Trello (ejecución de campañas y cobranza), con reportes mensuales generados por IA (Claude) y un agente de lenguaje natural embebido para consultar los datos.

## Core Value

Dar visibilidad consolidada y en tiempo real del funnel comercial e ingresos por talento — reemplazando el proceso actual donde el equipo revisa Pipedrive, Sheets y Trello por separado y arma reportes a mano.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Estructura base FastAPI con autenticación JWT y endpoint de health check (M1)
- [ ] Catálogo de talentos administrable (DB/config) — agregar talentos nuevos sin tocar código
- [ ] Integración Pipedrive en vivo: deals, etapas del funnel, producto=talento asignado, campos custom (M2)
- [ ] Cálculo automático de % talento (70% fijo del valor del deal) y manejo de deals "Sin cotizar" ($0 MXN)
- [ ] Integración Google Sheets: ingesta de leads de Gmail clasificados por talento, fuente y estado (M3)
- [ ] Integración Trello: tarjetas de campañas con contrato firmado, fechas de cobro, distinción "en ejecución" vs "en cobranza" (M4)
- [ ] Automatización: deal marcado "ganado" en Pipedrive → crea tarjeta en Trello con fecha de cobro
- [ ] Dashboard — Resumen ejecutivo: KPIs globales, ranking de talentos por revenue, insights IA, actividad reciente
- [ ] Dashboard — Por talento: KPIs, proyección de ingresos mensual (cobrado/proyección/pendiente), calendario de cobranza, funnel individual, oportunidades perdidas, categorías de marca, top 3 campañas del mes, tabla completa de campañas
- [ ] Dashboard — Funnel completo: 6 etapas con conteo y monto, detección de cuellos de botella
- [ ] Dashboard — Leads Gmail: clasificados por talento, fuente y estado
- [ ] Dashboard — Reportes: generación de PDF con Claude AI, historial descargable (M5)
- [ ] Agente de lenguaje natural embebido para consultar datos del dashboard (M6)
- [ ] Deploy vía Docker en EasyPanel (M7)

### Out of Scope

- Roles de usuario diferenciados — todos los usuarios autenticados ven el mismo dashboard por ahora; se puede afinar después si se requiere
- Soporte multi-agencia / multi-tenant — diseño específico para SEG, aunque modular
- Construir M1-M7 simultáneamente — desarrollo incremental, arrancando únicamente con M1

## Context

**Situación actual:** Todo el tracking de revenue/funnel por talento es manual y disperso — el equipo revisa Pipedrive, Google Sheets y Trello por separado, sin vista consolidada, y arma reportes a mano.

**21 talentos actuales:** Navarretes Show, Don Silverio, Don Wicho, Deliberración, Emicanico, Abelito, Mamamecanic, Alan Lopez, Karamella, Mariana, Ale, Elisa, Edgar, Dulce, Reborujados, Victor Halfon, Doc Fitness, Lalo Escalante, Tony Franco, Moni, Casandra Salinas.

**Usuarios:** Dirección/dueño de la agencia (visión ejecutiva: KPIs, ranking, insights) y equipo comercial/ventas (funnel, leads de Gmail). Por ahora mismo nivel de acceso para todos.

**Mockup de referencia:** Existe un mockup HTML funcional (dark mode, mobile-first, 5 tabs: Resumen / Por talento / Funnel / Leads / Reportes) guardado en `.planning/reference/mockup.html`. Sirve como referencia visual y de UX para las fases de UI; se conectará al backend real conforme se construyan los módulos.

**Visión "OpenClaw":** Nombre interno para una futura plataforma de orquestación multi-agente. Este dashboard es el primer módulo de esa visión — la arquitectura debe ser modular para poder agregar después agentes especializados (prospección, WhatsApp, contratos) sin reescribir la base.

**Lógica de negocio — Pipedrive:**
- Talento = producto asignado al deal
- Etapas del funnel: Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza
- % talento = 70% fijo del valor del deal
- Deals con $0 MXN = "Sin cotizar"
- Campos custom por deal: razón de pérdida, categoría de marca, fecha de cobro esperada
- Razones de pérdida: Presupuesto insuficiente, No respondieron, Eligieron otro talento, Campaña cancelada, Sin fit estratégico
- Categorías de marca: Moda/Retail, Alimentos/Restaurantes, Agencias, Medios y Entretenimiento, Educación/Gobierno, Otros

**Lógica de negocio — Trello:**
- Solo deals con contrato firmado generan tarjeta
- Diferencia entre "en ejecución de campaña" y "en cobranza"
- Fechas de cobro visibles en la tarjeta
- Automatización: deal ganado en Pipedrive → crear tarjeta en Trello con fecha de cobro

**Módulos en orden de desarrollo:**
1. M1: Estructura base FastAPI + autenticación JWT + health check
2. M2: Integración Pipedrive en vivo
3. M3: Integración Google Sheets (leads Gmail)
4. M4: Integración Trello
5. M5: Reportes PDF con Claude AI
6. M6: Agente de lenguaje natural embebido
7. M7: Deploy + Docker + EasyPanel

**Arrancar únicamente con M1.** No desarrollar todos los módulos de una vez.

## Constraints

- **Tech stack (backend)**: Python 3.12 + FastAPI + SQLite (SQLAlchemy) + python-dotenv + httpx — elección fija, no sustituir framework
- **Tech stack (frontend)**: HTML + CSS + Vanilla JS, dark mode, mobile-first — sin frameworks JS
- **Integraciones**: Pipedrive API, Google Sheets API (gspread + google-auth), Trello API
- **IA**: Anthropic Claude API para reportes PDF (M5) y agente de lenguaje natural (M6)
- **Deploy**: EasyPanel + Docker (M7)
- **Estructura de carpetas predefinida**:
  ```
  seg-dashboard/
  ├── app/
  │   ├── main.py
  │   ├── config.py
  │   ├── models.py
  │   ├── database.py
  │   ├── integrations/ (pipedrive.py, sheets.py, trello.py)
  │   ├── services/ (funnel.py, kpis.py, reports.py, agent.py)
  │   └── routers/ (dashboard.py, talents.py, leads.py, reports.py)
  ├── frontend/ (index.html, css/, js/)
  ├── Dockerfile
  ├── docker-compose.yml
  ├── .env.example
  ├── CLAUDE.md
  └── memory.md
  ```
- **Variables de entorno**: PIPEDRIVE_API_TOKEN, PIPEDRIVE_DOMAIN, GOOGLE_SHEETS_ID, GOOGLE_SERVICE_ACCOUNT_JSON, TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_BOARD_IDS, ANTHROPIC_API_KEY, SECRET_KEY, DATABASE_URL=sqlite:///./seg.db
- **Extensibilidad**: agregar talentos nuevos debe ser posible vía datos/configuración, sin tocar código
- **Orden de build**: estrictamente incremental M1 → M7, validando cada módulo antes de avanzar

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SQLite + SQLAlchemy como base de datos | Simplicidad operativa para single-tenant, fácil de respaldar y desplegar | — Pending |
| Desarrollo incremental M1→M7, arrancando solo con M1 (estructura + JWT + health check) | Validar la base antes de integrar fuentes de datos externas; evitar construir todo a la vez | — Pending |
| Acceso uniforme para todos los usuarios autenticados (sin roles por ahora) | Equipo pequeño (dirección + comercial); simplicidad inicial, roles se afinan después si hace falta | — Pending |
| Arquitectura modular orientada a la futura plataforma "OpenClaw" (multi-agente) | Evitar reescritura cuando se agreguen agentes especializados (prospección, WhatsApp, contratos) | — Pending |
| Talento = producto asignado al deal en Pipedrive, comisión fija 70% | Refleja el modelo de negocio real de la agencia | — Pending |
| Mockup HTML existente como referencia visual (`.planning/reference/mockup.html`) | Ya valida la UX deseada (dark mode, mobile-first, 5 secciones); guía las fases de UI | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-09 after initialization*
