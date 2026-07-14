from app.services import audit


def test_trello_card_created_is_a_known_action():
    assert "TRELLO_CARD_CREATED" in audit.ACTION_TYPES
