import logging
import time
import re
from datetime import datetime
from functools import wraps
from typing import List, Dict, Any, Optional

from app.llm.sql_generator import generate_sql_query
from app.rag.text_processor import text_processor
from app.database.db import execute_query
from app.utils.formatters import format_product_list, format_price, format_availability_summary
from app.llm.language_model import get_language_model
from app.config.settings import settings
from app.rag.conversation_manager import conversation_manager
from app.rag.query_classifier import query_classifier
from app.learning.integrator import learning_integrator

logger = logging.getLogger(__name__)

# Decorador para medir el tiempo de ejecución
def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_time = time.time() - start_time
        logger.debug(f"Operación '{func.__name__}' completada en {elapsed_time:.4f} segundos")
        return result
    return wrapper

class ResponseGenerator:
    @staticmethod
    def format_total_stock_response(total: Optional[int], product_name: str) -> str:
        if total and total > 0:
            return f"Actualmente tenemos {total:,} unidades de {product_name} en nuestro inventario."
        else:
            return f"Lamentablemente, no tenemos {product_name} disponibles en este momento."

    @staticmethod
    def format_availability_response(exists: bool, product_name: str, result: List[Dict] = None) -> str:
        if exists:
            if result and len(result) > 0:
                # Proporcionar información más específica
                sample_product = result[0]
                precio = sample_product.get('Precio', 0)
                stock = sample_product.get('Stock', 0)
                return f"¡Sí! Tenemos {product_name} disponibles. Por ejemplo, tenemos {product_name} a ${precio:.2f} con {stock} unidades en stock."
            else:
                return f"¡Sí! Tenemos {product_name} disponibles en nuestro inventario."
        else:
            return f"Lamentablemente, no tenemos {product_name} disponibles en este momento. Te recomiendo revisar otros productos similares o contactar a nuestro personal para verificar disponibilidad."

    @staticmethod
    def format_low_stock_response(result: List[Dict[str, Any]]) -> str:
        if not result:
            return "¡Excelente! Todos nuestros productos tienen stock suficiente en este momento."
        response = "Los siguientes productos están por acabarse y te recomendamos comprarlos pronto:\n"
        for product in result[:5]:  # Mostrar máximo 5 productos
            nombre = product.get('Nombre', 'Producto')
            stock = product.get('Stock', 0)
            precio = product.get('Precio', 0)
            response += f"• {nombre}: solo {stock} unidades disponibles a ${precio:.2f}\n"
        return response

    @staticmethod
    def format_product_price_response(result: List[Dict[str, Any]], label: str) -> str:
        if not result:
            return f"No pude encontrar información específica sobre el precio de {label}. ¿Podrías ser más específico sobre qué producto buscas?"
        producto = result[0]
        precio = format_price(producto.get('Precio', 0))
        nombre = producto.get('Nombre', 'Producto')
        stock = producto.get('Stock', 0)
        return f"El {label} que encontré es {nombre} con un precio de {precio} y {stock} unidades disponibles."

class Retriever:
    def __init__(self):
        self.response_generator = ResponseGenerator()
        self.llm = get_language_model()
        self.conversation_context = {}

    def extract_brand(self, nombre_producto: str) -> str:
        # Busca patrones como "Marca X" o "marca X" en el nombre
        match = re.search(r"marca\s+([A-Za-z0-9]+)", nombre_producto, re.IGNORECASE)
        if match:
            return match.group(1)
        return "Sin marca"

    def _detect_special_query(self, question: str) -> Optional[str]:
        question_lower = question.lower()
        
        # Detectar consultas de productos más caros (con variaciones de ortografía)
        if any(phrase in question_lower for phrase in [
            "más caro", "mayor precio", "mas caro", "mas cara", "más cara",
            "más costoso", "mas costoso", "más costosa", "mas costosa",
            "más alto", "mas alto", "más cara", "mas cara"
        ]):
            # Verificar si se menciona un producto específico
            product_name = self.extract_product_name(question)
            if product_name and product_name.lower() != "producto":
                return f"SELECT TOP 1 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%{product_name}%' ORDER BY Precio DESC"
            return "SELECT TOP 1 Nombre, Precio, Stock FROM Productos ORDER BY Precio DESC"
        
        # Detectar consultas de productos más baratos (con variaciones de ortografía)
        if any(phrase in question_lower for phrase in [
            "más barato", "menor precio", "mas barato", "mas barata", "más barata",
            "más económico", "mas economico", "más económica", "mas economica",
            "más bajo", "mas bajo", "más barata", "mas barata", "varato", "varata"
        ]):
            # Verificar si se menciona un producto específico
            product_name = self.extract_product_name(question)
            if product_name and product_name.lower() != "producto":
                return f"SELECT TOP 1 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%{product_name}%' AND Stock > 0 ORDER BY Precio ASC"
            return "SELECT TOP 1 Nombre, Precio, Stock FROM Productos WHERE Stock > 0 ORDER BY Precio ASC"
        
        return None

    def _detect_low_stock_query(self, question: str) -> bool:
        return any(word in question.lower() for word in ["acabarse", "pocos", "bajo stock", "por acabarse"])

    def _detect_total_stock_query(self, question: str) -> bool:
        question_lower = question.lower()
        
        # Si es una consulta de precio, NO es una consulta de stock total
        if self._detect_price_query(question):
            return False
        
        # Palabras clave específicas para consultas de stock total
        stock_keywords = [
            "cuántos hay", "cuantos hay", "cuántas hay", "cuantas hay",
            "total de", "cantidad de", "cuánto stock", "cuanto stock",
            "cuántas unidades", "cuantas unidades", "cuántos productos", "cuantos productos",
            "stock total", "inventario total", "disponibilidad total", "cuántos", "cuantos"
        ]
        
        # Verificar si contiene palabras clave específicas de stock total
        if any(keyword in question_lower for keyword in stock_keywords):
            # Verificar que NO sea una consulta de precio
            price_indicators = ["cuesta", "vale", "precio", "costo", "valor"]
            if not any(indicator in question_lower for indicator in price_indicators):
                return True
        
        # Patrones específicos para consultas de stock total
        stock_patterns = [
            r"cu[aá]ntos?\s+hay",
            r"cu[aá]ntas?\s+hay", 
            r"total\s+de\s+\w+",
            r"cantidad\s+de\s+\w+",
            r"cu[aá]nto\s+stock",
            r"cu[aá]ntas?\s+unidades"
        ]
        
        for pattern in stock_patterns:
            if re.search(pattern, question_lower):
                # Verificar que NO sea una consulta de precio
                price_indicators = ["cuesta", "vale", "precio", "costo", "valor"]
                if not any(indicator in question_lower for indicator in price_indicators):
                    return True
        
        return False

    def _detect_availability_query(self, question: str) -> bool:
        return any(word in question.lower() for word in ["hay", "disponible", "tienen"])
        
    def _detect_price_query(self, question: str) -> bool:
        question_lower = question.lower()
        
        # Palabras clave específicas para consultas de precio
        price_keywords = [
            "precio", "cuesta", "vale", "costo", "cuánto", "cuanto", "cuánta", "cuanta",
            "valor", "dinero", "pagar", "cobrar", "tarifa", "precio de", "cuesta el",
            "vale el", "costo de", "cuánto vale", "cuanto vale", "cuánto cuesta", "cuanto cuesta"
        ]
        
        # Verificar si contiene palabras clave de precio
        if any(keyword in question_lower for keyword in price_keywords):
            # Verificar que NO sea una consulta de cantidad (cuántos hay, cuántas hay)
            if "hay" in question_lower and ("cuántos" in question_lower or "cuantos" in question_lower or "cuántas" in question_lower or "cuantas" in question_lower):
                return False
            return True
        
        # Patrones específicos para consultas de precio
        price_patterns = [
            r"cu[aá]nto\s+cuesta",
            r"cu[aá]nto\s+vale", 
            r"cu[aá]l\s+es\s+el\s+precio",
            r"precio\s+de",
            r"costo\s+de",
            r"valor\s+de"
        ]
        
        for pattern in price_patterns:
            if re.search(pattern, question_lower):
                return True
        
        return False

    def _handle_price_range_query(self, min_price: float, max_price: float) -> str:
        """Maneja consultas de rango de precios."""
        # Usar TOP para SQL Server en lugar de LIMIT
        query = f"SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Precio BETWEEN {min_price} AND {max_price} AND Stock > 0 ORDER BY Precio ASC"
        result = execute_query(query)
        
        if result:
            response = f"Encontré {len(result)} productos con precios entre ${min_price} y ${max_price}:\n"
            for prod in result[:10]:  # Mostrar máximo 10 productos
                nombre = prod.get('Nombre', '')
                precio = format_price(prod.get('Precio', 0))
                stock = prod.get('Stock', 0)
                response += f"• {nombre}: {precio} ({stock} unidades disponibles)\n"
            return response
        else:
            return f"No encontré productos en el rango de precios entre ${min_price} y ${max_price}."

    def _detect_price_range_query(self, question: str) -> Optional[tuple]:
        """Detecta consultas de rango de precios."""
        question_lower = question.lower()
        
        # Patrones para detectar rangos de precios
        patterns = [
            r"entre\s+\$?(\d+(?:\.\d+)?)\s+y\s+\$?(\d+(?:\.\d+)?)",
            r"de\s+\$?(\d+(?:\.\d+)?)\s+a\s+\$?(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*dólares?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question_lower)
            if match:
                min_price = float(match.group(1))
                max_price = float(match.group(2))
                return (min_price, max_price)
        
        return None

    def _detect_brand_query(self, question: str) -> bool:
        return "marca" in question.lower() or "marcas" in question.lower()

    def _detect_info_query(self, question: str) -> Optional[str]:
        """Detecta consultas de información general"""
        question_lower = question.lower()
        
        # Detectar consultas de productos por acabarse
        if any(phrase in question_lower for phrase in [
            "productos están por acabarse", "productos por acabarse", "productos se están acabando",
            "productos con poco stock", "productos con bajo stock", "productos agotándose"
        ]):
            return "low_stock"
        
        # Detectar consultas de productos agotados
        if any(phrase in question_lower for phrase in [
            "productos agotados", "productos sin stock", "productos no disponibles"
        ]):
            return "out_of_stock"
        
        # Detectar consultas de productos más vendidos
        if any(phrase in question_lower for phrase in [
            "productos más vendidos", "productos populares", "productos más comprados"
        ]):
            return "best_sellers"
        
        # Detectar consultas de productos en oferta
        if any(phrase in question_lower for phrase in [
            "productos en oferta", "productos con descuento", "ofertas", "promociones"
        ]):
            return "on_sale"
        
        return None

    def _get_info_response(self, info_type: str) -> str:
        """Genera respuestas para consultas de información general"""
        if info_type == "low_stock":
            query = "SELECT TOP 10 Nombre, Stock FROM Productos WHERE Stock <= 10 AND Stock > 0 ORDER BY Stock ASC"
            result = execute_query(query)
            if result:
                response = "Los productos que están por acabarse son:\n"
                for prod in result:
                    nombre = prod.get('Nombre', '')
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {stock} unidades restantes\n"
                return response
            else:
                return "Actualmente no tenemos productos con stock bajo."
        
        elif info_type == "out_of_stock":
            query = "SELECT TOP 10 Nombre FROM Productos WHERE Stock = 0"
            result = execute_query(query)
            if result:
                response = "Los productos agotados son:\n"
                for prod in result:
                    nombre = prod.get('Nombre', '')
                    response += f"• {nombre}\n"
                return response
            else:
                return "Actualmente no tenemos productos agotados."
        
        elif info_type == "best_sellers":
            query = "SELECT TOP 10 Nombre, Stock FROM Productos WHERE Stock > 0 ORDER BY Stock DESC"
            result = execute_query(query)
            if result:
                response = "Los productos más populares son:\n"
                for prod in result:
                    nombre = prod.get('Nombre', '')
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {stock} unidades disponibles\n"
                return response
            else:
                return "No tenemos información de productos populares en este momento."
        
        elif info_type == "on_sale":
            query = "SELECT TOP 10 Nombre, Precio FROM Productos WHERE Stock > 0 ORDER BY Precio ASC"
            result = execute_query(query)
            if result:
                response = "Los productos con mejores precios son:\n"
                for prod in result:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    response += f"• {nombre}: {precio}\n"
                return response
            else:
                return "No tenemos ofertas especiales en este momento."
        
        return "No pude encontrar la información solicitada."

    def set_last_product(self, user_id: str, product_name: str):
        self.conversation_context[user_id] = product_name

    def get_last_product(self, user_id: str) -> str:
        return self.conversation_context.get(user_id, "")

    def _handle_specific_product_not_found(self, product_name: str) -> str:
        """Maneja casos donde no se encuentra un producto específico."""
        # Limpiar el nombre del producto de preposiciones
        clean_product_name = re.sub(r'^(del|de|la|las|el|los|un|una|unos|unas)\s+', '', product_name.strip())
        
        # Intentar búsquedas con variaciones
        search_variations = [
            clean_product_name,
            clean_product_name.rstrip('s'),  # Quitar 's' final (plural a singular)
            clean_product_name + 's',        # Agregar 's' final (singular a plural)
            clean_product_name.rstrip('es') + 'a',  # Cambiar 'es' por 'a' (ej: cuadernes -> cuaderna)
            clean_product_name.rstrip('a') + 'o',   # Cambiar 'a' por 'o' (ej: cuaderna -> cuaderno)
        ]
        
        # Eliminar duplicados y variaciones vacías
        search_variations = list(set([v for v in search_variations if v and len(v) > 2]))
        
        for variation in search_variations:
            similar_query = f"SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%{variation}%' AND Stock > 0"
            similar_result = execute_query(similar_query)
            
            if similar_result:
                response = f"Encontré productos similares a '{product_name}':\n"
                for prod in similar_result:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += f"\n¿Te interesa alguno de estos productos o buscas algo más específico?"
                return response
        
        # Si no se encuentra con variaciones, intentar búsqueda más amplia
        broad_query = f"SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%{clean_product_name[:4]}%' AND Stock > 0"
        broad_result = execute_query(broad_query)
        
        if broad_result:
            response = f"No encontré exactamente '{product_name}', pero tenemos productos similares:\n"
            for prod in broad_result:
                nombre = prod.get('Nombre', '')
                precio = format_price(prod.get('Precio', 0))
                stock = prod.get('Stock', 0)
                response += f"• {nombre}: {precio} ({stock} unidades)\n"
            response += f"\n¿Te interesa alguno de estos productos o buscas algo más específico?"
        else:
            response = f"Lamentablemente, no tenemos '{product_name}' en nuestro inventario actual. "
            response += "Te recomiendo revisar otros productos similares o contactar a nuestro personal para verificar disponibilidad."
        
        return response

    def _improve_generic_response(self, question: str, product_name: str = None, context: Dict = None) -> str:
        """Mejora las respuestas genéricas con mejor contexto"""
        question_lower = question.lower()
        
        # 🚀 NUEVA LÓGICA: Detectar consultas sobre listado de productos por categoría
        if any(phrase in question_lower for phrase in [
            "listado de productos por categoría", "listado de productos por categoria",
            "productos por categoría", "productos por categoria", "categorías", "categorias",
            "listar categorías", "listar categorias", "mostrar categorías", "mostrar categorias"
        ]):
            # Obtener todas las categorías disponibles
            query_categorias = """
            SELECT DISTINCT 
                CASE 
                    WHEN Nombre LIKE '%limpieza%' OR Nombre LIKE '%detergente%' OR Nombre LIKE '%jabon%' THEN 'Limpieza'
                    WHEN Nombre LIKE '%bebida%' OR Nombre LIKE '%jugo%' OR Nombre LIKE '%agua%' THEN 'Bebidas'
                    WHEN Nombre LIKE '%fruta%' OR Nombre LIKE '%verdura%' OR Nombre LIKE '%vegetal%' THEN 'Frutas y Verduras'
                    WHEN Nombre LIKE '%lácteo%' OR Nombre LIKE '%lacteo%' OR Nombre LIKE '%leche%' OR Nombre LIKE '%queso%' THEN 'Lácteos'
                    WHEN Nombre LIKE '%pan%' OR Nombre LIKE '%galleta%' OR Nombre LIKE '%dulce%' THEN 'Panadería y Dulces'
                    WHEN Nombre LIKE '%arroz%' OR Nombre LIKE '%pasta%' OR Nombre LIKE '%frijol%' THEN 'Abarrotes'
                    WHEN Nombre LIKE '%monitor%' OR Nombre LIKE '%teclado%' OR Nombre LIKE '%mouse%' THEN 'Tecnología'
                    WHEN Nombre LIKE '%esfero%' OR Nombre LIKE '%cuaderno%' OR Nombre LIKE '%papel%' THEN 'Papelería'
                    WHEN Nombre LIKE '%mascota%' OR Nombre LIKE '%perro%' OR Nombre LIKE '%gato%' THEN 'Mascotas'
                    WHEN Nombre LIKE '%bebé%' OR Nombre LIKE '%bebe%' OR Nombre LIKE '%pañal%' THEN 'Bebés'
                    ELSE 'Otros'
                END as Categoria,
                COUNT(*) as Cantidad_Productos
            FROM Productos 
            WHERE Stock > 0 
            GROUP BY 
                CASE 
                    WHEN Nombre LIKE '%limpieza%' OR Nombre LIKE '%detergente%' OR Nombre LIKE '%jabon%' THEN 'Limpieza'
                    WHEN Nombre LIKE '%bebida%' OR Nombre LIKE '%jugo%' OR Nombre LIKE '%agua%' THEN 'Bebidas'
                    WHEN Nombre LIKE '%fruta%' OR Nombre LIKE '%verdura%' OR Nombre LIKE '%vegetal%' THEN 'Frutas y Verduras'
                    WHEN Nombre LIKE '%lácteo%' OR Nombre LIKE '%lacteo%' OR Nombre LIKE '%leche%' OR Nombre LIKE '%queso%' THEN 'Lácteos'
                    WHEN Nombre LIKE '%pan%' OR Nombre LIKE '%galleta%' OR Nombre LIKE '%dulce%' THEN 'Panadería y Dulces'
                    WHEN Nombre LIKE '%arroz%' OR Nombre LIKE '%pasta%' OR Nombre LIKE '%frijol%' THEN 'Abarrotes'
                    WHEN Nombre LIKE '%monitor%' OR Nombre LIKE '%teclado%' OR Nombre LIKE '%mouse%' THEN 'Tecnología'
                    WHEN Nombre LIKE '%esfero%' OR Nombre LIKE '%cuaderno%' OR Nombre LIKE '%papel%' THEN 'Papelería'
                    WHEN Nombre LIKE '%mascota%' OR Nombre LIKE '%perro%' OR Nombre LIKE '%gato%' THEN 'Mascotas'
                    WHEN Nombre LIKE '%bebé%' OR Nombre LIKE '%bebe%' OR Nombre LIKE '%pañal%' THEN 'Bebés'
                    ELSE 'Otros'
                END
            ORDER BY Cantidad_Productos DESC
            """
            
            result_categorias = execute_query(query_categorias)
            
            if result_categorias:
                response = "📋 **LISTADO DE PRODUCTOS POR CATEGORÍA**\n\n"
                response += "Aquí tienes las categorías disponibles con la cantidad de productos en cada una:\n\n"
                
                for categoria in result_categorias:
                    nombre_categoria = categoria.get('Categoria', 'Sin categoría')
                    cantidad = categoria.get('Cantidad_Productos', 0)
                    response += f"• **{nombre_categoria}**: {cantidad} productos\n"
                
                response += "\n¿Te gustaría ver los productos de alguna categoría específica? Solo dime cuál te interesa."
                return response
            else:
                return "No pude obtener el listado de categorías en este momento. ¿Te interesa algún producto específico?"
        
        # Si hay contexto y es una pregunta de seguimiento
        if context and context.get("last_product"):
            last_product = context["last_product"]
            
            # Mejorar preguntas específicas con contexto
            if "precio" in question_lower:
                return f"Para ayudarte con el precio de {last_product}, necesito hacer una consulta específica. Déjame buscar esa información para ti."
            
            elif "stock" in question_lower or "unidades" in question_lower:
                return f"Te ayudo a verificar el stock de {last_product}. Déjame consultar cuántas unidades tenemos disponibles."
            
            elif "marca" in question_lower:
                return f"Respecto a las marcas de {last_product}, déjame buscar qué opciones tenemos disponibles."
            
            elif "disponible" in question_lower:
                return f"Para verificar la disponibilidad de {last_product}, déjame consultar nuestro inventario."
        
        # 🚀 NUEVA LÓGICA: Detectar consultas específicas sobre productos
        # Detectar consultas sobre productos de limpieza
        if any(word in question_lower for word in ["limpieza", "limpiador", "detergente", "jabón", "jabon", "desinfectante"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%detergente%' OR Nombre LIKE '%jabon%' OR Nombre LIKE '%limpiador%' OR Nombre LIKE '%desinfectante%' OR Nombre LIKE '%cloro%' OR Nombre LIKE '%suavizante%') AND Stock > 0"
            result = execute_query(query)
            if result:
                response = "🧽 **PRODUCTOS DE LIMPIEZA**\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
        
        # Detectar consultas sobre productos de bebidas
        if any(word in question_lower for word in ["bebida", "bebidas", "jugo", "jugos", "refresco", "refrescos", "agua"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%bebida%' OR Nombre LIKE '%jugo%' OR Nombre LIKE '%refresco%' OR Nombre LIKE '%agua%' OR Nombre LIKE '%gaseosa%' OR Nombre LIKE '%soda%') AND Stock > 0"
            result = execute_query(query)
            if result:
                response = "🥤 **BEBIDAS**\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
        
        # Detectar consultas sobre productos de frutas y verduras
        if any(word in question_lower for word in ["fruta", "frutas", "verdura", "verduras", "vegetal", "vegetales"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%fruta%' OR Nombre LIKE '%verdura%' OR Nombre LIKE '%vegetal%' OR Nombre LIKE '%manzana%' OR Nombre LIKE '%plátano%' OR Nombre LIKE '%naranja%' OR Nombre LIKE '%tomate%' OR Nombre LIKE '%cebolla%') AND Stock > 0"
            result = execute_query(query)
            if result:
                response = "🥬 **FRUTAS Y VERDURAS**\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
        
        # Detectar consultas sobre productos lácteos
        if any(word in question_lower for word in ["lácteo", "lacteo", "lácteos", "lacteos", "leche", "queso", "yogurt", "yogur"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%leche%' OR Nombre LIKE '%queso%' OR Nombre LIKE '%yogurt%' OR Nombre LIKE '%yogur%' OR Nombre LIKE '%mantequilla%' OR Nombre LIKE '%crema%') AND Stock > 0"
            result = execute_query(query)
            if result:
                response = "🥛 **LÁCTEOS**\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
        
        # Detectar consultas sobre productos de panadería y dulces
        if any(word in question_lower for word in ["pan", "panadería", "panaderia", "dulce", "dulces", "galleta", "galletas"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%pan%' OR Nombre LIKE '%galleta%' OR Nombre LIKE '%dulce%' OR Nombre LIKE '%chocolate%' OR Nombre LIKE '%caramelo%' OR Nombre LIKE '%pastel%') AND Stock > 0"
            result = execute_query(query)
            if result:
                response = "🍞 **PANADERÍA Y DULCES**\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
        
        # Detectar consultas sobre productos de abarrotes
        if any(word in question_lower for word in ["abarrote", "abarrotes", "arroz", "pasta", "frijol", "frijoles", "lenteja", "lentejas"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%arroz%' OR Nombre LIKE '%pasta%' OR Nombre LIKE '%frijol%' OR Nombre LIKE '%lenteja%' OR Nombre LIKE '%aceite%' OR Nombre LIKE '%azúcar%' OR Nombre LIKE '%azucar%' OR Nombre LIKE '%sal%') AND Stock > 0"
            result = execute_query(query)
            if result:
                response = "🛒 **ABARROTES**\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
        
        # Detectar consultas sobre productos de tecnología
        if any(word in question_lower for word in ["tecnología", "tecnologia", "tecnológico", "tecnologico", "monitor", "teclado", "mouse", "computadora", "laptop"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%monitor%' OR Nombre LIKE '%teclado%' OR Nombre LIKE '%mouse%' OR Nombre LIKE '%computadora%' OR Nombre LIKE '%laptop%' OR Nombre LIKE '%celular%' OR Nombre LIKE '%tablet%' OR Nombre LIKE '%cable%') AND Stock > 0"
            result = execute_query(query)
            if result:
                response = "💻 **TECNOLOGÍA**\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
        
        # Detectar consultas sobre productos de papelería
        if any(word in question_lower for word in ["papelería", "papeleria", "esfero", "esferos", "cuaderno", "cuadernos", "papel", "lápiz", "lapiz"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%esfero%' OR Nombre LIKE '%cuaderno%' OR Nombre LIKE '%papel%' OR Nombre LIKE '%lápiz%' OR Nombre LIKE '%lapiz%' OR Nombre LIKE '%marcador%' OR Nombre LIKE '%tijera%' OR Nombre LIKE '%pegamento%') AND Stock > 0"
            result = execute_query(query)
            if result:
                response = "📚 **PAPELERÍA**\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
        
        # Detectar consultas sobre productos para mascotas
        if any(word in question_lower for word in ["mascota", "mascotas", "perro", "gato", "alimento para"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%perro%' OR Nombre LIKE '%gato%' OR Nombre LIKE '%mascota%' OR Nombre LIKE '%croqueta%' OR Nombre LIKE '%alimento%') AND Stock > 0"
            result = execute_query(query)
            if result:
                response = "🐕 **MASCOTAS**\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
            else:
                # No hay productos específicos de mascotas, pero podemos sugerir alternativas
                response = "Actualmente no tenemos productos específicos para mascotas (como alimento para perros o gatos) en nuestro inventario. "
                response += "Sin embargo, tenemos muchos otros productos que podrían ser útiles:\n\n"
                
                # Buscar productos que podrían ser útiles para mascotas
                query_alternativas = "SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%papel%' OR Nombre LIKE '%toalla%' OR Nombre LIKE '%jabon%' OR Nombre LIKE '%detergente%') AND Stock > 0"
                result_alt = execute_query(query_alternativas)
                
                if result_alt:
                    response += "Productos que podrían ser útiles para el cuidado de mascotas:\n"
                    for prod in result_alt:
                        nombre = prod.get('Nombre', '')
                        precio = format_price(prod.get('Precio', 0))
                        stock = prod.get('Stock', 0)
                        response += f"• {nombre}: {precio} ({stock} unidades)\n"
                
                response += "\n¿Te interesa algún producto específico o necesitas ayuda con otra categoría?"
                return response
        
        # Detectar consultas sobre productos para bebés
        if any(word in question_lower for word in ["bebé", "bebe", "bebés", "bebes", "pañal", "pañales", "leche en polvo", "fórmula", "formula"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE (Nombre LIKE '%bebe%' OR Nombre LIKE '%bebé%' OR Nombre LIKE '%pañal%' OR Nombre LIKE '%formula%' OR Nombre LIKE '%fórmula%' OR Nombre LIKE '%biberon%' OR Nombre LIKE '%chupon%' OR Nombre LIKE '%papilla%') AND Stock > 0"
            result = execute_query(query)
            if result:
                response = "👶 **BEBÉS**\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
        
        # Detectar consultas sobre productos nuevos
        if any(word in question_lower for word in ["nuevo", "nuevos", "nueva", "nuevas", "llegaron", "llegó", "llegaron", "recién", "recien", "reciente", "recientes"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock, FechaCreacion FROM Productos WHERE Stock > 0 ORDER BY FechaCreacion DESC"
            result = execute_query(query)
            if result:
                response = "🆕 **PRODUCTOS NUEVOS**\n\n"
                response += "Aquí tienes los productos más recientes en nuestro inventario:\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    fecha = prod.get('FechaCreacion', '')
                    if fecha:
                        # Formatear la fecha para mostrar solo la fecha sin la hora
                        try:
                            fecha_obj = datetime.fromisoformat(str(fecha).replace('Z', '+00:00'))
                            fecha_formateada = fecha_obj.strftime('%d/%m/%Y')
                        except:
                            fecha_formateada = str(fecha)[:10]  # Solo los primeros 10 caracteres (YYYY-MM-DD)
                    else:
                        fecha_formateada = "Fecha no disponible"
                    response += f"• {nombre}: {precio} ({stock} unidades) - Llegó: {fecha_formateada}\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
            else:
                return "No pude obtener la información de productos nuevos en este momento. ¿Te interesa algún producto específico?"
        
        # Detectar consultas sobre productos más vendidos
        if any(word in question_lower for word in ["más vendido", "mas vendido", "más vendidos", "mas vendidos", "populares", "más comprado", "mas comprado", "más popular", "mas popular"]):
            query = "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Stock > 0 ORDER BY Stock DESC"
            result = execute_query(query)
            if result:
                response = "🔥 **PRODUCTOS MÁS POPULARES**\n\n"
                response += "Aquí tienes los productos con mayor stock (más vendidos):\n\n"
                for prod in result[:8]:
                    nombre = prod.get('Nombre', '')
                    precio = format_price(prod.get('Precio', 0))
                    stock = prod.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
                response += "\n¿Te interesa algún producto específico?"
                return response
            else:
                return "No pude obtener la información de productos más vendidos en este momento. ¿Te interesa algún producto específico?"
        
        # Clasificar el tipo de consulta
        classification = query_classifier.classify_query(question, context)
        
        if classification.query_type == "service":
            return "Te puedo ayudar con información sobre nuestros servicios. ¿Necesitas información sobre entrega, horarios, ubicación o algún otro servicio específico?"
        
        elif classification.query_type == "information":
            return "Te puedo ayudar con información sobre precios, stock, marcas y promociones. ¿Qué información específica necesitas?"
        
        else:
            return "Te puedo ayudar a encontrar productos, verificar precios, stock y obtener información sobre nuestros servicios. ¿Qué necesitas específicamente?"

    @timer
    def process_question(self, question: str, style: str = "largo", user_id: str = "default", session_id: str = None) -> str:
        """
        Procesa una pregunta y genera una respuesta con aprendizaje automático.
        """
        start_time = time.time()
        
        try:
            # Limpiar y normalizar la pregunta
            question = question.strip()
            if not question:
                return "Por favor, ingresa tu pregunta para poder ayudarte."

            # Obtener contexto de la conversación si hay session_id
            context = None
            if session_id:
                context = conversation_manager.get_context_for_question(session_id, question, user_id)
                # Mejorar la pregunta con contexto usando el conversation manager
                enhanced_question = conversation_manager.enhance_question_with_context(question, context)
                if enhanced_question != question:
                    logger.debug(f"Pregunta mejorada con contexto: '{question}' -> '{enhanced_question}'")
                    question = enhanced_question

            # Clasificar la consulta para el sistema de aprendizaje
            classification = query_classifier.classify_query(question, context)
            category = classification.query_type

            # Intentar obtener respuesta aprendida primero
            learned_response = learning_integrator.enhance_response_with_learning(
                question, "", category, user_id, session_id
            )
            
            if learned_response[1]:  # Si usa aprendizaje
                response = learned_response[0]
                response_time = time.time() - start_time
                
                # Registrar interacción para aprendizaje
                learning_integrator.record_interaction_for_learning(
                    question=question,
                    response=response,
                    category=category,
                    success=True,
                    confidence=0.9,  # Alta confianza para respuestas aprendidas
                    response_time=response_time,
                    user_id=user_id,
                    session_id=session_id,
                    product_mentions=[]
                )
                
                return response

            # Si no hay respuesta aprendida, procesar normalmente
            original_response = self._process_question_internal(question, style, user_id, session_id, context)
            
            # Mejorar respuesta con aprendizaje
            enhanced_response, uses_learning = learning_integrator.enhance_response_with_learning(
                question, original_response, category, user_id, session_id
            )
            
            response_time = time.time() - start_time
            
            # Extraer nombre del producto para registro
            product_name = self.extract_product_name(question, context)
            
            # Registrar interacción para aprendizaje
            learning_integrator.record_interaction_for_learning(
                question=question,
                response=enhanced_response,
                category=category,
                success=True,  # Asumimos éxito por ahora
                confidence=0.7,  # Confianza media para respuestas procesadas
                response_time=response_time,
                user_id=user_id,
                session_id=session_id,
                product_mentions=[product_name] if product_name else []
            )
            
            return enhanced_response

        except Exception as e:
            logger.error(f"Error procesando pregunta: {e}")
            response_time = time.time() - start_time
            
            # Registrar interacción fallida
            learning_integrator.record_interaction_for_learning(
                question=question,
                response="Error en procesamiento",
                category="error",
                success=False,
                confidence=0.0,
                response_time=response_time,
                user_id=user_id,
                session_id=session_id,
                product_mentions=[]
            )
            
            return "Lo siento, tuve un problema procesando tu pregunta. ¿Podrías intentar de nuevo?"
    
    def _handle_fast_price_query(self, question: str) -> Optional[str]:
        """
        Manejo ultra-rápido para consultas de precio de productos comunes.
        Evita completamente el procesamiento de RAG para consultas simples.
        """
        try:
            from app.llm.sql_generator import generate_sql_query
            from app.database.db import execute_query
            from app.utils.formatters import format_price
            
            # Detectar si es una consulta de precio simple
            question_lower = question.lower()
            price_keywords = ['precio', 'cuesta', 'vale', 'costo', 'valor']
            
            if not any(keyword in question_lower for keyword in price_keywords):
                return None
            
            # Intentar generar consulta SQL directamente
            sql_query = generate_sql_query(question)
            if not sql_query:
                logger.debug("No se pudo generar consulta SQL rápida")
                return None
            
            # Verificar que la consulta no sea demasiado genérica (solo rechazar consultas completamente sin filtros)
            if sql_query.strip().endswith("ORDER BY Precio ASC") and "LIKE" not in sql_query and "WHERE Nombre" not in sql_query:
                logger.debug("Consulta SQL demasiado genérica (sin filtros de producto), saltando atajo rápido")
                return None
            
            logger.debug(f"✅ Consulta SQL rápida generada: {sql_query}")
            
            # Ejecutar consulta directamente
            result = execute_query(sql_query)
            if not result:
                logger.debug("No se encontraron resultados en consulta rápida")
                return None
            
            logger.debug(f"✅ Consulta rápida ejecutada con {len(result)} resultados")
            
            # Formatear respuesta ultra-rápida
            if len(result) == 1:
                producto = result[0]
                nombre = producto.get('Nombre', 'Producto')
                precio = format_price(producto.get('Precio', 0))
                stock = producto.get('Stock', 0)
                response = f"📦 {nombre}: {precio} ({stock} unidades disponibles)"
                logger.debug(f"✅ Respuesta rápida única generada")
                return response
            else:
                # Múltiples productos - respuesta concisa
                productos_texto = []
                product_type = "productos"
                
                for i, producto in enumerate(result[:5]):  # Máximo 5 productos
                    nombre = producto.get('Nombre', 'Producto')
                    precio = format_price(producto.get('Precio', 0))
                    stock = producto.get('Stock', 0)
                    productos_texto.append(f"• {nombre}: {precio} ({stock} unidades)")
                    
                    # Detectar tipo de producto en la primera iteración
                    if i == 0:
                        nombre_lower = nombre.lower()
                        if 'atun' in nombre_lower or 'atún' in nombre_lower:
                            product_type = "atún"
                        elif 'leche' in nombre_lower:
                            product_type = "leche"
                        elif 'arroz' in nombre_lower:
                            product_type = "arroz"
                        elif 'aceite' in nombre_lower:
                            product_type = "aceite"
                
                response = f"Encontré {len(result)} productos de {product_type} con estos precios: 💰 Productos económicos:\n" + "\n".join(productos_texto)
                logger.debug(f"✅ Respuesta rápida múltiple generada")
                return response
            
        except Exception as e:
            logger.debug(f"❌ Error en consulta rápida: {e}")
            return None
    
    def _process_question_internal(self, question: str, style: str, user_id: str, session_id: str, context: Dict) -> str:
        """Procesamiento interno de la pregunta (lógica original)"""
        try:
            # 🚀 OPTIMIZACIÓN: Atajo rápido para consultas de precio de productos comunes
            fast_price_response = self._handle_fast_price_query(question)
            if fast_price_response:
                return fast_price_response

            # Detectar consultas de información general
            info_type = self._detect_info_query(question)
            if info_type:
                response = self._get_info_response(info_type)
                if session_id and context:
                    response = conversation_manager.generate_contextual_response(response, context)
                return response

            # Verificar si es una consulta de servicio
            service_response = self._handle_service_query(question, context)
            if service_response:
                if session_id and context:
                    service_response = conversation_manager.generate_contextual_response(service_response, context)
                return service_response

            # Detectar consultas especiales
            special_query = self._detect_special_query(question)
            if special_query:
                result = execute_query(special_query)
                if result:
                    product = result[0]
                    nombre = product.get('Nombre', 'Producto')
                    precio = format_price(product.get('Precio', 0))
                    stock = product.get('Stock', 0)
                    if "más caro" in question.lower():
                        response = f"El producto más caro en nuestro inventario es {nombre} con un precio de {precio} y {stock} unidades disponibles."
                    else:
                        response = f"El producto más económico con stock disponible es {nombre} con un precio de {precio} y {stock} unidades disponibles."
                    
                    if session_id and context:
                        response = conversation_manager.generate_contextual_response(response, context)
                    return response
                else:
                    return "No pude encontrar productos que cumplan con tu criterio."

            # Detectar consultas de rango de precios
            price_range = self._detect_price_range_query(question)
            if price_range:
                response = self._handle_price_range_query(price_range[0], price_range[1])
                if session_id and context:
                    response = conversation_manager.generate_contextual_response(response, context)
                return response

            # Extraer nombre del producto
            product_name = self.extract_product_name(question, context)
            
            if not product_name:
                response = self._improve_generic_response(question)
                if session_id and context:
                    response = conversation_manager.generate_contextual_response(response, context)
                return response

            # 🚀 CORRECCIÓN: Priorizar consultas de precio sobre consultas de stock
            # Detectar consultas de precio PRIMERO
            if self._detect_price_query(question):
                # Consulta de precio
                query = f"SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%{product_name}%' AND Stock > 0 ORDER BY Precio ASC"
                result = execute_query(query)
                if result:
                    response = self.generate_price_response(result, product_name)
                else:
                    response = self._handle_specific_product_not_found(product_name)
                
                if session_id and context:
                    response = conversation_manager.generate_contextual_response(response, context)
                return response

            # 🚀 CORRECCIÓN: Detectar consultas de stock total ANTES que disponibilidad
            elif self._detect_total_stock_query(question):
                # Consulta de cantidad total
                # Intentar búsqueda con variaciones singular/plural
                search_terms = [product_name]
                
                # Agregar variaciones para productos específicos problemáticos
                if product_name.lower() in ["cuadernos", "cuaderno"]:
                    search_terms.extend(["cuaderno", "cuadernos"])
                elif product_name.lower() in ["esferos", "esfero"]:
                    search_terms.extend(["esfero", "esferos"])
                elif product_name.lower() in ["teclados", "teclado"]:
                    search_terms.extend(["teclado", "teclados"])
                elif product_name.lower() in ["monitores", "monitor"]:
                    search_terms.extend(["monitor", "monitores"])
                
                # Buscar con cada término
                for term in search_terms:
                    query = f"SELECT SUM(Stock) as Total FROM Productos WHERE Nombre LIKE '%{term}%' AND Stock > 0"
                    result = execute_query(query)
                    if result and result[0].get('Total'):
                        total = int(result[0]['Total'])
                        response = self.response_generator.format_total_stock_response(total, product_name)
                        
                        if session_id and context:
                            response = conversation_manager.generate_contextual_response(response, context)
                        return response
                
                # Si no se encuentra con variaciones, usar la búsqueda original
                query = f"SELECT SUM(Stock) as Total FROM Productos WHERE Nombre LIKE '%{product_name}%' AND Stock > 0"
                result = execute_query(query)
                if result and result[0].get('Total'):
                    total = int(result[0]['Total'])
                    response = self.response_generator.format_total_stock_response(total, product_name)
                else:
                    response = f"No tenemos {product_name} en nuestro inventario actual."
                
                if session_id and context:
                    response = conversation_manager.generate_contextual_response(response, context)
                return response

            # Detectar consultas de disponibilidad
            elif self._detect_availability_query(question):
                # Consulta de disponibilidad
                # Intentar búsqueda con variaciones singular/plural
                search_terms = [product_name]
                
                # Agregar variaciones para productos específicos problemáticos
                if product_name.lower() in ["cuadernos", "cuaderno"]:
                    search_terms.extend(["cuaderno", "cuadernos"])
                elif product_name.lower() in ["esferos", "esfero"]:
                    search_terms.extend(["esfero", "esferos"])
                elif product_name.lower() in ["teclados", "teclado"]:
                    search_terms.extend(["teclado", "teclados"])
                elif product_name.lower() in ["monitores", "monitor"]:
                    search_terms.extend(["monitor", "monitores"])
                
                # Buscar con cada término
                for term in search_terms:
                    query = f"SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%{term}%' AND Stock > 0"
                    result = execute_query(query)
                    if result:
                        exists = len(result) > 0
                        response = self.response_generator.format_availability_response(exists, product_name, result)
                        
                        if session_id and context:
                            response = conversation_manager.generate_contextual_response(response, context)
                        return response
                
                # Si no se encuentra con variaciones, usar la búsqueda original
                query = f"SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%{product_name}%' AND Stock > 0"
                result = execute_query(query)
                exists = len(result) > 0
                response = self.response_generator.format_availability_response(exists, product_name, result)
                
                if session_id and context:
                    response = conversation_manager.generate_contextual_response(response, context)
                return response

            # Detectar consultas de marcas
            elif self._detect_brand_query(question):
                # Consulta de marcas
                query = f"SELECT DISTINCT TOP 10 Nombre FROM Productos WHERE Nombre LIKE '%{product_name}%' AND Stock > 0"
                result = execute_query(query)
                if result:
                    brands = []
                    for row in result:
                        brand = self.extract_brand(row.get('Nombre', ''))
                        if brand != "Sin marca" and brand not in brands:
                            brands.append(brand)
                    
                    if brands:
                        response = f"Las marcas disponibles para {product_name} son: {', '.join(brands[:10])}"
                        if len(brands) > 10:
                            response += f" y {len(brands) - 10} marcas más."
                    else:
                        response = f"Tenemos {product_name} disponibles, pero la mayoría son productos sin marca específica."
                else:
                    response = self._handle_specific_product_not_found(product_name)
                
                if session_id and context:
                    response = conversation_manager.generate_contextual_response(response, context)
                return response

            else:
                # Consulta general
                query = f"SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%{product_name}%' AND Stock > 0"
                result = execute_query(query)
                if result:
                    response = self.generate_generic_response(result, style)
                else:
                    response = self._handle_specific_product_not_found(product_name)
                
                if session_id and context:
                    response = conversation_manager.generate_contextual_response(response, context)
                return response

        except Exception as e:
            logger.error(f"Error en procesamiento interno: {e}")
            return "Lo siento, tuve un problema procesando tu pregunta. ¿Podrías intentar de nuevo?"

    def _handle_service_query(self, question: str, context: Dict = None) -> str:
        """Maneja consultas de servicios específicamente"""
        question_lower = question.lower()
        
        # Clasificar el tipo de servicio
        classification = query_classifier.classify_query(question, context)
        
        if classification.query_type == "service":
            # Generar respuesta de servicio apropiada
            if any(word in question_lower for word in ["entrega", "envío", "domicilio"]):
                return "Sí, ofrecemos entrega a domicilio en un radio de 10 km. El costo de envío es de $2.50 y el tiempo de entrega es de 2-4 horas. Para pedidos mayores a $50, el envío es gratuito."
            
            elif any(word in question_lower for word in ["horario", "abren", "cerrado", "atención"]):
                return "Nuestro horario de atención es de lunes a sábado de 8:00 AM a 8:00 PM, y domingos de 9:00 AM a 6:00 PM. Estamos cerrados en días festivos oficiales."
            
            elif any(word in question_lower for word in ["ubicado", "dirección", "dónde", "donde", "estacionamiento"]):
                return "Nos encontramos en la Av. Principal #123, Centro Comercial Plaza Mayor, Local 45. Estamos a 2 cuadras del parque central, con estacionamiento gratuito disponible."
            
            elif any(word in question_lower for word in ["puntos", "programa", "fidelidad", "beneficios"]):
                return "Tenemos un programa de fidelización con puntos acumulables. Por cada $10 de compra obtienes 1 punto. Los puntos se pueden canjear por descuentos en futuras compras."
            
            elif any(word in question_lower for word in ["ayudar", "ayuda", "buscar", "encontrar", "recomendar"]):
                return "Estoy aquí para ayudarte con cualquier consulta sobre nuestros productos, precios, horarios, entrega o servicios. ¿En qué puedo asistirte específicamente?"
        
        # Si no es claramente un servicio, continuar con el procesamiento normal
        return None

    def extract_product_name(self, question: str, context: Dict = None) -> Optional[str]:
        """Extrae el nombre del producto de la pregunta con mejoras contextuales"""
        question_lower = question.lower()
        
        # Si hay contexto y es una pregunta de seguimiento, usar el producto anterior
        if context and context.get("last_product"):
            # Detectar si es una pregunta de seguimiento
            follow_up_indicators = [
                "también", "además", "otro", "otra", "más", "cuál", "cual", "qué", "que",
                "precio", "stock", "unidades", "marca", "disponible", "recomendar"
            ]
            
            if any(indicator in question_lower for indicator in follow_up_indicators):
                return context["last_product"]
        
        # Buscar productos específicos en la pregunta
        product_keywords = [
            # Alimentos básicos
            "arroz", "leche", "aceite", "pan", "huevos", "carne", "pescado", "frutas", "verduras",
            "cereales", "pasta", "salsas", "condimentos", "bebidas", "jugos", "refrescos", "agua",
            "café", "té", "chocolate", "dulces", "galletas", "snacks", "atún", "tuna", "queso",
            "mantequilla", "azúcar", "azucar", "sal", "harina", "frijoles", "lentejas",
            
            # Productos de limpieza
            "detergente", "jabón", "jabon", "shampoo", "papel higiénico", "papel higienico", 
            "toallas", "desinfectante", "limpiador", "escoba", "trapeador", "bolsas", "pañales",
            "pañal", "servilletas", "toallas de papel", "cloro", "suavizante",
            
            # Cuidado personal
            "desodorante", "crema", "pasta dental", "pasta de dientes", "cepillo", "cepillo de dientes",
            "peine", "maquillaje", "perfume", "protector solar", "papel de baño", "papel sanitario",
            
            # Hogar y oficina
            "baterías", "baterias", "bombillos", "cables", "herramientas", "pintura", "pegamento", 
            "cinta", "papel", "lápices", "lapices", "lápiz", "lapiz", "cuadernos", "libretas",
            "plumas", "bolígrafos", "boligrafos", "marcadores", "tijeras", "grapas", "clips",
            
            # Tecnología y electrónicos
            "monitor", "monitores", "teclado", "teclados", "mouse", "ratón", "ratones",
            "laptop", "computadora", "pc", "tablet", "celular", "teléfono", "telefono",
            "cámara", "camara", "auriculares", "altavoces", "bocinas", "cable", "cables",
            "cargador", "cargadores", "adaptador", "adaptadores", "usb", "hdmi", "vga",
            
            # Papelería y escritura
            "esfero", "esferos", "bolígrafo", "boligrafo", "bolígrafos", "boligrafos",
            "lápiz", "lapiz", "lápices", "lapices", "cuaderno", "cuadernos", "libreta", "libretas",
            "marcador", "marcadores", "resaltador", "resaltadores", "tijera", "tijeras",
            "grapa", "grapas", "clip", "clips", "pegamento", "cinta", "papel", "hojas",
            
            # Productos específicos mencionados
            "lápiz", "lapiz", "lápices", "lapices", "monitor", "monitores", "esfero", "esferos",
            "teclado", "teclados", "cuaderno", "cuadernos"
        ]
        
        for keyword in product_keywords:
            if keyword in question_lower:
                return keyword
        
        # Buscar patrones más complejos
        patterns = [
            r"(\w+)\s+(?:de|del|la|el)\s+(\w+)",  # "marca de producto"
            r"(\w+)\s+(?:con|sin)\s+(\w+)",       # "producto con característica"
            r"(\w+)\s+(?:integral|especial|premium)",  # "producto integral"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, question_lower)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        for word in match:
                            if word in product_keywords:
                                return word
                    elif match in product_keywords:
                        return match

        return None

    def generate_price_response(self, result: List[Dict[str, Any]], product_name: str) -> str:
        """
        Genera una respuesta mejorada para consultas de precio.
        """
        if not result:
            return f"No encontré información de precios para {product_name}."
        
        if len(result) == 1:
            product = result[0]
            nombre = product.get('Nombre', 'Producto')
            precio = format_price(product.get('Precio', 0))
            stock = product.get('Stock', 0)
            return f"El {product_name} que encontré es {nombre} con un precio de {precio} y {stock} unidades disponibles."
        
        else:
            response = f"Encontré {len(result)} productos de {product_name} con estos precios:\n"
            
            # Agrupar por rangos de precio
            price_ranges = {}
            for product in result:
                precio = product.get('Precio', 0)
                if precio <= 5:
                    range_key = "económicos"
                elif precio <= 15:
                    range_key = "precio medio"
                else:
                    range_key = "premium"
                
                if range_key not in price_ranges:
                    price_ranges[range_key] = []
                price_ranges[range_key].append(product)
            
            for range_name, products in price_ranges.items():
                response += f"\n📦 Productos {range_name}:\n"
                for product in products[:3]:  # Mostrar máximo 3 por rango
                    nombre = product.get('Nombre', 'Producto')
                    precio = format_price(product.get('Precio', 0))
                    stock = product.get('Stock', 0)
                    response += f"• {nombre}: {precio} ({stock} unidades)\n"
            
            return response

    def generate_generic_response(self, result: List[Dict[str, Any]], style: str = "largo") -> str:
        """
        Genera una respuesta genérica mejorada.
        """
        if not result:
            return "No encontré productos que coincidan con tu búsqueda."

        if style == "corto":
            return f"Encontré {len(result)} productos disponibles."
        
        # Respuesta detallada
        response = f"Encontré {len(result)} productos que coinciden con tu búsqueda:\n\n"
        
        for i, product in enumerate(result[:5], 1):  # Mostrar máximo 5 productos
            nombre = product.get('Nombre', 'Producto')
            precio = format_price(product.get('Precio', 0))
            stock = product.get('Stock', 0)
            
            # Agregar información adicional según el stock
            if stock < 10:
                stock_info = f"⚠️ Solo {stock} unidades disponibles"
            elif stock < 50:
                stock_info = f"📦 {stock} unidades en stock"
            else:
                stock_info = f"✅ {stock} unidades disponibles"
            
            response += f"{i}. {nombre}\n"
            response += f"   💰 Precio: {precio}\n"
            response += f"   {stock_info}\n\n"
        
        if len(result) > 5:
            response += f"... y {len(result) - 5} productos más.\n\n"
        
        response += "¿Te gustaría información específica sobre alguno de estos productos?"
        
        return response

    def extract_contextual_info(self, question: str, response: str, result: List[Dict] = None) -> Dict[str, Any]:
        """Extrae información contextual de la pregunta y respuesta"""
        contextual_info = {
            "product_mentions": [],
            "price_mentions": [],
            "category_mentions": []
        }
        
        # Extraer productos mencionados
        product_name = self.extract_product_name(question)
        if product_name:
            contextual_info["product_mentions"].append(product_name)
        
        # Extraer precios de la respuesta
        price_pattern = r'\$(\d+\.?\d*)'
        prices = re.findall(price_pattern, response)
        contextual_info["price_mentions"] = [float(p) for p in prices]
        
        # Extraer categorías basadas en palabras clave
        category_keywords = {
            "productos": ["producto", "disponible", "tienen", "hay", "stock"],
            "precios": ["precio", "costo", "cuánto", "cuanto", "vale"],
            "entrega": ["entrega", "envío", "domicilio", "tiempo"],
            "horarios": ["horario", "abren", "cerrado", "atención"],
            "ubicación": ["ubicado", "dirección", "dónde", "donde"],
            "fidelización": ["puntos", "programa", "fidelidad", "beneficios"],
            "promociones": ["promoción", "descuento", "oferta", "cupón"]
        }
        
        question_lower = question.lower()
        for category, keywords in category_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                contextual_info["category_mentions"].append(category)
                break
        
        return contextual_info

    def process_question_with_context(self, question: str, style: str = "largo", user_id: str = "default", session_id: str = None) -> str:
        """
        Procesa una pregunta con contexto conversacional completo.
        """
        # Procesar la pregunta normalmente
        response = self.process_question(question, style, user_id, session_id)
        
        # Si hay session_id, registrar el turno en la conversación
        if session_id:
            # Extraer información contextual
            contextual_info = self.extract_contextual_info(question, response)
            
            # Registrar el turno en el gestor de conversaciones
            conversation_manager.add_turn(
                session_id=session_id,
                question=question,
                answer=response,
                product_mentions=contextual_info["product_mentions"],
                price_mentions=contextual_info["price_mentions"],
                category_mentions=contextual_info["category_mentions"],
                user_id=user_id
            )
            
            logger.debug(f"Turno registrado en conversación {session_id}: {len(contextual_info['product_mentions'])} productos, {len(contextual_info['price_mentions'])} precios")
        
        return response

def retriever(question: str, estilo: str = "largo", user_id: str = "default", session_id: str = None) -> str:
    """
    Función principal para procesar preguntas del chatbot con contexto conversacional.
    """
    retriever_instance = Retriever()
    return retriever_instance.process_question_with_context(question, estilo, user_id, session_id)
