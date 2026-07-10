from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.config import get_settings
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RegisterIn(BaseModel):
    username: str
    email:    EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type:   str = "bearer"


def _create_token(user_id: int) -> str:
    cfg = get_settings()
    exp = datetime.utcnow() + timedelta(minutes=cfg.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, cfg.secret_key, cfg.jwt_algorithm)


async def get_current_user(token: str = Depends(oauth2), db: AsyncSession = Depends(get_db)) -> User:
    cfg = get_settings()
    credentials_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    try:
        payload = jwt.decode(token, cfg.secret_key, algorithms=[cfg.jwt_algorithm])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise credentials_exc
    user = await db.get(User, uid)
    if not user or not user.is_active:
        raise credentials_exc
    return user


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email já cadastrado")
    user = User(
        username=body.username,
        email=body.email,
        password_hash=pwd_ctx.hash(body.password),
    )
    db.add(user)
    await db.flush()
    return {"id": user.id, "username": user.username, "token": _create_token(user.id)}


@router.post("/token", response_model=TokenOut)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()
    if not user or not pwd_ctx.verify(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário ou senha incorretos")
    user.last_seen = datetime.utcnow()
    return TokenOut(access_token=_create_token(user.id))
