#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para inicializar el primer usuario administrador del sistema.
Este script debe ejecutarse una sola vez para crear el usuario inicial.
"""

import sys
import os
import hashlib
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database.db import SessionLocal
from app.models import Usuario
from app.config.settings import settings
from app.security.auth import hash_password

def create_initial_admin():
    """
    Crea el primer usuario administrador del sistema.
    """
    print("🔐 Inicializando primer usuario administrador...")
    
    # Verificar si ya existe un usuario administrador
    db = SessionLocal()
    try:
        existing_admin = db.query(Usuario).filter(
            Usuario.rol.in_(["dueño", "administrador"])
        ).first()
        
        if existing_admin:
            print(f"⚠️  Ya existe un usuario administrador: {existing_admin.email}")
            print("   No se puede crear otro usuario administrador desde este script.")
            return False
        
        # Solicitar información del administrador
        print("\n📝 Ingrese la información del primer administrador:")
        
        nombre = input("Nombre completo: ").strip()
        if not nombre:
            print("❌ El nombre es obligatorio")
            return False
        
        email = input("Email: ").strip()
        if not email or "@" not in email:
            print("❌ El email es obligatorio y debe ser válido")
            return False
        
        # Verificar si el email ya existe
        existing_user = db.query(Usuario).filter(Usuario.email == email).first()
        if existing_user:
            print(f"❌ Ya existe un usuario con el email: {email}")
            return False
        
        password = input("Contraseña (mínimo 6 caracteres): ").strip()
        if len(password) < 6:
            print("❌ La contraseña debe tener al menos 6 caracteres")
            return False
        
        # Confirmar contraseña
        confirm_password = input("Confirmar contraseña: ").strip()
        if password != confirm_password:
            print("❌ Las contraseñas no coinciden")
            return False
        
        # Seleccionar rol
        print("\n👥 Seleccione el rol:")
        print("1. Dueño (acceso completo)")
        print("2. Administrador (gestión de empleados)")
        
        role_choice = input("Opción (1 o 2): ").strip()
        if role_choice == "1":
            rol = "dueño"
        elif role_choice == "2":
            rol = "administrador"
        else:
            print("❌ Opción inválida. Usando rol de administrador por defecto.")
            rol = "administrador"
        
        # Crear el usuario administrador
        hashed_password = hash_password(password)
        
        new_admin = Usuario(
            nombre=nombre,
            email=email,
            password=hashed_password,
            rol=rol,
            activo=True,
            permisos_especiales=True
        )
        
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        
        print(f"\n✅ Usuario {rol} creado exitosamente!")
        print(f"   Nombre: {nombre}")
        print(f"   Email: {email}")
        print(f"   ID: {new_admin.ID}")
        print(f"   Fecha de creación: {new_admin.FechaRegistro}")
        
        print(f"\n🔐 Ahora puede iniciar sesión en el sistema con:")
        print(f"   Email: {email}")
        print(f"   Contraseña: [la que ingresó]")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al crear el usuario administrador: {str(e)}")
        return False
    finally:
        db.close()

def create_default_employees():
    """
    Crea algunos empleados de ejemplo para pruebas.
    """
    print("\n👥 Creando empleados de ejemplo...")
    
    db = SessionLocal()
    try:
        # Empleados de ejemplo
        example_employees = [
            {
                "nombre": "María González",
                "email": "maria@tienda.com",
                "password": "empleado123",
                "rol": "empleado"
            },
            {
                "nombre": "Carlos Rodríguez",
                "email": "carlos@tienda.com", 
                "password": "empleado123",
                "rol": "empleado"
            },
            {
                "nombre": "Ana Martínez",
                "email": "ana@tienda.com",
                "password": "empleado123", 
                "rol": "empleado"
            }
        ]
        
        created_count = 0
        for emp_data in example_employees:
            # Verificar si ya existe
            existing = db.query(Usuario).filter(Usuario.email == emp_data["email"]).first()
            if existing:
                print(f"   ⚠️  Empleado {emp_data['email']} ya existe")
                continue
            
            # Crear empleado
            hashed_password = hash_password(emp_data["password"])
            new_employee = Usuario(
                nombre=emp_data["nombre"],
                email=emp_data["email"],
                password=hashed_password,
                rol=emp_data["rol"],
                activo=True,
                permisos_especiales=False
            )
            
            db.add(new_employee)
            created_count += 1
            print(f"   ✅ Empleado {emp_data['email']} creado")
        
        db.commit()
        print(f"\n✅ Se crearon {created_count} empleados de ejemplo")
        
        if created_count > 0:
            print("\n🔐 Credenciales de empleados de ejemplo:")
            print("   Email: maria@tienda.com, carlos@tienda.com, ana@tienda.com")
            print("   Contraseña: empleado123")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al crear empleados de ejemplo: {str(e)}")
        return False
    finally:
        db.close()

def main():
    """
    Función principal del script.
    """
    print("🚀 Inicialización del Sistema de Empleados")
    print("=" * 50)
    
    # Crear administrador inicial
    admin_created = create_initial_admin()
    
    if admin_created:
        # Preguntar si crear empleados de ejemplo
        print("\n" + "=" * 50)
        create_examples = input("¿Desea crear empleados de ejemplo para pruebas? (s/n): ").strip().lower()
        
        if create_examples in ["s", "si", "sí", "y", "yes"]:
            create_default_employees()
    
    print("\n🎉 Inicialización completada!")
    print("\n📋 Próximos pasos:")
    print("1. Iniciar el servidor: python main.py")
    print("2. Navegar a: http://localhost:8000")
    print("3. Iniciar sesión con las credenciales creadas")
    print("4. Usar el chatbot para consultas internas")

if __name__ == "__main__":
    main() 