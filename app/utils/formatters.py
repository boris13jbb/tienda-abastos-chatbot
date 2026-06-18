"""
Módulo con funciones para formatear datos en el chatbot de la tienda de abastos.
"""

from typing import List, Dict, Any, Optional

def format_price(price: float, currency: str = "$") -> str:
    """
    Formatea un precio con el símbolo de moneda.
    
    Args:
        price: Precio a formatear
        currency: Símbolo de moneda
        
    Returns:
        Precio formateado
    """
    try:
        return f"{currency}{price:.2f}"
    except (TypeError, ValueError):
        # Si price no es un número, devolver como string
        return f"{currency}{price}"

def format_product(product: Dict[str, Any], detailed: bool = False) -> str:
    """
    Formatea la información de un Productos.
    
    Args:
        product: Diccionario con la información del Productos
        detailed: Si se debe mostrar información detallada
        
    Returns:
        Información del Productos formateada
    """
    if detailed:
        description = product.get('Descripcion', product.get('descripcion', 'Sin descripción'))
        # Comprobar si hay precio y stock disponibles
        if 'Precio' in product or 'precio' in product:
            precio = product.get('Precio', product.get('precio', 0))
            precio_formateado = format_price(precio)
        else:
            precio_formateado = "Precio no disponible"
            
        if 'Stock' in product or 'stock' in product:
            stock = product.get('Stock', product.get('stock', 0))
        else:
            stock = "Stock no disponible"
            
        return (
            f"- {product.get('Nombre', product.get('nombre', 'Productos'))}\n"
            f"  Descripción: {description}\n"
            f"  Precio: {precio_formateado}\n"
            f"  Stock: {stock} unidades"
        )
    else:
        nombre = product.get('Nombre', product.get('nombre', 'Productos'))
        
        # Comprobar si hay precio y stock disponibles
        if 'Precio' in product or 'precio' in product:
            precio = product.get('Precio', product.get('precio', 0))
            precio_formateado = format_price(precio)
        else:
            precio_formateado = "Precio no disponible"
            
        if 'Stock' in product or 'stock' in product:
            stock = product.get('Stock', product.get('stock', 0))
        else:
            stock = "Stock no disponible"
            
        return f"{nombre} - {precio_formateado} ({stock} unidades)"

def format_product_list(products: List[Dict[str, Any]], detailed: bool = False) -> str:
    """
    Formatea una lista de Productos.
    
    Args:
        products: Lista de Productos
        detailed: Si se debe mostrar información detallada
        
    Returns:
        Lista de Productos formateada
    """
    if not products:
        return "No se encontraron Productos."
    
    if detailed:
        result = f"Encontré {len(products)} Productos:\n\n"
        for product in products:
            result += format_product(product, detailed=True) + "\n\n"
        return result.strip()
    else:
        result = f"Encontré {len(products)} Productos:\n"
        for product in products:
            result += f"- {format_product(product)}\n"
        return result.strip()

def format_stock_summary(products: List[Dict[str, Any]]) -> str:
    """
    Genera un resumen del stock de Productos.
    
    Args:
        products: Lista de Productos
        
    Returns:
        Resumen del stock formateado
    """
    if not products:
        return "No hay Productos en stock."
    
    # Extraer stock de los Productos, usando claves en minúsculas o mayúsculas
    total_stock = sum(p.get('Stock', p.get('stock', 0)) for p in products)
    
    # Contar Productos con bajo stock (≤10)
    low_stock = sum(1 for p in products if p.get('Stock', p.get('stock', 0)) <= 10)
    
    return (
        f"Resumen de inventario:\n"
        f"- Total de Productos: {len(products)}\n"
        f"- Unidades totales en stock: {total_stock}\n"
        f"- Productos con bajo stock (≤10): {low_stock}"
    )

def format_price_range(products: List[Dict[str, Any]]) -> str:
    """
    Genera un resumen del rango de precios de los Productos.
    
    Args:
        products: Lista de Productos
        
    Returns:
        Resumen del rango de precios formateado
    """
    if not products:
        return "No hay Productos para analizar precios."
    
    # Extraer precios, permitiendo claves en mayúsculas o minúsculas
    prices = []
    for p in products:
        if 'Precio' in p:
            prices.append(p['Precio'])
        elif 'precio' in p:
            prices.append(p['precio'])
    
    if not prices:
        return "No hay información de precios disponible para estos Productos."
    
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    
    return (
        f"Rango de precios:\n"
        f"- Precio mínimo: {format_price(min_price)}\n"
        f"- Precio máximo: {format_price(max_price)}\n"
        f"- Precio promedio: {format_price(avg_price)}"
    )

def format_availability_summary(product_name: str, products: List[Dict[str, Any]]) -> str:
    """
    Genera un resumen de la disponibilidad de un Productos.
    
    Args:
        product_name: Nombre del Productos a buscar
        products: Lista de Productos
        
    Returns:
        Resumen de disponibilidad formateado
    """
    if not products:
        return f"No se encontraron Productos que coincidan con '{product_name}'."
    
    # Calcular stock total sumando el stock de todos los Productos
    total_stock = 0
    for p in products:
        if 'Stock' in p:
            total_stock += p['Stock']
        elif 'stock' in p:
            total_stock += p['stock']
    
    variants = len(products)
    
    if variants == 1:
        p = products[0]
        nombre = p.get('Nombre', p.get('nombre', product_name))
        stock = p.get('Stock', p.get('stock', 0))
        
        # Verificar si hay precio disponible
        if 'Precio' in p or 'precio' in p:
            precio = p.get('Precio', p.get('precio', 0))
            precio_formateado = f"Precio: {format_price(precio)}"
        else:
            precio_formateado = "Precio no disponible"
        
        return (
            f"Disponibilidad de {nombre}:\n"
            f"- En stock: {stock} unidades\n"
            f"- {precio_formateado}"
        )
    else:
        result = f"Encontramos {variants} variantes de {product_name}:\n"
        for p in products:
            nombre = p.get('Nombre', p.get('nombre', 'Productos'))
            stock = p.get('Stock', p.get('stock', 0))
            
            # Verificar si hay precio disponible
            if 'Precio' in p or 'precio' in p:
                precio = p.get('Precio', p.get('precio', 0))
                precio_formateado = format_price(precio)
            else:
                precio_formateado = "Precio no disponible"
            
            result += (
                f"- {nombre}: {stock} unidades "
                f"a {precio_formateado}\n"
            )
        result += f"\nStock total: {total_stock} unidades"
        return result

def format_conversation_response(question: str, response: str) -> str:
    """
    Formatea la respuesta para mantener el contexto de la conversación.
    
    Args:
        question: Pregunta del usuario
        response: Respuesta generada
        
    Returns:
        Respuesta formateada para la conversación
    """
    # Verificar si la respuesta ya es suficientemente conversacional
    if "hola" in question.lower() or "buenas" in question.lower():
        return response  # Ya es un saludo, no hay necesidad de modificar
    
    # Ajustar la respuesta para que sea más conversacional
    question_words = ["qué", "cuál", "cuánto", "cuántos", "dónde", "cómo", "quién", "cuándo", "por qué"]
    is_question = any(word in question.lower() for word in question_words) or "?" in question
    
    if is_question:
        # Si es una pregunta, la respuesta ya debería ser adecuada
        return response
    else:
        # Si no es una pregunta, hacer la respuesta más conversacional
        if "no encontré información" in response.lower():
            return f"Lo siento, no encontré información sobre '{question}'. ¿Hay algo más en lo que pueda ayudarte?"
        else:
            # Si la respuesta es muy corta, añadir una pregunta de seguimiento
            if len(response) < 100:
                return f"{response} ¿Necesitas más información sobre esto?"
            else:
                return response