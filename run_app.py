#!/usr/bin/env python3
"""
Script para ejecutar la aplicación FastAPI del chatbot de tienda de abastos
"""

import uvicorn
import os
import sys
import logging

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# APLICAR PARCHES ULTRA-AGRESIVOS DE PYTORCH ANTES DE CUALQUIER IMPORTACIÓN
try:
    # Aplicar parche ultra-agresivo antes de importar app
    from app.utils.global_torch_patch import apply_ultra_aggressive_torch_patch, ensure_torch_compatibility
    
    print("Aplicando parches ultra-agresivos de PyTorch...")
    patch_result = apply_ultra_aggressive_torch_patch()
    compatibility_result = ensure_torch_compatibility()
    
    # Usar solo caracteres ASCII para evitar problemas de encoding en Windows
    if patch_result or compatibility_result:
        print("Parches de PyTorch aplicados exitosamente en run_app.py")
    else:
        print("Algunos parches de PyTorch pueden no haberse aplicado completamente")
    
except Exception as emergency_error:
    # Usar solo ASCII en mensajes de error
    print(f"Error aplicando parches de PyTorch en run_app.py: {emergency_error}")
    
    # Parche de emergencia básico como fallback
    try:
        import torch
        if not hasattr(torch, 'amp'):
            torch.amp = type('MockAmp', (), {})()
        if not hasattr(torch.amp, 'autocast'):
            class BasicMockAutocast:
                def __init__(self, *args, **kwargs): pass
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def __call__(self, *args, **kwargs): return self
            torch.amp.autocast = BasicMockAutocast
            print("Parche básico de emergencia aplicado")
    except:
        pass

# Importar configuración centralizada
from app.config.settings import settings

if __name__ == "__main__":
    print("🚀 Iniciando Chatbot Tienda de Abastos...")
    print(f"📍 Puerto: {settings.PORT}")
    print(f"🌐 Host: {settings.HOST}")
    print(f"🔄 Modo: {'Desarrollo' if settings.DEBUG else 'Producción'}")
    print(f"📊 Base de datos: {settings.DATABASE_TYPE}")
    print(f"🤖 LLM Provider: {settings.LLM_PROVIDER}")
    print("-" * 50)
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD_ON_CHANGE,
        log_level=settings.LOG_LEVEL.lower()
    ) 