"""
API para la autenticación de usuarios.
Define los endpoints para registro, login y gestión de sesiones.
"""

import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Dict, Any

from app.database.db import get_db
from app.utils.logger import get_logger
from app.config.settings import settings
from app.models import Usuario, PasswordReset as DBPasswordReset, SolicitudRegistro
from app.security.auth import (
    create_access_token,
    hash_password,
    require_admin_auth,
    require_auth,
    verify_password,
)

# Configurar logging específico para este módulo
logger = get_logger(__name__)

# Crear router para las rutas de autenticación
router = APIRouter()

# Modelos de datos para la API
class User(BaseModel):
    id: int
    nombre: str
    email: str
    rol: str
    activo: bool = True
    permisos_especiales: bool = False

class UserCreate(BaseModel):
    """Modelo para la creación de usuarios."""
    nombre: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    password: str = Field(..., min_length=6)
    rol: str = Field(default="empleado", pattern="^(dueño|empleado|administrador)$")

class SolicitudRegistroCreate(BaseModel):
    """Modelo para solicitudes de registro público."""
    nombre: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    """Modelo para el login de usuarios."""
    email: str
    password: str

class Token(BaseModel):
    """Modelo para los tokens de autenticación."""
    access_token: str
    token_type: str = "bearer"
    user_info: Dict[str, Any] = {}

class UserInfo(BaseModel):
    """Modelo para la información del usuario."""
    id: int
    nombre: str
    email: str
    rol: str
    activo: bool
    permisos_especiales: bool

class PasswordResetRequest(BaseModel):
    """Modelo para solicitud de restablecimiento de contraseña."""
    email: str

class PasswordReset(BaseModel):
    """Modelo para restablecimiento de contraseña."""
    token: str
    new_password: str = Field(..., min_length=6)

def send_reset_email(to_email: str, reset_url: str):
    """Función para enviar el correo de restablecimiento de contraseña."""
    try:
        logger.info(f"Intentando enviar correo de restablecimiento a {to_email}")
        logger.debug(f"Configuración SMTP: Server={settings.SMTP_SERVER}, Port={settings.SMTP_PORT}")

        msg = MIMEMultipart()
        msg['From'] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = "Restablecimiento de Contraseña"

        body = f"""
Hola,

Has solicitado restablecer tu contraseña. Por favor, haz clic en el siguiente enlace para continuar:

{reset_url}

Si no solicitaste este cambio, puedes ignorar este correo.

Saludos,
{settings.SMTP_FROM_NAME}
"""

        msg.attach(MIMEText(body, 'plain'))

        logger.debug("Iniciando conexión SMTP...")
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

            logger.debug("Enviando correo...")
            server.sendmail(
                settings.SMTP_FROM_EMAIL,
                to_email,
                msg.as_string()
            )

        logger.info(f"Correo enviado exitosamente a {to_email}")

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Error de autenticación SMTP: {str(e)}")
        logger.warning("SMTP no configurado correctamente. El token de reset se ha generado pero no se envió por email.")
        # No lanzar excepción, solo loggear el error
        return
    except smtplib.SMTPException as e:
        logger.error(f"Error SMTP al enviar correo: {str(e)}")
        logger.warning("Error SMTP. El token de reset se ha generado pero no se envió por email.")
        # No lanzar excepción, solo loggear el error
        return
    except Exception as e:
        logger.error(f"Error inesperado al enviar correo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al enviar el correo"
        )

async def get_current_active_user(token_data: Dict[str, Any] = Depends(require_auth), db: Session = Depends(get_db)):
    """
    Obtiene el usuario activo actual desde el token de autenticación.
    """
    try:
        user_id = token_data.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )

        user = db.query(Usuario).filter(Usuario.ID == int(user_id)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        if not user.activo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario inactivo"
            )

        return User(
            id=user.ID,
            nombre=user.nombre,
            email=user.email,
            rol=user.rol,
            activo=user.activo,
            permisos_especiales=user.permisos_especiales,
        )
    except Exception as e:
        logger.error(f"Error al obtener usuario activo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener usuario"
        )

@router.post("/registrar", response_model=Dict[str, str], summary="Registrar nuevo empleado")
async def register(user_data: UserCreate, token_data: dict = Depends(require_admin_auth), db: Session = Depends(get_db)):
    """
    Registra un nuevo empleado. Solo administradores y dueños pueden registrar usuarios.
    """
    try:
        existing_user = db.query(Usuario).filter(Usuario.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email ya registrado"
            )

        hashed_password = hash_password(user_data.password)
        new_user = Usuario(
            nombre=user_data.nombre,
            email=user_data.email,
            password=hashed_password,
            rol=user_data.rol
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"Empleado registrado por {token_data.get('name')}: {user_data.email} (Rol: {user_data.rol})")
        return {"message": "Empleado registrado correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al registrar empleado: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al registrar empleado"
        )

@router.post("/login", response_model=Token, summary="Iniciar sesión")
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Inicia sesión de usuario y devuelve un token JWT.
    Solo empleados autorizados pueden acceder.
    """
    try:
        user = db.query(Usuario).filter(Usuario.email == user_data.email).first()

        logger.debug(f"Intento de login para: {user_data.email}")
        logger.debug(f"Usuario encontrado: {user is not None}")

        if not user:
            logger.warning(f"Login fallido - usuario no encontrado: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales inválidas"
            )

        # Verificar que el usuario esté activo
        if not user.activo:
            logger.warning(f"Login fallido - usuario inactivo: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario inactivo"
            )

        # Verificar que sea empleado autorizado
        if not user.es_empleado():
            logger.warning(f"Login fallido - no es empleado: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado. Solo empleados autorizados."
            )

        valid_password = verify_password(user_data.password, user.password)
        logger.debug(f"Contraseña válida: {valid_password}")

        if not valid_password:
            logger.warning(f"Login fallido - contraseña incorrecta: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales inválidas"
            )

        token_data = {
            "sub": str(user.ID),
            "email": user.email,
            "name": user.nombre,
            "rol": user.rol,
            "permisos_especiales": user.permisos_especiales
        }

        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
        )

        user_info = {
            "id": user.ID,
            "nombre": user.nombre,
            "email": user.email,
            "rol": user.rol,
            "activo": user.activo,
            "permisos_especiales": user.permisos_especiales
        }

        logger.info(f"Inicio de sesión exitoso: {user_data.email} (Rol: {user.rol})")
        return {"access_token": access_token, "token_type": "bearer", "user_info": user_info}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado en login: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/logout", summary="Cerrar sesión")
async def logout():
    """
    Cierra la sesión del usuario (invalidación del lado del cliente).
    """
    try:
        return {"message": "Sesión cerrada correctamente"}
    except Exception as e:
        logger.error(f"Error al cerrar sesión: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al cerrar sesión"
        )

@router.get("/perfil", response_model=UserInfo, summary="Obtener perfil del usuario")
async def get_profile(token_data: Dict[str, Any] = Depends(require_auth), db: Session = Depends(get_db)):
    """
    Obtiene información del perfil del usuario autenticado.
    """
    try:
        user_id = token_data.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )

        user = db.query(Usuario).filter(Usuario.ID == int(user_id)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        return {"id": user.ID, "nombre": user.nombre, "email": user.email}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener perfil: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener perfil"
        )

@router.post("/reset-password-request", response_model=Dict[str, str], summary="Solicitar restablecimiento de contraseña")
async def request_password_reset(request_data: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Solicita un token para restablecer la contraseña.
    """
    try:
        logger.info(f"Solicitud de restablecimiento de contraseña para: {request_data.email}")
        user = db.query(Usuario).filter(Usuario.email == request_data.email).first()

        if not user:
            logger.info(f"Solicitud de restablecimiento para email no registrado: {request_data.email}")
            return {"message": "Si el email está registrado, recibirás un enlace para restablecer tu contraseña"}

        reset_token = secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + timedelta(hours=1)

        existing_tokens = db.query(DBPasswordReset).filter(DBPasswordReset.Email == user.email).all()
        if existing_tokens:
            for token in existing_tokens:
                db.delete(token)
            db.commit()
            logger.info(f"Tokens previos eliminados para {user.email}")

        db_token = DBPasswordReset(
            Email=user.email,
            Token=reset_token,
            Expiry=expiry,
            Used=False
        )

        db.add(db_token)
        db.commit()
        logger.info(f"Token creado para {user.email}")

        reset_url = f"{settings.APP_URL}/reset-password?token={reset_token}"
        try:
            send_reset_email(user.email, reset_url)
            return {"message": "Si el email está registrado, recibirás un enlace para restablecer tu contraseña"}
        except Exception as email_error:
            logger.warning(f"No se pudo enviar email, pero el token fue creado: {email_error}")
            return {"message": "Token de restablecimiento creado. Contacta al administrador si no recibes el email."}

    except Exception as e:
        logger.error(f"Error en request_password_reset: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar la solicitud"
        )

@router.post("/reset-password", response_model=Dict[str, str], summary="Restablecer contraseña")
async def reset_password(reset_data: PasswordReset, db: Session = Depends(get_db)):
    """
    Restablece la contraseña utilizando un token válido.
    """
    try:
        db_token = (
            db.query(DBPasswordReset)
            .filter(DBPasswordReset.Token == reset_data.token, DBPasswordReset.Used == False)
            .first()
        )

        if not db_token:
            logger.warning(f"Intento de uso de token no encontrado: {reset_data.token[:10]}...")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido o expirado"
            )

        if db_token.Expiry < datetime.utcnow():
            logger.warning(f"Intento de uso de token expirado: {reset_data.token[:10]}...")
            db_token.Used = True
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido o expirado"
            )

        user = db.query(Usuario).filter(Usuario.email == db_token.Email).first()
        if not user:
            logger.error(f"Usuario no encontrado para token válido: {db_token.Email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        hashed_password = hash_password(reset_data.new_password)
        user.password = hashed_password
        db_token.Used = True

        db.commit()
        logger.info(f"Contraseña restablecida para: {user.email}")
        return {"message": "Contraseña actualizada correctamente"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al restablecer contraseña: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al restablecer contraseña"
        )

@router.post("/solicitar-registro", response_model=Dict[str, str], summary="Solicitar registro público")
async def solicitar_registro(user_data: SolicitudRegistroCreate, db: Session = Depends(get_db)):
    """
    Solicita registro público. Si no hay usuarios en el sistema, crea el primer administrador.
    Si ya hay usuarios, la solicitud queda pendiente de aprobación del administrador.
    """
    try:
        # Verificar que el email no esté ya registrado
        existing_user = db.query(Usuario).filter(Usuario.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email ya registrado"
            )

        # Verificar si es el primer usuario del sistema
        total_users = db.query(Usuario).count()

        if total_users == 0:
            # Es el primer usuario - crear como administrador automáticamente
            logger.info(f"Creando primer administrador del sistema: {user_data.email}")

            hashed_password = hash_password(user_data.password)
            primer_admin = Usuario(
                nombre=user_data.nombre,
                email=user_data.email,
                password=hashed_password,
                rol="dueño",  # Primer usuario como dueño
                activo=True,
                permisos_especiales=True
            )

            db.add(primer_admin)
            db.commit()
            db.refresh(primer_admin)

            logger.info(f"✅ Primer administrador creado exitosamente: {user_data.email}")

            return {
                "message": "¡Bienvenido! Has sido registrado como el primer administrador del sistema. Ya puedes iniciar sesión.",
                "is_first_admin": True
            }
        else:
            # Ya hay usuarios - crear solicitud pendiente de aprobación
            existing_request = db.query(SolicitudRegistro).filter(
                SolicitudRegistro.email == user_data.email,
                SolicitudRegistro.estado == "pendiente"
            ).first()

            if existing_request:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe una solicitud pendiente con este email"
                )

            # Crear la solicitud de registro
            hashed_password = hash_password(user_data.password)
            solicitud = SolicitudRegistro(
                nombre=user_data.nombre,
                email=user_data.email,
                password=hashed_password,
                estado="pendiente"
            )

            db.add(solicitud)
            db.commit()
            db.refresh(solicitud)

            logger.info(f"Nueva solicitud de registro: {user_data.email}")

            # Notificar al administrador (opcional - por email)
            try:
                notificar_admin_solicitud_nueva(user_data.email, user_data.nombre, db)
            except Exception as e:
                logger.warning(f"No se pudo enviar notificación al admin: {e}")

            return {
                "message": "Solicitud de registro enviada correctamente. Serás notificado por email cuando sea aprobada.",
                "is_first_admin": False
            }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al solicitar registro: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar la solicitud de registro"
        )

def notificar_admin_solicitud_nueva(email_solicitante: str, nombre_solicitante: str, db: Session):
    """Notifica al administrador sobre una nueva solicitud de registro."""
    try:
        # Buscar administradores para notificar
        admins = db.query(Usuario).filter(
            Usuario.rol.in_(["admin", "administrador", "dueño"]),
            Usuario.activo == True
        ).all()

        for admin in admins:
            subject = "Nueva Solicitud de Registro"
            body = f"""
Hola {admin.nombre},

Se ha recibido una nueva solicitud de registro:

- Nombre: {nombre_solicitante}
- Email: {email_solicitante}
- Fecha: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}

Para revisar y aprobar/rechazar esta solicitud, accede al panel de administración.

Saludos,
Sistema de Gestión
"""

            send_reset_email(admin.email, f"{settings.APP_URL}/admin")

    except Exception as e:
        logger.error(f"Error al notificar admin: {e}")

@router.get("/debug/db", tags=["Debug"])
def check_db_connection(db: Session = Depends(get_db)):
    """
    Verifica la conexión a la base de datos.
    """
    try:
        db.execute("SELECT 1")
        return {"db": "✅ Conectado correctamente"}
    except Exception as e:
        return {"db": f"❌ Error: {str(e)}"}

@router.get("/debug/smtp", tags=["Debug"])
async def check_smtp_connection():
    logger.info("Verificando configuración SMTP...")
    logger.debug(f"Server: {settings.SMTP_SERVER}")
    logger.debug(f"Port: {settings.SMTP_PORT}")
    logger.debug(f"User: {settings.SMTP_USER}")
    logger.debug(f"From Email: {settings.SMTP_FROM_EMAIL}")
    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            return {
                "smtp": "✅ Conectado correctamente",
                "server": settings.SMTP_SERVER,
                "port": settings.SMTP_PORT,
                "user": settings.SMTP_USER,
                "from_email": settings.SMTP_FROM_EMAIL
            }
    except Exception as e:
        logger.error(f"Error al verificar SMTP: {str(e)}")
        return {
            "smtp": f"❌ Error: {str(e)}",
            "server": settings.SMTP_SERVER,
            "port": settings.SMTP_PORT,
            "user": settings.SMTP_USER,
            "from_email": settings.SMTP_FROM_EMAIL
        }
