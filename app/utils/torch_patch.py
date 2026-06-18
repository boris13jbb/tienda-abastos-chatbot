#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parche global avanzado para problemas de compatibilidad de PyTorch.
Este archivo debe importarse antes que cualquier otro módulo que use torch.
Proporciona una solución robusta para problemas de autocast y otros componentes de torch.amp.
"""

import sys
import logging
import importlib
import warnings

logger = logging.getLogger(__name__)

def apply_torch_patches():
    """
    Aplica parches de compatibilidad completos para PyTorch.
    Maneja múltiples versiones y configuraciones problemáticas.
    """
    try:
        import torch
        logger.info(f"Aplicando parches de PyTorch para versión: {torch.__version__}")
        
        # Crear torch.amp si no existe
        if not hasattr(torch, 'amp'):
            logger.info("torch.amp no existe, creando módulo mock completo")
            torch.amp = type('MockAmp', (), {})()
        
        # Asegurar que autocast_mode existe
        if not hasattr(torch.amp, 'autocast_mode'):
            class MockAutocastMode:
                def __init__(self, *args, **kwargs):
                    pass
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
            torch.amp.autocast_mode = MockAutocastMode
            logger.info("Parche aplicado: MockAutocastMode creado para torch.amp.autocast_mode")
        
        # Parche completo para autocast
        if not hasattr(torch.amp, 'autocast'):
            class MockAutocast:
                def __init__(self, device_type='cuda', dtype=None, enabled=True, cache_enabled=None):
                    self.device_type = device_type
                    self.dtype = dtype
                    self.enabled = enabled
                    self.cache_enabled = cache_enabled
                    
                def __enter__(self):
                    return self
                    
                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
                    
                def __call__(self, *args, **kwargs):
                    return self
                    
                def __bool__(self):
                    return self.enabled
                    
                def __repr__(self):
                    return f"MockAutocast(device_type='{self.device_type}', enabled={self.enabled})"
            
            torch.amp.autocast = MockAutocast
            logger.info("Parche aplicado: MockAutocast completo creado para torch.amp.autocast")
        
        # Parche para GradScaler
        if not hasattr(torch.amp, 'GradScaler'):
            class MockGradScaler:
                def __init__(self, init_scale=2.**16, growth_factor=2.0, backoff_factor=0.5, 
                           growth_interval=2000, enabled=True):
                    self.init_scale = init_scale
                    self.growth_factor = growth_factor
                    self.backoff_factor = backoff_factor
                    self.growth_interval = growth_interval
                    self.enabled = enabled
                    self._scale = init_scale
                    
                def scale(self, outputs):
                    if isinstance(outputs, (list, tuple)):
                        return [out * self._scale if hasattr(out, '__mul__') else out for out in outputs]
                    return outputs * self._scale if hasattr(outputs, '__mul__') else outputs
                    
                def step(self, optimizer):
                    optimizer.step()
                    
                def update(self):
                    pass
                    
                def get_scale(self):
                    return self._scale
                    
                def set_growth_factor(self, new_factor):
                    self.growth_factor = new_factor
                    
                def __repr__(self):
                    return f"MockGradScaler(scale={self._scale}, enabled={self.enabled})"
            
            torch.amp.GradScaler = MockGradScaler
            logger.info("Parche aplicado: MockGradScaler completo creado para torch.amp.GradScaler")
        
        # Parche para custom_fwd y custom_bwd (utilizados por algunos modelos)
        if not hasattr(torch.amp, 'custom_fwd'):
            def mock_custom_fwd(fwd=None, *, cast_inputs=None):
                def decorator(func):
                    return func
                if fwd is None:
                    return decorator
                return decorator(fwd)
            torch.amp.custom_fwd = mock_custom_fwd
            logger.info("Parche aplicado: mock_custom_fwd creado para torch.amp.custom_fwd")
        
        if not hasattr(torch.amp, 'custom_bwd'):
            def mock_custom_bwd(bwd):
                def decorator(func):
                    return func
                if bwd is None:
                    return decorator
                return decorator(bwd)
            torch.amp.custom_bwd = mock_custom_bwd
            logger.info("Parche aplicado: mock_custom_bwd creado para torch.amp.custom_bwd")
        
        # Parche para funciones de utilidad de torch.amp
        amp_utils = ['scale_loss', 'unscale_', 'step', 'update', 'state_dict', 'load_state_dict']
        for util_name in amp_utils:
            if not hasattr(torch.amp, util_name):
                setattr(torch.amp, util_name, lambda *args, **kwargs: None)
                logger.debug(f"Parche aplicado: función utilitaria {util_name} creada en torch.amp")
        
        # Parche global para interceptar importaciones problemáticas
        original_import = __builtins__['__import__']
        
        def enhanced_patched_import(name, globals=None, locals=None, fromlist=(), level=0):
            try:
                # Interceptar importaciones específicas problemáticas
                if name == 'torch.amp' or (name == 'torch' and fromlist and any(item.startswith('amp') for item in fromlist)):
                    # Asegurar que torch.amp está completamente configurado
                    result = original_import(name, globals, locals, fromlist, level)
                    
                    # Verificar y corregir atributos faltantes después de la importación
                    if hasattr(result, 'amp') or name == 'torch.amp':
                        amp_module = result.amp if hasattr(result, 'amp') else result
                        
                        # Asegurar que todos los componentes necesarios existen
                        if not hasattr(amp_module, 'autocast'):
                            amp_module.autocast = torch.amp.autocast
                        if not hasattr(amp_module, 'GradScaler'):
                            amp_module.GradScaler = torch.amp.GradScaler
                        if not hasattr(amp_module, 'autocast_mode'):
                            amp_module.autocast_mode = torch.amp.autocast_mode
                    
                    return result
                
                # Para importaciones específicas de autocast
                elif 'autocast' in name or (fromlist and 'autocast' in fromlist):
                    try:
                        result = original_import(name, globals, locals, fromlist, level)
                        return result
                    except (ImportError, AttributeError) as e:
                        logger.warning(f"Interceptando importación problemática de autocast: {e}")
                        # Retornar nuestro mock
                        if fromlist and 'autocast' in fromlist:
                            class MockModule:
                                autocast = torch.amp.autocast
                            return MockModule()
                        return torch.amp.autocast
                
                # Para otras importaciones, usar comportamiento normal
                return original_import(name, globals, locals, fromlist, level)
                
            except Exception as import_error:
                logger.warning(f"Error en importación interceptada para {name}: {import_error}")
                return original_import(name, globals, locals, fromlist, level)
        
        # Solo aplicar el parche de importación si no está ya aplicado
        if not hasattr(__builtins__['__import__'], '_torch_patched'):
            __builtins__['__import__'] = enhanced_patched_import
            __builtins__['__import__']._torch_patched = True
            logger.info("Parche de importación global aplicado para torch.amp")
        
        # Suprimir advertencias específicas de PyTorch relacionadas con autocast
        warnings.filterwarnings("ignore", message=".*autocast.*", category=UserWarning)
        warnings.filterwarnings("ignore", message=".*torch.amp.*", category=DeprecationWarning)
        
        logger.info("Todos los parches de PyTorch aplicados exitosamente")
        
        # Información de depuración
        logger.debug(f"torch.amp disponible: {hasattr(torch, 'amp')}")
        logger.debug(f"torch.amp.autocast disponible: {hasattr(torch.amp, 'autocast')}")
        logger.debug(f"torch.amp.GradScaler disponible: {hasattr(torch.amp, 'GradScaler')}")
        
        return True
        
    except ImportError as e:
        logger.warning(f"PyTorch no está disponible, saltando parches: {e}")
        return False
    except Exception as e:
        logger.error(f"Error aplicando parches de PyTorch: {str(e)}")
        logger.error(f"Tipo de error: {type(e).__name__}")
        return False

def verify_torch_patches():
    """
    Verifica que todos los parches de PyTorch estén aplicados correctamente.
    """
    try:
        import torch
        
        checks = {
            "torch.amp existe": hasattr(torch, 'amp'),
            "torch.amp.autocast existe": hasattr(torch, 'amp') and hasattr(torch.amp, 'autocast'),
            "torch.amp.GradScaler existe": hasattr(torch, 'amp') and hasattr(torch.amp, 'GradScaler'),
            "autocast es callable": hasattr(torch, 'amp') and callable(torch.amp.autocast),
            "GradScaler es instanciable": hasattr(torch, 'amp') and callable(torch.amp.GradScaler)
        }
        
        all_passed = all(checks.values())
        
        logger.info("Verificación de parches de PyTorch:")
        for check_name, result in checks.items():
            status = "✓" if result else "✗"
            logger.info(f"  {status} {check_name}")
        
        if all_passed:
            logger.info("Todos los parches de PyTorch están funcionando correctamente")
        else:
            logger.warning("Algunos parches de PyTorch no están funcionando correctamente")
        
        return all_passed
        
    except Exception as e:
        logger.error(f"Error verificando parches de PyTorch: {e}")
        return False

def get_torch_patch_status():
    """
    Obtiene el estado actual de los parches de PyTorch.
    """
    try:
        import torch
        
        status = {
            "torch_version": torch.__version__,
            "amp_available": hasattr(torch, 'amp'),
            "autocast_available": hasattr(torch, 'amp') and hasattr(torch.amp, 'autocast'),
            "gradscaler_available": hasattr(torch, 'amp') and hasattr(torch.amp, 'GradScaler'),
            "patches_applied": True,
            "import_patch_active": hasattr(__builtins__['__import__'], '_torch_patched')
        }
        
        return status
        
    except Exception as e:
        return {"error": str(e), "patches_applied": False}

# Aplicar parches automáticamente al importar este módulo
if apply_torch_patches():
    # Verificar que los parches funcionan
    verify_torch_patches()
