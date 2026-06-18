#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Inicialización del paquete app.
Aplica parches críticos de compatibilidad antes de cualquier importación.
"""

# APLICAR PARCHES CRÍTICOS INMEDIATAMENTE
try:
    # Importar y aplicar el parche ultra-agresivo
    from app.utils.global_torch_patch import apply_ultra_aggressive_torch_patch, ensure_torch_compatibility
    
    # Aplicar parche inmediatamente
    patch_result = apply_ultra_aggressive_torch_patch()
    
    # Asegurar compatibilidad
    compatibility_result = ensure_torch_compatibility()
    
    if patch_result or compatibility_result:
        import logging
        logging.getLogger(__name__).info("Parches de PyTorch aplicados en app/__init__.py")
    
except Exception as init_error:
    # No fallar si los parches no se pueden aplicar
    import warnings
    warnings.warn(f"No se pudieron aplicar parches de PyTorch en app/__init__.py: {init_error}")
    pass
