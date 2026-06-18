# app/models.py (final corregido y listo para producción)

from datetime import datetime
from typing import Dict, Any

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

# Declarar Base global
Base = declarative_base()


class Usuario(Base):
    __tablename__ = "Usuarios"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    password = Column(String(100), nullable=False)
    rol = Column(
        String(20), nullable=False, default="empleado"
    )  # dueño, empleado, administrador
    activo = Column(Boolean, default=True)
    permisos_especiales = Column(
        Boolean, default=False
    )  # Para acceso a funciones administrativas
    FechaRegistro = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.ID,
            "nombre": self.nombre,
            "email": self.email,
            "rol": self.rol,
            "activo": self.activo,
            "permisos_especiales": self.permisos_especiales,
            "fechaRegistro": (
                self.FechaRegistro.isoformat() if self.FechaRegistro else None
            ),
        }

    def es_dueño(self) -> bool:
        return self.rol == "dueño"

    def es_empleado(self) -> bool:
        return self.rol in ["empleado", "administrador", "admin", "dueño"]

    def tiene_permisos_administrativos(self) -> bool:
        return (
            self.rol in ["administrador", "admin", "dueño"] or self.permisos_especiales
        )

    def __repr__(self) -> str:
        return f"<Usuario(ID={self.ID}, nombre='{self.nombre}', email='{self.email}', rol='{self.rol}')>"


class Productos(Base):
    __tablename__ = "Productos"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    Nombre = Column(String(100), nullable=False)
    Descripcion = Column(String(500), nullable=True)
    Precio = Column(Float, nullable=False)
    Stock = Column(Integer, nullable=False, default=0)
    FechaCreacion = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.ID,
            "nombre": self.Nombre,
            "descripcion": self.Descripcion,
            "precio": self.Precio,
            "stock": self.Stock,
            "fechaCreacion": (
                self.FechaCreacion.isoformat() if self.FechaCreacion else None
            ),
        }

    def __repr__(self) -> str:
        return (
            f"<Productos(ID={self.ID}, Nombre='{self.Nombre}', Precio={self.Precio})>"
        )


class PasswordReset(Base):
    __tablename__ = "PasswordResets"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    Email = Column(String(100), nullable=False)
    Token = Column(String(100), nullable=False)
    Expiry = Column(DateTime, nullable=False)
    Used = Column(Boolean, default=False)

    def is_valid(self) -> bool:
        return not self.Used and self.Expiry > datetime.utcnow()

    def __repr__(self) -> str:
        return f"<PasswordReset(ID={self.ID}, Email='{self.Email}', Expiry='{self.Expiry}')>"


class Categoria(Base):
    __tablename__ = "Categorias"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    Nombre = Column(String(50), nullable=False, unique=True)
    Descripcion = Column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<Categoria(ID={self.ID}, Nombre='{self.Nombre}')>"


class Proveedor(Base):
    __tablename__ = "Proveedores"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    Nombre = Column(String(100), nullable=False)
    Contacto = Column(String(100), nullable=True)
    Telefono = Column(String(20), nullable=True)
    Email = Column(String(100), nullable=True)
    Direccion = Column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<Proveedor(ID={self.ID}, Nombre='{self.Nombre}')>"


class Pedido(Base):
    __tablename__ = "Pedidos"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    UsuarioID = Column(Integer, ForeignKey("Usuarios.ID"), nullable=False)
    Fecha = Column(DateTime, default=datetime.utcnow)
    Estado = Column(String(20), default="Pendiente")
    Total = Column(Float, nullable=False, default=0.0)

    def __repr__(self) -> str:
        return f"<Pedido(ID={self.ID}, UsuarioID={self.UsuarioID}, Total={self.Total})>"


class SolicitudRegistro(Base):
    __tablename__ = "SolicitudesRegistro"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    password = Column(String(100), nullable=False)
    estado = Column(String(20), default="pendiente")  # pendiente, aprobada, rechazada
    fecha_solicitud = Column(DateTime, default=datetime.utcnow)
    fecha_resolucion = Column(DateTime, nullable=True)
    rol_asignado = Column(String(20), nullable=True)  # El rol que le asignará el admin
    comentarios = Column(String(500), nullable=True)  # Comentarios del admin
    aprobado_por = Column(Integer, ForeignKey("Usuarios.ID"), nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.ID,
            "nombre": self.nombre,
            "email": self.email,
            "estado": self.estado,
            "fecha_solicitud": (
                self.fecha_solicitud.isoformat() if self.fecha_solicitud else None
            ),
            "fecha_resolucion": (
                self.fecha_resolucion.isoformat() if self.fecha_resolucion else None
            ),
            "rol_asignado": self.rol_asignado,
            "comentarios": self.comentarios,
            "aprobado_por": self.aprobado_por,
        }

    def __repr__(self) -> str:
        return f"<SolicitudRegistro(ID={self.ID}, email='{self.email}', estado='{self.estado}')>"
