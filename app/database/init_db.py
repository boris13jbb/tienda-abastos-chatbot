# init_db.py (completo y corregido)

import logging
from sqlalchemy import text
from app.database.db import engine, Base, SessionLocal
from app.models import Usuario, Productos, PasswordReset, Categoria, Proveedor, Pedido
from app.utils.logger import get_logger
from passlib.context import CryptContext

logger = get_logger(__name__)

# Configurar el contexto de encriptación de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def initialize_database():
    try:
        logger.info("Creando tablas en la base de datos...")
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas creadas correctamente")

        is_sqlite = 'sqlite' in str(engine.url).lower()

        with engine.connect() as conn:
            try:
                if is_sqlite:
                    conn.execute(text(""" 
                        CREATE TABLE IF NOT EXISTS PasswordResets (
                            ID INTEGER PRIMARY KEY AUTOINCREMENT,
                            Email TEXT NOT NULL,
                            Token TEXT NOT NULL,
                            Expiry TIMESTAMP NOT NULL,
                            Used INTEGER DEFAULT 0
                        )
                    """))
                    logger.info("Tabla PasswordResets creada/verificada (SQLite)")
                else:
                    result = conn.execute(text(""" 
                        SELECT COUNT(*) 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_NAME = 'PasswordResets'
                    """))
                    if result.scalar() == 0:
                        logger.info("Creando tabla PasswordResets...")
                        conn.execute(text(""" 
                            CREATE TABLE PasswordResets (
                                ID INT IDENTITY(1,1) PRIMARY KEY,
                                Email NVARCHAR(100) NOT NULL,
                                Token NVARCHAR(100) NOT NULL,
                                Expiry DATETIME NOT NULL,
                                Used BIT DEFAULT 0
                            )
                        """))
                        logger.info("Tabla PasswordResets creada correctamente")
            except Exception as e:
                logger.error(f"Error creando/verificando PasswordResets: {str(e)}")
                logger.info("Continuando con la inicialización...")

        check_and_create_initial_data()
        return True

    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def check_and_create_initial_data():
    try:
        db = SessionLocal()
        try:
            productos_count = db.query(Productos).count()
            if productos_count == 0:
                logger.info("Insertando Productos iniciales...")
                productos_iniciales = [
                    Productos(Nombre="Arroz", Descripcion="Arroz de calidad", Precio=1.5, Stock=100),
                    Productos(Nombre="Monitor 24 pulgadas", Descripcion="Monitor LED Full HD", Precio=150.0, Stock=10),
                    Productos(Nombre="Teclado Mecánico", Descripcion="Teclado gaming RGB", Precio=80.0, Stock=15),
                    Productos(Nombre="Mouse Inalámbrico", Descripcion="Mouse ergonómico", Precio=25.0, Stock=20),
                    Productos(Nombre="Disco SSD 500GB", Descripcion="Unidad de estado sólido", Precio=120.0, Stock=8),
                    Productos(Nombre="Memoria USB 64GB", Descripcion="USB 3.0 de alta velocidad", Precio=18.0, Stock=30),
                    Productos(Nombre="Esfero Azul", Descripcion="Esfero punta fina", Precio=1.5, Stock=100),
                    Productos(Nombre="Cuaderno Universitario", Descripcion="100 hojas cuadriculado", Precio=3.0, Stock=50)
                ]
                db.add_all(productos_iniciales)
                db.commit()
                logger.info(f"Se crearon {len(productos_iniciales)} Productos iniciales")

            usuarios_count = db.query(Usuario).count()
            if usuarios_count == 0:
                logger.info("⚠️  No hay usuarios en el sistema.")
                logger.info("🔐 Para crear el primer administrador, ejecute:")
                logger.info("   python -m app.database.init_admin")
                logger.info("")
                logger.info("📝 O use el endpoint de registro público:")
                logger.info("   POST /api/auth/solicitar-registro")
                logger.info("")
                logger.info("🚨 IMPORTANTE: No hay credenciales por defecto por seguridad.")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error creando datos iniciales: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def create_admin_user(email: str, password: str, nombre: str = "Administrador"):
    """
    Crea un usuario administrador en el sistema.
    
    Args:
        email: Email del administrador
        password: Contraseña del administrador
        nombre: Nombre del administrador
    
    Returns:
        bool: True si se creó correctamente, False en caso contrario
    """
    try:
        db = SessionLocal()
        try:
            # Verificar si el usuario ya existe
            existing_user = db.query(Usuario).filter(Usuario.email == email).first()
            if existing_user:
                logger.warning(f"El usuario {email} ya existe en el sistema.")
                return False
            
            # Crear hash de la contraseña
            hashed_password = pwd_context.hash(password)
            
            # Crear el usuario administrador
            admin_user = Usuario(
                nombre=nombre,
                email=email,
                password=hashed_password,
                rol="admin",
                activo=True,
                permisos_especiales=True
            )
            
            db.add(admin_user)
            db.commit()
            
            logger.info(f"✅ Usuario administrador creado exitosamente:")
            logger.info(f"   Email: {email}")
            logger.info(f"   Nombre: {nombre}")
            logger.info(f"   Rol: admin")
            logger.info(f"   Estado: activo")
            
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creando usuario administrador: {str(e)}")
            return False
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error en create_admin_user: {str(e)}")
        return False

def create_employee_user(email: str, password: str, nombre: str, rol: str = "empleado"):
    """
    Crea un usuario empleado en el sistema.
    
    Args:
        email: Email del empleado
        password: Contraseña del empleado
        nombre: Nombre del empleado
        rol: Rol del empleado (empleado, supervisor, etc.)
    
    Returns:
        bool: True si se creó correctamente, False en caso contrario
    """
    try:
        db = SessionLocal()
        try:
            # Verificar si el usuario ya existe
            existing_user = db.query(Usuario).filter(Usuario.email == email).first()
            if existing_user:
                logger.warning(f"El usuario {email} ya existe en el sistema.")
                return False
            
            # Crear hash de la contraseña
            hashed_password = pwd_context.hash(password)
            
            # Crear el usuario empleado
            employee_user = Usuario(
                nombre=nombre,
                email=email,
                password=hashed_password,
                rol=rol,
                activo=True,
                permisos_especiales=False
            )
            
            db.add(employee_user)
            db.commit()
            
            logger.info(f"✅ Usuario empleado creado exitosamente:")
            logger.info(f"   Email: {email}")
            logger.info(f"   Nombre: {nombre}")
            logger.info(f"   Rol: {rol}")
            logger.info(f"   Estado: activo")
            
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creando usuario empleado: {str(e)}")
            return False
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error en create_employee_user: {str(e)}")
        return False
