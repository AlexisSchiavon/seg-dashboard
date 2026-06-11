from app.database import SessionLocal
from app.models import Talent

TALENT_NAMES = [
    "Navarretes Show",
    "Don Silverio",
    "Don Wicho",
    "Deliberración",
    "Emicanico",
    "Abelito",
    "Mamamecanic",
    "Alan Lopez",
    "Karamella",
    "Mariana",
    "Ale",
    "Elisa",
    "Edgar",
    "Dulce",
    "Reborujados",
    "Victor Halfon",
    "Doc Fitness",
    "Lalo Escalante",
    "Tony Franco",
    "Moni",
    "Casandra Salinas",
]


def seed_talents(session_factory=SessionLocal):
    db = session_factory()
    try:
        existing = {t.name for t in db.query(Talent).all()}
        for name in TALENT_NAMES:
            if name not in existing:
                db.add(Talent(name=name, active=True))  # D-15: products left null
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_talents()
