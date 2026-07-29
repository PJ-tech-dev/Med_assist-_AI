from beanie import Document, Indexed
from app.models.base import TimestampMixin

class User(Document, TimestampMixin):
    email: Indexed(str, unique=True)
    full_name: str
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False

    class Settings:
        name = "users"