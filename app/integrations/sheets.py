"""Google Sheets client via gspread.

CRITICAL (CLAUDE.md): READ-ONLY integration. Never call ws.update(), ws.append_row(),
ws.insert_row(), ws.delete_rows(), or any write method. Only ws.get_all_values() is
permitted for fetching lead data.

Security note: never log gspread client or worksheet objects — they may reflect
service-account credentials in error messages. Callers in app/sync/jobs.py must
catch exceptions and persist only str(exc).
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FuturesTimeout

import gspread
from google.oauth2.service_account import Credentials
from pydantic import BaseModel, field_validator

from app.config import settings

logger = logging.getLogger(__name__)

_SHEETS_TIMEOUT_SECS = 30

# Fase 8 (8.1): headers read for the lead detail modal. Names verified against the
# LIVE Sheet on 30-jun-2026 (a real sync revealed the brief's "Razon_Validacion"
# was actually "Razon_validacion" — lowercase v — and that Categoria_Detectada
# exists). If a header is renamed/absent we log a WARNING and continue with "" —
# NOT an error (old leads stay valid with NULL values, D7).
_EMAIL_BODY_HEADER = "Email_Completo"
_VALIDATION_REASON_HEADER = "Razon_validacion"
_CATEGORY_HEADER = "Categoria_Detectada"

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def _client() -> gspread.Client:
    """Create authenticated gspread client from GOOGLE_SERVICE_ACCOUNT_JSON env var."""
    sa_info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = Credentials.from_service_account_info(sa_info, scopes=_SCOPES)
    return gspread.authorize(creds)


class SheetLeadRow(BaseModel):
    """Typed representation of one data row from the Leads worksheet.

    Pydantic field_validators coerce raw Sheet strings to Python types
    before any DB write — bad data becomes None/False, never a crash (T-03-04).
    """

    sheet_row_id: int
    remitente_email: str
    remitente_nombre: str
    asunto: str
    fecha_recepcion: str  # Raw string; parsed to datetime in sync job
    talento_mencionado: str
    status_filtrado: str
    score_calidad: int | None
    bloqueado: bool
    convertido_a_prospecto: bool
    # Fase 8 (8.1): raw Sheet text — sanitized (bleach) + size-capped at write-time
    # in app/sync/jobs.py, NOT here. Default "" when the column is empty/absent.
    email_completo: str = ""
    razon_validacion: str = ""
    categoria_detectada: str = ""

    @field_validator("score_calidad", mode="before")
    @classmethod
    def parse_score(cls, v):
        """Coerce Sheet score string → int. Empty or None → None. Garbage → None."""
        if v == "" or v is None:
            return None
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return None

    @field_validator("bloqueado", mode="before")
    @classmethod
    def parse_bool(cls, v):
        """Coerce Sheet boolean cell → Python bool. 'TRUE' → True, else False."""
        return str(v).upper() == "TRUE"

    @field_validator("convertido_a_prospecto", mode="before")
    @classmethod
    def parse_convertido(cls, v):
        """Coerce Sheet boolean cell → Python bool. 'TRUE' → True, else False."""
        return str(v).upper() == "TRUE"


def get_leads_rows() -> list[SheetLeadRow]:
    """Fetch all data rows from the Leads worksheet.

    Returns typed SheetLeadRow list. Single API call — ~0.40s for 730 rows.
    Natural key: sheet_row_id = enumerate index + 2 (header is row 1).

    ASSUMPTION (A1): Sheet is append-only; row numbers are stable across syncs.
    If rows are ever reordered or inserted mid-sheet, truncate leads table and re-sync.

    Times out after _SHEETS_TIMEOUT_SECS seconds to prevent indefinitely blocking
    the background sync thread and locking the concurrency guard.
    """
    def _fetch() -> list:
        gc = _client()
        sh = gc.open_by_key(settings.GOOGLE_SHEETS_ID)
        ws = sh.worksheet("Leads")
        return ws.get_all_values()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_fetch)
        try:
            all_values = future.result(timeout=_SHEETS_TIMEOUT_SECS)
        except _FuturesTimeout:
            raise TimeoutError(
                f"Google Sheets API did not respond within {_SHEETS_TIMEOUT_SECS}s"
            )

    if not all_values:
        return []

    headers = all_values[0]

    # Fase 8 (8.1): warn once per sync if the email-body headers are missing, so a
    # Sheet rename surfaces in logs instead of silently storing empty bodies (D7).
    for expected in (_EMAIL_BODY_HEADER, _VALIDATION_REASON_HEADER, _CATEGORY_HEADER):
        if expected not in headers:
            logger.warning(
                "Leads sheet is missing expected column %r — leads will be synced "
                "with an empty value for it.",
                expected,
            )

    rows = []
    for row_idx, row in enumerate(all_values[1:], start=2):
        # Pad short rows — gspread omits trailing empty cells (Pitfall 2 in RESEARCH.md)
        padded = row + [""] * (len(headers) - len(row))
        row_dict = dict(zip(headers, padded))
        rows.append(
            SheetLeadRow(
                sheet_row_id=row_idx,
                remitente_email=row_dict.get("Remitente_Email", ""),
                remitente_nombre=row_dict.get("Remitente_Nombre", ""),
                asunto=row_dict.get("Asunto", ""),
                fecha_recepcion=row_dict.get("Fecha_Recepcion", ""),
                talento_mencionado=row_dict.get("Talento_Mencionado", ""),
                status_filtrado=row_dict.get("Status_Filtrado", ""),
                score_calidad=row_dict.get("Score_Calidad"),
                bloqueado=row_dict.get("Bloqueado", ""),
                convertido_a_prospecto=row_dict.get("Convertido_a_Prospecto", ""),
                email_completo=row_dict.get(_EMAIL_BODY_HEADER, ""),
                razon_validacion=row_dict.get(_VALIDATION_REASON_HEADER, ""),
                categoria_detectada=row_dict.get(_CATEGORY_HEADER, ""),
            )
        )
    return rows
