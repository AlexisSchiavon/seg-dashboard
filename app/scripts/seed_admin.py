from app.database import SessionLocal
from app.models import User
from app.auth.security import get_password_hash
from app.config import settings


def seed_admin():
    db = SessionLocal()
    try:
        # 5.5.1: keep the users table lowercase-consistent on every write path.
        admin_email = settings.ADMIN_EMAIL.strip().lower()
        user = db.query(User).filter(User.email == admin_email).first()
        hashed = get_password_hash(settings.ADMIN_PASSWORD)
        if user:
            user.hashed_password = hashed  # D-10: idempotent password rotation
            user.is_admin = True
        else:
            user = User(email=admin_email, hashed_password=hashed, is_admin=True)
            db.add(user)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
