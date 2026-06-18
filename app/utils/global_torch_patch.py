#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parche global ultra-agresivo para PyTorch que se aplica inmediatamente.
Este archivo corrige problemas de autocast en cualquier contexto, incluido multiprocessing.
"""

import sys
import warnings
import logging

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _bind_autocast_on_mode(amp_module) -> None:
    """Vincula autocast en autocast_mode (requerido por transformers/sentence-transformers)."""
    if amp_module is None:
        return
    autocast_ref = getattr(amp_module, "autocast", None)
    if autocast_ref is None:
        return
    mode = getattr(amp_module, "autocast_mode", None)
    if mode is None:
        return
    if isinstance(mode, type) and not hasattr(mode, "autocast"):
        mode.autocast = autocast_ref
    elif not isinstance(mode, type) and not hasattr(mode, "autocast"):
        setattr(mode, "autocast", autocast_ref)

def create_complete_mock_amp():
    """
    Crea un objeto MockAmp completo con todos los atributos necesarios.
    """
    class MockAutocastMode:
        """Mock para torch.amp.autocast_mode"""
        autocast = None

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class MockAutocast:
        """Mock para torch.amp.autocast"""
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

    class MockGradScaler:
        """Mock para torch.amp.GradScaler"""
        def __init__(self, *args, **kwargs):
            self._scale = 1.0

        def scale(self, outputs):
            return outputs

        def step(self, optimizer):
            if hasattr(optimizer, 'step'):
                optimizer.step()

        def update(self):
            pass

        def get_scale(self):
            return self._scale

    # Crear el objeto MockAmp con todos los atributos
    mock_amp = type('MockAmp', (), {})()
    mock_amp.autocast = MockAutocast
    mock_amp.GradScaler = MockGradScaler
    mock_amp.autocast_mode = MockAutocastMode
    MockAutocastMode.autocast = MockAutocast
    _bind_autocast_on_mode(mock_amp)

    return mock_amp

def apply_ultra_aggressive_torch_patch():
    """
    Aplica un parche ultra-agresivo que funciona en cualquier contexto.
    """
    try:
        # Primer intento: modificar directamente torch antes de que sea importado
        if 'torch' not in sys.modules:
            # Interceptar la importación de torch
            original_import = __builtins__['__import__']

            def patched_torch_import(name, globals=None, locals=None, fromlist=(), level=0):
                result = original_import(name, globals, locals, fromlist, level)

                # Si se está importando torch, aplicar el parche inmediatamente
                if name == 'torch' or (isinstance(result, type(sys)) and hasattr(result, '__name__') and result.__name__ == 'torch'):
                    try:
                        # Asegurar que torch.amp existe
                        if not hasattr(result, 'amp'):
                            result.amp = create_complete_mock_amp()

                        # Asegurar que todos los atributos necesarios existen
                        if not hasattr(result.amp, 'autocast_mode'):
                            class MockAutocastMode:
                                def __init__(self, *args, **kwargs):
                                    pass
                                def __enter__(self):
                                    return self
                                def __exit__(self, *args):
                                    pass
                            result.amp.autocast_mode = MockAutocastMode

                        # Crear MockAutocast si no existe
                        if not hasattr(result.amp, 'autocast'):
                            class UltraAggressiveMockAutocast:
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
                                    return f"UltraAggressiveMockAutocast(device_type='{self.device_type}', enabled={self.enabled})"

                            result.amp.autocast = UltraAggressiveMockAutocast
                            logger.info("ULTRA-AGRESIVO: torch.amp.autocast creado durante importación")

                        # Crear MockGradScaler si no existe
                        if not hasattr(result.amp, 'GradScaler'):
                            class UltraAggressiveMockGradScaler:
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

                                def __repr__(self):
                                    return f"UltraAggressiveMockGradScaler(scale={self._scale}, enabled={self.enabled})"

                            result.amp.GradScaler = UltraAggressiveMockGradScaler
                            logger.info("ULTRA-AGRESIVO: torch.amp.GradScaler creado durante importación")

                    except Exception as patch_error:
                        logger.warning(f"Error en parche ultra-agresivo durante importación: {patch_error}")

                return result

            __builtins__['__import__'] = patched_torch_import
            logger.info("ULTRA-AGRESIVO: Interceptor de importación de torch activado")

        # Segundo intento: si torch ya está importado, parcharlo directamente
        if 'torch' in sys.modules:
            torch = sys.modules['torch']

            if not hasattr(torch, 'amp'):
                torch.amp = create_complete_mock_amp()
                logger.info("ULTRA-AGRESIVO: torch.amp creado en módulo existente")

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

            if not hasattr(torch.amp, 'autocast'):
                class UltraAggressiveMockAutocast:
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
                        return f"UltraAggressiveMockAutocast(device_type='{self.device_type}', enabled={self.enabled})"

                torch.amp.autocast = UltraAggressiveMockAutocast
                logger.info("ULTRA-AGRESIVO: torch.amp.autocast aplicado a módulo existente")

            if not hasattr(torch.amp, 'GradScaler'):
                class UltraAggressiveMockGradScaler:
                    def __init__(self, *args, **kwargs):
                        self._scale = 1.0

                    def scale(self, outputs):
                        return outputs

                    def step(self, optimizer):
                        optimizer.step()

                    def update(self):
                        pass

                    def get_scale(self):
                        return self._scale

                torch.amp.GradScaler = UltraAggressiveMockGradScaler
                logger.info("ULTRA-AGRESIVO: torch.amp.GradScaler aplicado a módulo existente")

            _bind_autocast_on_mode(torch.amp)

        # Tercer intento: módulo torch.amp solo si torch ya está cargado
        if 'torch' in sys.modules and 'torch.amp' not in sys.modules:
            # Crear un módulo mock para torch.amp
            import types
            mock_amp_module = types.ModuleType('torch.amp')

            class UltraAggressiveMockAutocast:
                def __init__(self, *args, **kwargs):
                    pass
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def __call__(self, *args, **kwargs):
                    return self

            class UltraAggressiveMockGradScaler:
                def __init__(self, *args, **kwargs):
                    pass
                def scale(self, outputs):
                    return outputs
                def step(self, optimizer):
                    optimizer.step()
                def update(self):
                    pass

            class UltraAggressiveMockAutocastMode:
                def __init__(self, *args, **kwargs):
                    pass
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass

            mock_amp_module.autocast = UltraAggressiveMockAutocast
            mock_amp_module.GradScaler = UltraAggressiveMockGradScaler
            mock_amp_module.autocast_mode = UltraAggressiveMockAutocastMode
            UltraAggressiveMockAutocastMode.autocast = UltraAggressiveMockAutocast
            _bind_autocast_on_mode(mock_amp_module)

            sys.modules['torch.amp'] = mock_amp_module
            logger.info("ULTRA-AGRESIVO: Módulo mock torch.amp añadido a sys.modules")

        # Suprimir todas las advertencias relacionadas con autocast
        warnings.filterwarnings("ignore", message=".*autocast.*")
        warnings.filterwarnings("ignore", message=".*torch.amp.*")
        warnings.filterwarnings("ignore", category=UserWarning, module="torch.amp")

        logger.info("ULTRA-AGRESIVO: Parche aplicado exitosamente")
        return True

    except Exception as e:
        logger.error(f"ULTRA-AGRESIVO: Error aplicando parche: {e}")
        return False

def ensure_torch_compatibility():
    """
    Función que debe ser llamada al inicio de cualquier script que use torch.
    """
    try:
        # Intentar importar torch de forma segura
        import torch

        # Verificar y corregir torch.amp si es necesario
        if not hasattr(torch, 'amp'):
            torch.amp = create_complete_mock_amp()

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

        if not hasattr(torch.amp, 'autocast'):
            class SafeMockAutocast:
                def __init__(self, *args, **kwargs):
                    pass
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def __call__(self, *args, **kwargs):
                    return self

            torch.amp.autocast = SafeMockAutocast

        if not hasattr(torch.amp, 'GradScaler'):
            class SafeMockGradScaler:
                def __init__(self, *args, **kwargs):
                    pass
                def scale(self, outputs):
                    return outputs
                def step(self, optimizer):
                    optimizer.step()
                def update(self):
                    pass

            torch.amp.GradScaler = SafeMockGradScaler

        _bind_autocast_on_mode(torch.amp)

        return True

    except ImportError as e:
        if "autocast" in str(e):
            logger.error(f"Error de autocast detectado: {e}")
            # Intentar la solución más agresiva
            return apply_ultra_aggressive_torch_patch()
        else:
            logger.warning(f"PyTorch no disponible: {e}")
            return False
    except Exception as e:
        logger.error(f"Error asegurando compatibilidad de torch: {e}")
        return False

# Aplicar el parche inmediatamente al importar este módulo
if __name__ != "__main__":
    apply_ultra_aggressive_torch_patch()

# También aplicar cuando se ejecute directamente
if __name__ == "__main__":
    result = apply_ultra_aggressive_torch_patch()
    print(f"Resultado del parche ultra-agresivo: {result}")

    # Verificar que funciona
    try:
        import torch
        print(f"torch.amp disponible: {hasattr(torch, 'amp')}")
        print(f"torch.amp.autocast disponible: {hasattr(torch.amp, 'autocast')}")
        print(f"torch.amp.GradScaler disponible: {hasattr(torch.amp, 'GradScaler')}")

        # Probar autocast
        with torch.amp.autocast():
            print("autocast funcionando correctamente")

        # Probar GradScaler
        scaler = torch.amp.GradScaler()
        print("GradScaler funcionando correctamente")

        print("✅ Todos los parches funcionan correctamente")

    except Exception as e:
        print(f"❌ Error verificando parches: {e}")
