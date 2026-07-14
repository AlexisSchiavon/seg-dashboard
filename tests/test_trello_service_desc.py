from types import SimpleNamespace

from app.services import trello_service


def test_build_auto_card_desc_has_marker_monto_talento_link():
    deal = SimpleNamespace(pipedrive_id=526, value=1500000.0, currency="MXN")
    desc = trello_service.build_auto_card_desc(
        deal, talent_name="Emicanico", pipedrive_domain="talentagency"
    )
    # Idempotency marker present and parseable.
    assert "[seg:deal_id=526]" in desc
    assert trello_service._extract_deal_id_from_desc(desc) == 526
    # Human context.
    assert "1,500,000" in desc  # monto formatted with thousands separator
    assert "MXN" in desc
    assert "Emicanico" in desc
    assert "https://talentagency.pipedrive.com/deal/526" in desc


def test_build_auto_card_desc_handles_missing_talent():
    deal = SimpleNamespace(pipedrive_id=519, value=35000.0, currency="MXN")
    desc = trello_service.build_auto_card_desc(
        deal, talent_name=None, pipedrive_domain="talentagency"
    )
    assert "Sin talento" in desc
    assert "[seg:deal_id=519]" in desc
