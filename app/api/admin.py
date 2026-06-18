"""
API para la administración de usuarios.
Solo el dueño puede acceder a estos endpoints.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models import Usuario, Productos
from app.security.auth import require_admin_auth, hash_password
from app.utils.logger import get_logger
from app.models import SolicitudRegistro
from app.config.settings import settings

# Configurar logging
logger = get_logger(__name__)

# Crear router
router = APIRouter()


# Modelos de datos
class UserUpdate(BaseModel):
    """Modelo para actualizar usuarios."""

    nombre: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
    rol: Optional[str] = Field(None, pattern="^(empleado|administrador|admin|dueño)$")
    activo: Optional[bool] = None
    permisos_especiales: Optional[bool] = None


class UserCreate(BaseModel):
    """Modelo para crear usuarios."""

    nombre: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    password: str = Field(..., min_length=6)
    rol: str = Field(
        default="empleado", pattern="^(empleado|administrador|admin|dueño)$"
    )
    activo: bool = True
    permisos_especiales: bool = False


class UserResponse(BaseModel):
    """Modelo para respuesta de usuarios."""

    id: int
    nombre: str
    email: str
    rol: str
    activo: bool
    permisos_especiales: bool
    fecha_registro: datetime


class AdminStats(BaseModel):
    """Modelo para estadísticas de administración."""

    total_usuarios: int
    usuarios_activos: int
    usuarios_inactivos: int
    empleados: int
    administradores: int


# Modelos para solicitudes de registro
class SolicitudRegistroResponse(BaseModel):
    """Modelo para respuesta de solicitudes de registro."""

    id: int
    nombre: str
    email: str
    estado: str
    fecha_solicitud: datetime
    fecha_resolucion: Optional[datetime] = None
    rol_asignado: Optional[str] = None
    comentarios: Optional[str] = None
    aprobado_por: Optional[int] = None


class SolicitudRegistroUpdate(BaseModel):
    """Modelo para actualizar solicitudes de registro."""

    estado: str = Field(..., pattern="^(aprobada|rechazada)$")
    rol_asignado: Optional[str] = Field(
        None, pattern="^(empleado|administrador|admin|dueño)$"
    )
    comentarios: Optional[str] = None


@router.get(
    "/usuarios", response_model=List[UserResponse], summary="Listar todos los usuarios"
)
async def listar_usuarios(
    db: Session = Depends(get_db), token_data: dict = Depends(require_admin_auth)
):
    """
    Lista todos los usuarios del sistema.
    Solo accesible por administradores y dueños.
    """
    try:
        usuarios = db.query(Usuario).all()
        return [
            UserResponse(
                id=user.ID,
                nombre=user.nombre,
                email=user.email,
                rol=user.rol,
                activo=user.activo,
                permisos_especiales=user.permisos_especiales,
                fecha_registro=user.FechaRegistro,
            )
            for user in usuarios
        ]
    except Exception as e:
        logger.error(f"Error al listar usuarios: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener la lista de usuarios",
        )


@router.get(
    "/usuarios/{user_id}",
    response_model=UserResponse,
    summary="Obtener usuario específico",
)
async def obtener_usuario(
    user_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin_auth),
):
    """
    Obtiene información de un usuario específico.
    """
    try:
        usuario = db.query(Usuario).filter(Usuario.ID == user_id).first()
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
            )

        return UserResponse(
            id=usuario.ID,
            nombre=usuario.nombre,
            email=usuario.email,
            rol=usuario.rol,
            activo=usuario.activo,
            permisos_especiales=usuario.permisos_especiales,
            fecha_registro=usuario.FechaRegistro,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener usuario {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el usuario",
        )


@router.put(
    "/usuarios/{user_id}", response_model=UserResponse, summary="Actualizar usuario"
)
async def actualizar_usuario(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin_auth),
):
    """
    Actualiza información de un usuario.
    """
    try:
        usuario = db.query(Usuario).filter(Usuario.ID == user_id).first()
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
            )

        # Actualizar campos si están presentes
        if user_data.nombre is not None:
            usuario.nombre = user_data.nombre
        if user_data.email is not None:
            # Verificar que el email no esté en uso
            existing_user = (
                db.query(Usuario)
                .filter(Usuario.email == user_data.email, Usuario.ID != user_id)
                .first()
            )
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El email ya está en uso",
                )
            usuario.email = user_data.email
        if user_data.rol is not None:
            usuario.rol = user_data.rol
        if user_data.activo is not None:
            usuario.activo = user_data.activo
        if user_data.permisos_especiales is not None:
            usuario.permisos_especiales = user_data.permisos_especiales
        if user_data.password:
            usuario.password = hash_password(user_data.password)

        db.commit()
        db.refresh(usuario)

        logger.info(f"Usuario {user_id} actualizado por {token_data.get('email')}")

        return UserResponse(
            id=usuario.ID,
            nombre=usuario.nombre,
            email=usuario.email,
            rol=usuario.rol,
            activo=usuario.activo,
            permisos_especiales=usuario.permisos_especiales,
            fecha_registro=usuario.FechaRegistro,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar usuario {user_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar el usuario",
        )


@router.post("/usuarios", response_model=UserResponse, summary="Crear nuevo usuario")
async def crear_usuario(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin_auth),
):
    """
    Crea un nuevo usuario en el sistema.
    """
    try:
        # Verificar que el email no esté en uso
        existing_user = (
            db.query(Usuario).filter(Usuario.email == user_data.email).first()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado",
            )

        # Crear nuevo usuario
        nuevo_usuario = Usuario(
            nombre=user_data.nombre,
            email=user_data.email,
            password=hash_password(user_data.password),
            rol=user_data.rol,
            activo=user_data.activo,
            permisos_especiales=user_data.permisos_especiales,
            FechaRegistro=datetime.now(),
        )

        db.add(nuevo_usuario)
        db.commit()
        db.refresh(nuevo_usuario)

        logger.info(
            f"Nuevo usuario creado por {token_data.get('email')}: {user_data.email}"
        )

        return UserResponse(
            id=nuevo_usuario.ID,
            nombre=nuevo_usuario.nombre,
            email=nuevo_usuario.email,
            rol=nuevo_usuario.rol,
            activo=nuevo_usuario.activo,
            permisos_especiales=nuevo_usuario.permisos_especiales,
            fecha_registro=nuevo_usuario.FechaRegistro,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear usuario: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear el usuario",
        )


@router.delete("/usuarios/{user_id}", summary="Eliminar usuario")
async def eliminar_usuario(
    user_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin_auth),
):
    """
    Elimina un usuario del sistema.
    """
    try:
        usuario = db.query(Usuario).filter(Usuario.ID == user_id).first()
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
            )

        # No permitir eliminar al dueño principal
        if usuario.rol == "dueño":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar al dueño principal",
            )

        db.delete(usuario)
        db.commit()

        logger.info(f"Usuario {user_id} eliminado por {token_data.get('email')}")

        return {"message": "Usuario eliminado correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar usuario {user_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al eliminar el usuario",
        )


class ProductoResponse(BaseModel):
    """Modelo para respuesta de productos en el panel admin."""

    id: int
    nombre: str
    descripcion: Optional[str] = None
    precio: float
    stock: int


@router.get(
    "/productos", response_model=List[ProductoResponse], summary="Listar productos"
)
async def listar_productos(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin_auth),
):
    """Lista productos disponibles para gestión administrativa."""
    try:
        productos = db.query(Productos).order_by(Productos.Nombre.asc()).all()
        return [
            ProductoResponse(
                id=producto.ID,
                nombre=producto.Nombre,
                descripcion=producto.Descripcion,
                precio=producto.Precio,
                stock=producto.Stock,
            )
            for producto in productos
        ]
    except Exception as e:
        logger.error(f"Error al listar productos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener productos",
        )


@router.get(
    "/stats",
    response_model=AdminStats,
    summary="Obtener estadísticas de administración",
)
async def obtener_estadisticas(
    db: Session = Depends(get_db), token_data: dict = Depends(require_admin_auth)
):
    """
    Obtiene estadísticas de usuarios para el panel de administración.
    """
    try:
        total_usuarios = db.query(Usuario).count()
        usuarios_activos = db.query(Usuario).filter(Usuario.activo == True).count()
        usuarios_inactivos = total_usuarios - usuarios_activos
        empleados = db.query(Usuario).filter(Usuario.rol == "empleado").count()
        administradores = (
            db.query(Usuario)
            .filter(Usuario.rol.in_(["administrador", "admin", "dueño"]))
            .count()
        )

        return AdminStats(
            total_usuarios=total_usuarios,
            usuarios_activos=usuarios_activos,
            usuarios_inactivos=usuarios_inactivos,
            empleados=empleados,
            administradores=administradores,
        )
    except Exception as e:
        logger.error(f"Error al obtener estadísticas: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estadísticas",
        )


@router.get(
    "/solicitudes",
    response_model=List[SolicitudRegistroResponse],
    summary="Listar solicitudes de registro",
)
async def listar_solicitudes(
    db: Session = Depends(get_db), token_data: dict = Depends(require_admin_auth)
):
    """
    Lista todas las solicitudes de registro.
    Solo accesible por administradores y dueños.
    """
    try:
        solicitudes = (
            db.query(SolicitudRegistro)
            .order_by(SolicitudRegistro.fecha_solicitud.desc())
            .all()
        )
        return [
            SolicitudRegistroResponse(
                id=solicitud.ID,
                nombre=solicitud.nombre,
                email=solicitud.email,
                estado=solicitud.estado,
                fecha_solicitud=solicitud.fecha_solicitud,
                fecha_resolucion=solicitud.fecha_resolucion,
                rol_asignado=solicitud.rol_asignado,
                comentarios=solicitud.comentarios,
                aprobado_por=solicitud.aprobado_por,
            )
            for solicitud in solicitudes
        ]
    except Exception as e:
        logger.error(f"Error al listar solicitudes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener la lista de solicitudes",
        )


@router.put(
    "/solicitudes/{solicitud_id}",
    response_model=SolicitudRegistroResponse,
    summary="Aprobar/rechazar solicitud",
)
async def procesar_solicitud(
    solicitud_id: int,
    solicitud_data: SolicitudRegistroUpdate,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin_auth),
):
    """
    Aprueba o rechaza una solicitud de registro y crea el usuario si es aprobada.
    """
    try:
        solicitud = (
            db.query(SolicitudRegistro)
            .filter(SolicitudRegistro.ID == solicitud_id)
            .first()
        )
        if not solicitud:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada"
            )

        if solicitud.estado != "pendiente":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La solicitud ya fue procesada",
            )

        # Actualizar la solicitud
        solicitud.estado = solicitud_data.estado
        solicitud.fecha_resolucion = datetime.utcnow()
        solicitud.comentarios = solicitud_data.comentarios
        solicitud.aprobado_por = token_data.get("sub")

        if solicitud_data.estado == "aprobada":
            if not solicitud_data.rol_asignado:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Debe asignar un rol para aprobar la solicitud",
                )

            solicitud.rol_asignado = solicitud_data.rol_asignado

            # Crear el usuario real
            nuevo_usuario = Usuario(
                nombre=solicitud.nombre,
                email=solicitud.email,
                password=solicitud.password,  # Ya está hasheada
                rol=solicitud_data.rol_asignado,
                activo=True,
                permisos_especiales=False,
            )

            db.add(nuevo_usuario)

            # Enviar correo de aprobación al usuario
            try:
                enviar_correo_aprobacion(
                    solicitud.email, solicitud.nombre, solicitud_data.rol_asignado
                )
            except Exception as e:
                logger.warning(f"No se pudo enviar correo de aprobación: {e}")

        elif solicitud_data.estado == "rechazada":
            # Enviar correo de rechazo al usuario
            try:
                enviar_correo_rechazo(
                    solicitud.email, solicitud.nombre, solicitud_data.comentarios
                )
            except Exception as e:
                logger.warning(f"No se pudo enviar correo de rechazo: {e}")

        # Guardar los datos de la solicitud antes de eliminarla
        solicitud_data_response = SolicitudRegistroResponse(
            id=solicitud.ID,
            nombre=solicitud.nombre,
            email=solicitud.email,
            estado=solicitud.estado,
            fecha_solicitud=solicitud.fecha_solicitud,
            fecha_resolucion=solicitud.fecha_resolucion,
            rol_asignado=solicitud.rol_asignado,
            comentarios=solicitud.comentarios,
            aprobado_por=solicitud.aprobado_por,
        )

        # Eliminar la solicitud después de procesarla
        db.delete(solicitud)
        db.commit()

        logger.info(
            f"Solicitud {solicitud_id} {solicitud_data.estado} y eliminada por {token_data.get('email')}"
        )

        return solicitud_data_response

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al procesar solicitud {solicitud_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar la solicitud",
        )


@router.delete("/solicitudes/{solicitud_id}", summary="Eliminar solicitud de registro")
async def eliminar_solicitud(
    solicitud_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin_auth),
):
    """
    Elimina una solicitud de registro manualmente.
    Solo accesible por administradores y dueños.
    """
    try:
        solicitud = (
            db.query(SolicitudRegistro)
            .filter(SolicitudRegistro.ID == solicitud_id)
            .first()
        )
        if not solicitud:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada"
            )

        # Guardar información para el log antes de eliminar
        solicitud_info = {
            "id": solicitud.ID,
            "email": solicitud.email,
            "nombre": solicitud.nombre,
            "estado": solicitud.estado,
        }

        # Eliminar la solicitud
        db.delete(solicitud)
        db.commit()

        logger.info(
            f"Solicitud {solicitud_id} eliminada manualmente por {token_data.get('email')}: {solicitud_info}"
        )

        return {
            "message": f"Solicitud de {solicitud_info['nombre']} eliminada correctamente"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al eliminar solicitud {solicitud_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al eliminar la solicitud",
        )


def enviar_correo_aprobacion(email: str, nombre: str, rol: str):
    """Envía correo de aprobación al usuario."""
    subject = "Solicitud de Registro Aprobada"
    body = f"""
Hola {nombre},

Tu solicitud de registro ha sido aprobada.

- Rol asignado: {rol}
- Email: {email}

Ya puedes iniciar sesión en el sistema usando tu email y contraseña.

Saludos,
Sistema de Gestión
"""

    # Usar la función existente de envío de correo
    from app.api.auth import send_reset_email

    send_reset_email(email, f"{settings.APP_URL}")


def enviar_correo_rechazo(email: str, nombre: str, comentarios: str = None):
    """Envía correo de rechazo al usuario."""
    subject = "Solicitud de Registro Rechazada"
    body = f"""
Hola {nombre},

Tu solicitud de registro ha sido rechazada.

"""

    if comentarios:
        body += f"Comentarios: {comentarios}\n\n"

    body += """
Si tienes alguna pregunta, contacta al administrador.

Saludos,
Sistema de Gestión
"""

    # Usar la función existente de envío de correo
    from app.api.auth import send_reset_email

    send_reset_email(email, f"{settings.APP_URL}")
