from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User, Role

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()

def hash_password(password: str): return pwd.hash(password)
def verify_password(password: str, hashed: str): return pwd.verify(password, hashed)

def create_token(user: User):
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user.id), "role": user.role.value, "exp": exp}, settings.jwt_secret, algorithm="HS256")

def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=["HS256"])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, uid)
    if not user or not user.active:
        raise HTTPException(401, "Inactive or missing account")
    return user

def require_role(*roles: Role):
    def dep(user: User = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, "This action is not allowed for your role")
        return user
    return dep

def automation_auth(x_automation_key: str = Header(default="")):
    if x_automation_key != settings.automation_key:
        raise HTTPException(403, "Invalid automation key")
