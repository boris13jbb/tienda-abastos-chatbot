"""
API para el Escaneo de Códigos QR de la Tienda de Abastos.
Define los endpoints para escanear códigos QR y buscar productos.
"""

import logging
import json
import re
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

from app.database.db import get_direct_connection
from app.security.auth import verify_token
from app.utils.logger import get_logger
from app.rag.retriever import retriever

# Configurar logging específico para este módulo
logger = get_logger(__name__)

# Crear router para las rutas del escáner QR
router = APIRouter()

# Modelos de datos para la API
class QRScanRequest(BaseModel):
    """Modelo para las solicitudes de escaneo QR."""
    qr_code: str
    scan_type: str = "product"  # Valores posibles: "product", "barcode", "manual", "barcode_scanner"
    session_id: Optional[str] = None

class NewProductRequest(BaseModel):
    """Modelo para agregar nuevos productos desde código de barras."""
    codigo_barras: str
    nombre: str
    precio: float
    stock: int = 0
    categoria: str = "General"
    descripcion: Optional[str] = None
    proveedor: Optional[str] = None

class QRScanResponse(BaseModel):
    """Modelo para las respuestas del escáner QR."""
    success: bool
    product_info: Optional[Dict[str, Any]] = None
    message: str
    search_results: Optional[list] = None

class ProductInfo(BaseModel):
    """Modelo para información de producto."""
    codigo: str
    nombre: str
    precio: float
    stock: int
    categoria: str
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None

# Middleware para verificar autenticación (opcional para escaneo público)
async def verify_optional_token(authorization: Optional[str] = None):
    """
    Middleware que verifica el token de autenticación si está presente.
    Permite acceso público si no hay token.
    """
    if not authorization:
        return {"user_type": "public", "user_id": "public_user"}
    
    try:
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        return token_data
    except Exception as e:
        logger.warning(f"Token inválido en escaneo QR: {str(e)}")
        return {"user_type": "public", "user_id": "public_user"}

def parse_qr_code(qr_code: str) -> Dict[str, Any]:
    """
    Parsea el código QR y extrae información del producto.
    
    Args:
        qr_code: Código QR escaneado
        
    Returns:
        Diccionario con información parseada
    """
    try:
        # Intentar parsear como JSON si es un QR con datos estructurados
        if qr_code.startswith('{') and qr_code.endswith('}'):
            return json.loads(qr_code)
        
        # Si es un código de barras simple, extraer números
        numbers = re.findall(r'\d+', qr_code)
        if numbers:
            return {
                "codigo": numbers[0],
                "tipo": "barcode",
                "raw_code": qr_code
            }
        
        # Si contiene información de producto en texto
        if any(keyword in qr_code.lower() for keyword in ['producto', 'product', 'codigo', 'code']):
            return {
                "tipo": "text_product",
                "raw_code": qr_code,
                "searchable_text": qr_code
            }
        
        # Por defecto, tratar como código de producto
        return {
            "codigo": qr_code.strip(),
            "tipo": "product_code",
            "raw_code": qr_code
        }
        
    except Exception as e:
        logger.error(f"Error parseando código QR: {str(e)}")
        return {
            "tipo": "unknown",
            "raw_code": qr_code,
            "error": str(e)
        }

def validate_barcode(barcode: str) -> Dict[str, Any]:
    """
    Valida un código de barras y determina su tipo.
    """
    barcode = barcode.strip()
    
    # EAN-13 (13 dígitos)
    if len(barcode) == 13 and barcode.isdigit():
        return {"valid": True, "type": "EAN-13", "length": 13}
    
    # EAN-8 (8 dígitos)
    elif len(barcode) == 8 and barcode.isdigit():
        return {"valid": True, "type": "EAN-8", "length": 8}
    
    # UPC-A (12 dígitos)
    elif len(barcode) == 12 and barcode.isdigit():
        return {"valid": True, "type": "UPC-A", "length": 12}
    
    # Código de barras personalizado (6-20 caracteres alfanuméricos)
    elif 6 <= len(barcode) <= 20 and barcode.replace("-", "").replace("_", "").isalnum():
        return {"valid": True, "type": "Custom", "length": len(barcode)}
    
    else:
        return {"valid": False, "type": "Invalid", "length": len(barcode)}

async def add_new_product(product_data: NewProductRequest) -> Dict[str, Any]:
    """
    Agrega un nuevo producto a la base de datos desde código de barras.
    """
    try:
        conn = get_direct_connection()
        cursor = conn.cursor()
        
        # Verificar si el producto ya existe
        cursor.execute("SELECT ID FROM Productos WHERE ID = ?", (product_data.codigo_barras,))
        if cursor.fetchone():
            return {
                "success": False,
                "message": "El producto con este código de barras ya existe",
                "product_id": product_data.codigo_barras
            }
        
        # Insertar nuevo producto
        cursor.execute("""
            INSERT INTO Productos (ID, Nombre, Precio, Stock, Descripcion, Categoria, Proveedor, FechaCreacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, GETDATE())
        """, (
            product_data.codigo_barras,
            product_data.nombre,
            product_data.precio,
            product_data.stock,
            product_data.descripcion or "",
            product_data.categoria,
            product_data.proveedor or "",
        ))
        
        conn.commit()
        
        return {
            "success": True,
            "message": "Producto agregado exitosamente",
            "product_id": product_data.codigo_barras,
            "product_info": {
                "codigo": product_data.codigo_barras,
                "nombre": product_data.nombre,
                "precio": product_data.precio,
                "stock": product_data.stock,
                "categoria": product_data.categoria
            }
        }
        
    except Exception as e:
        logger.error(f"Error agregando producto: {str(e)}")
        return {
            "success": False,
            "message": f"Error al agregar producto: {str(e)}"
        }
    finally:
        if 'conn' in locals() and conn:
            conn.close()

async def search_product_by_code(codigo: str) -> Optional[Dict[str, Any]]:
    """
    Busca un producto en la base de datos por código.
    
    Args:
        codigo: Código del producto
        
    Returns:
        Información del producto o None si no se encuentra
    """
    try:
        conn = get_direct_connection()
        cursor = conn.cursor()
        
        # Buscar por ID o nombre del producto
        query = """
        SELECT TOP 1 
            ID, Nombre, Precio, Stock, Descripcion
        FROM Productos 
        WHERE ID = ? OR Nombre LIKE ? OR Descripcion LIKE ?
        ORDER BY 
            CASE WHEN ID = ? THEN 1 ELSE 2 END
        """
        
        cursor.execute(query, (codigo, f"%{codigo}%", f"%{codigo}%", codigo))
        result = cursor.fetchone()
        
        if result:
            return {
                "codigo": str(result[0]),  # Usar ID como código
                "nombre": result[1],
                "precio": float(result[2]) if result[2] else 0.0,
                "stock": int(result[3]) if result[3] else 0,
                "categoria": "General",  # Categoría por defecto
                "descripcion": result[4] or ""
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error buscando producto por código {codigo}: {str(e)}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

async def search_products_by_text(search_text: str, limit: int = 5) -> list:
    """
    Busca productos por texto usando el sistema RAG.
    
    Args:
        search_text: Texto a buscar
        limit: Límite de resultados
        
    Returns:
        Lista de productos encontrados
    """
    try:
        # Usar el sistema RAG para buscar productos
        query = f"Buscar productos relacionados con: {search_text}"
        response = retriever(query, "corto", "qr_scanner")
        
        # Extraer información de productos de la respuesta
        products = []
        
        # Buscar nombres de productos en la respuesta
        nombres = re.findall(r'producto[s]?\s*:?\s*([A-Za-z\s]+)', response, re.IGNORECASE)
        
        for nombre in nombres[:limit]:
            nombre_limpio = nombre.strip()
            if len(nombre_limpio) > 2:  # Filtrar nombres muy cortos
                product_info = await search_product_by_code(nombre_limpio)
                if product_info:
                    products.append(product_info)
        
        return products
        
    except Exception as e:
        logger.error(f"Error buscando productos por texto: {str(e)}")
        return []

@router.post("/scan", response_model=QRScanResponse, summary="Escanear código QR y buscar producto")
async def scan_qr_code(
    request: QRScanRequest,
    token_data: dict = Depends(verify_optional_token)
):
    """
    Endpoint para escanear códigos QR y buscar información de productos.
    
    Args:
        request: Datos del código QR escaneado
        token_data: Datos del token de autenticación (opcional)
        
    Returns:
        Información del producto encontrado
    """
    try:
        logger.info(f"Escaneo QR iniciado: {request.qr_code[:50]}...")
        
        # Parsear el código QR
        parsed_data = parse_qr_code(request.qr_code)
        
        if parsed_data.get("error"):
            return QRScanResponse(
                success=False,
                message=f"Error parseando código QR: {parsed_data['error']}"
            )
        
        # Buscar producto según el tipo de código
        product_info = None
        search_results = []
        
        if parsed_data.get("codigo"):
            # Buscar por código de producto
            product_info = await search_product_by_code(parsed_data["codigo"])
            
        elif parsed_data.get("searchable_text"):
            # Buscar por texto
            search_results = await search_products_by_text(parsed_data["searchable_text"])
            if search_results:
                product_info = search_results[0]
        
        # Si no se encontró producto directo, hacer búsqueda general
        if not product_info and not search_results:
            search_results = await search_products_by_text(request.qr_code)
            if search_results:
                product_info = search_results[0]
        
        if product_info:
            logger.info(f"Producto encontrado: {product_info['nombre']} (Código: {product_info['codigo']})")
            
            return QRScanResponse(
                success=True,
                product_info=product_info,
                message=f"Producto encontrado: {product_info['nombre']}",
                search_results=search_results[:3] if search_results else None
            )
        else:
            logger.warning(f"No se encontró producto para código QR: {request.qr_code}")
            
            return QRScanResponse(
                success=False,
                message="No se encontró información del producto. Intenta con otro código o busca manualmente.",
                search_results=search_results[:3] if search_results else None
            )
            
    except Exception as e:
        logger.error(f"Error en escaneo QR: {str(e)}")
        return QRScanResponse(
            success=False,
            message=f"Error procesando código QR: {str(e)}"
        )

@router.post("/search-manual", response_model=QRScanResponse, summary="Búsqueda manual de producto")
async def search_manual(
    request: QRScanRequest,
    token_data: dict = Depends(verify_optional_token)
):
    """
    Endpoint para búsqueda manual de productos por texto.
    
    Args:
        request: Datos de búsqueda
        token_data: Datos del token de autenticación (opcional)
        
    Returns:
        Resultados de búsqueda
    """
    try:
        logger.info(f"Búsqueda manual iniciada: {request.qr_code}")
        
        # Buscar productos por texto
        search_results = await search_products_by_text(request.qr_code, limit=10)
        
        if search_results:
            return QRScanResponse(
                success=True,
                message=f"Se encontraron {len(search_results)} productos",
                search_results=search_results
            )
        else:
            return QRScanResponse(
                success=False,
                message="No se encontraron productos con ese criterio de búsqueda"
            )
            
    except Exception as e:
        logger.error(f"Error en búsqueda manual: {str(e)}")
        return QRScanResponse(
            success=False,
            message=f"Error en búsqueda: {str(e)}"
        )

@router.get("/product/{codigo}", response_model=ProductInfo, summary="Obtener información de producto por código")
async def get_product_by_code(
    codigo: str,
    token_data: dict = Depends(verify_optional_token)
):
    """
    Endpoint para obtener información detallada de un producto por código.
    
    Args:
        codigo: Código del producto
        token_data: Datos del token de autenticación (opcional)
        
    Returns:
        Información detallada del producto
    """
    try:
        product_info = await search_product_by_code(codigo)
        
        if product_info:
            return ProductInfo(**product_info)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con código {codigo} no encontrado"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo producto {codigo}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )

@router.get("/test-qr", summary="Probar funcionalidad de escaneo QR")
async def test_qr_functionality():
    """
    Endpoint para probar la funcionalidad de escaneo QR con códigos de prueba.
    
    Returns:
        Resultados de prueba
    """
    test_codes = [
        "123456789",  # Código de barras simple
        '{"codigo": "TEST001", "nombre": "Producto de Prueba"}',  # QR con JSON
        "Producto: Arroz",  # Texto con información de producto
        "ABC123"  # Código de producto
    ]
    
    results = []
    
    for test_code in test_codes:
        try:
            parsed_data = parse_qr_code(test_code)
            product_info = None
            
            if parsed_data.get("codigo"):
                product_info = await search_product_by_code(parsed_data["codigo"])
            
            results.append({
                "test_code": test_code,
                "parsed_data": parsed_data,
                "product_found": product_info is not None,
                "product_info": product_info
            })
            
        except Exception as e:
            results.append({
                "test_code": test_code,
                "error": str(e)
            })
    
    return {
        "test_results": results,
        "status": "QR Scanner functionality test completed"
    }

@router.post("/barcode-scanner", response_model=QRScanResponse, summary="Escaneo con pistola láser de códigos de barras")
async def barcode_scanner_scan(
    request: QRScanRequest,
    token_data: dict = Depends(verify_optional_token)
):
    """
    Endpoint específico para escaneo con pistola láser de códigos de barras.
    Optimizado para códigos de barras estándar (EAN-13, EAN-8, UPC-A).
    """
    try:
        logger.info(f"Escaneo con pistola láser iniciado: {request.qr_code}")
        
        # Validar el código de barras
        barcode_validation = validate_barcode(request.qr_code)
        
        if not barcode_validation["valid"]:
            return QRScanResponse(
                success=False,
                message=f"Código de barras inválido: {barcode_validation['type']} (longitud: {barcode_validation['length']})"
            )
        
        # Buscar el producto en la base de datos
        product_info = await search_product_by_code(request.qr_code)
        
        if product_info:
            return QRScanResponse(
                success=True,
                product_info=product_info,
                message=f"Producto encontrado - {barcode_validation['type']}"
            )
        else:
            # Si no se encuentra, ofrecer agregar como nuevo producto
            return QRScanResponse(
                success=False,
                message=f"Producto no encontrado. Código de barras válido: {barcode_validation['type']}. ¿Desea agregarlo como nuevo producto?",
                product_info={
                    "codigo": request.qr_code,
                    "barcode_type": barcode_validation["type"],
                    "can_add_new": True
                }
            )
            
    except Exception as e:
        logger.error(f"Error en escaneo con pistola láser: {str(e)}")
        return QRScanResponse(
            success=False,
            message=f"Error procesando código de barras: {str(e)}"
        )

@router.post("/add-product", summary="Agregar nuevo producto desde código de barras")
async def add_product_from_barcode(
    request: NewProductRequest,
    token_data: dict = Depends(verify_optional_token)
):
    """
    Endpoint para agregar un nuevo producto a partir de un código de barras escaneado.
    """
    try:
        logger.info(f"Agregando nuevo producto: {request.codigo_barras}")
        
        # Validar el código de barras
        barcode_validation = validate_barcode(request.codigo_barras)
        
        if not barcode_validation["valid"]:
            return {
                "success": False,
                "message": f"Código de barras inválido: {barcode_validation['type']}"
            }
        
        # Agregar el producto
        result = await add_new_product(request)
        
        return result
        
    except Exception as e:
        logger.error(f"Error agregando producto: {str(e)}")
        return {
            "success": False,
            "message": f"Error al agregar producto: {str(e)}"
        }

@router.get("/validate-barcode/{barcode}", summary="Validar código de barras")
async def validate_barcode_endpoint(
    barcode: str,
    token_data: dict = Depends(verify_optional_token)
):
    """
    Endpoint para validar un código de barras sin buscar en la base de datos.
    """
    try:
        validation_result = validate_barcode(barcode)
        
        return {
            "barcode": barcode,
            "validation": validation_result,
            "is_valid": validation_result["valid"]
        }
        
    except Exception as e:
        logger.error(f"Error validando código de barras: {str(e)}")
        return {
            "barcode": barcode,
            "validation": {"valid": False, "type": "Error", "error": str(e)},
            "is_valid": False
        }

@router.get("/sync/products", summary="Sincronizar productos con APK")
async def sync_products_with_apk(
    last_sync: Optional[str] = None,
    token_data: dict = Depends(verify_optional_token)
):
    """
    Endpoint para sincronizar productos con la APK Android.
    Retorna todos los productos o solo los modificados desde la última sincronización.
    """
    try:
        conn = get_direct_connection()
        cursor = conn.cursor()
        
        # Construir query basada en fecha de última sincronización
        if last_sync:
            query = """
                SELECT ID, Nombre, Precio, Stock, Descripcion, Categoria, Proveedor, 
                       FechaCreacion, FechaActualizacion
                FROM Productos 
                WHERE FechaActualizacion > ? OR FechaCreacion > ?
                ORDER BY FechaActualizacion DESC
            """
            cursor.execute(query, (last_sync, last_sync))
        else:
            query = """
                SELECT ID, Nombre, Precio, Stock, Descripcion, Categoria, Proveedor, 
                       FechaCreacion, FechaActualizacion
                FROM Productos 
                ORDER BY FechaActualizacion DESC
            """
            cursor.execute(query)
        
        products = []
        for row in cursor.fetchall():
            products.append({
                "codigo": row[0],
                "nombre": row[1],
                "precio": float(row[2]),
                "stock": row[3],
                "descripcion": row[4] or "",
                "categoria": row[5] or "",
                "proveedor": row[6] or "",
                "fecha_creacion": row[7].isoformat() if row[7] else None,
                "fecha_actualizacion": row[8].isoformat() if row[8] else None
            })
        
        return {
            "success": True,
            "products": products,
            "total_products": len(products),
            "sync_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error sincronizando productos: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "products": [],
            "total_products": 0
        }
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@router.post("/sync/upload-products", summary="Subir productos desde APK")
async def upload_products_from_apk(
    products: List[Dict[str, Any]],
    token_data: dict = Depends(verify_optional_token)
):
    """
    Endpoint para recibir productos desde la APK Android y sincronizarlos.
    """
    try:
        conn = get_direct_connection()
        cursor = conn.cursor()
        
        uploaded_count = 0
        updated_count = 0
        errors = []
        
        for product in products:
            try:
                # Verificar si el producto ya existe
                cursor.execute("SELECT ID FROM Productos WHERE ID = ?", (product.get("codigo"),))
                existing = cursor.fetchone()
                
                if existing:
                    # Actualizar producto existente
                    cursor.execute("""
                        UPDATE Productos 
                        SET Nombre = ?, Precio = ?, Stock = ?, Descripcion = ?, 
                            Categoria = ?, Proveedor = ?, FechaActualizacion = GETDATE()
                        WHERE ID = ?
                    """, (
                        product.get("nombre"),
                        product.get("precio"),
                        product.get("stock"),
                        product.get("descripcion", ""),
                        product.get("categoria", ""),
                        product.get("proveedor", ""),
                        product.get("codigo")
                    ))
                    updated_count += 1
                else:
                    # Insertar nuevo producto
                    cursor.execute("""
                        INSERT INTO Productos (ID, Nombre, Precio, Stock, Descripcion, 
                                             Categoria, Proveedor, FechaCreacion, FechaActualizacion)
                        VALUES (?, ?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
                    """, (
                        product.get("codigo"),
                        product.get("nombre"),
                        product.get("precio"),
                        product.get("stock"),
                        product.get("descripcion", ""),
                        product.get("categoria", ""),
                        product.get("proveedor", "")
                    ))
                    uploaded_count += 1
                    
            except Exception as e:
                errors.append(f"Error con producto {product.get('codigo', 'unknown')}: {str(e)}")
        
        conn.commit()
        
        return {
            "success": True,
            "uploaded_count": uploaded_count,
            "updated_count": updated_count,
            "total_processed": len(products),
            "errors": errors,
            "sync_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error subiendo productos desde APK: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "uploaded_count": 0,
            "updated_count": 0,
            "total_processed": 0
        }
    finally:
        if 'conn' in locals() and conn:
            conn.close()
