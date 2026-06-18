"""
Módulo central de seguridad y autenticación.
Hashing, JWT y dependencias de autorización reutilizables por la API.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.db import get_db
from app.models import Usuario
from app.utils.logger import get_logger

logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

try:
    import bcrypt as _bcrypt

    def hash_password(password: str) -> str:
        return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        if not plain_password or not hashed_password:
            return False
        try:
            return _bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False

except ImportError:
    try:
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        def hash_password(password: str) -> str:
            return pwd_context.hash(password)

        def verify_password(plain_password: str, hashed_password: str) -> bool:
            return pwd_context.verify(plain_password, hashed_password)

    except ImportError:
        def hash_password(password: str) -> str:
            return hashlib.sha256(password.encode()).hexdigest()

        def verify_password(plain_password: str, hashed_password: str) -> bool:
            return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

        logging.warning(
            "Usando fallback SHA256 para hashing de contraseñas. Instala bcrypt para mayor seguridad."
        )


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.JWT_EXPIRATION_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        logger.warning(f"Token inválido: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_auth(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    return verify_token(token)


def _get_active_user_from_token(token_data: Dict[str, Any], db: Session) -> Usuario:
    user_id = token_data.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    user = db.query(Usuario).filter(Usuario.ID == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if not user.activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")
    return user


def require_employee_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    token_data = verify_token(token)
    user = _get_active_user_from_token(token_data, db)
    if not user.es_empleado():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Solo empleados autorizados.",
        )
    return token_data


def require_admin_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    token_data = verify_token(token)
    user = _get_active_user_from_token(token_data, db)
    if not user.tiene_permisos_administrativos():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Solo administradores y dueños.",
        )
    return token_data
