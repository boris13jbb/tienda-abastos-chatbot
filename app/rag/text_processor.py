 
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo para procesamiento de texto.
Proporciona utilidades para limpieza, normalización y extracción de información de textos.
"""

import re
import unicodedata
import logging
from typing import List, Dict, Set, Tuple, Optional, Any

from app.utils.logger import get_logger

# Configurar logging específico para este módulo
logger = get_logger(__name__)

# Lista de stopwords en español
SPANISH_STOPWORDS = set([
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como", "con", "contra",
    "cual", "cuando", "de", "del", "desde", "donde", "durante", "e", "el", "ella",
    "ellas", "ellos", "en", "entre", "era", "erais", "eran", "eras", "eres", "es",
    "esa", "esas", "ese", "eso", "esos", "esta", "estaba", "estabais", "estaban",
    "estabas", "estad", "estada", "estadas", "estado", "estados", "estamos", "estando",
    "estar", "estaremos", "estará", "estarán", "estarás", "estaré", "estaréis", "estaría",
    "estaríais", "estaríamos", "estarían", "estarías", "estas", "este", "estemos", "esto",
    "estos", "estoy", "estuve", "estuviera", "estuvierais", "estuvieran", "estuvieras",
    "estuvieron", "estuviese", "estuvieseis", "estuviesen", "estuvieses", "estuvimos",
    "estuviste", "estuvisteis", "estuviéramos", "estuviésemos", "estuvo", "fue", "fuera",
    "fuerais", "fueran", "fueras", "fueron", "fuese", "fueseis", "fuesen", "fueses",
    "fui", "fuimos", "fuiste", "fuisteis", "fuéramos", "fuésemos", "ha", "habida",
    "habidas", "habido", "habidos", "habiendo", "habremos", "habrá", "habrán", "habrás",
    "habré", "habréis", "habría", "habríais", "habríamos", "habrían", "habrías", "habéis",
    "había", "habíais", "habíamos", "habían", "habías", "han", "has", "hasta", "hay",
    "haya", "hayamos", "hayan", "hayas", "hayáis", "he", "hemos", "hube", "hubiera",
    "hubierais", "hubieran", "hubieras", "hubieron", "hubiese", "hubieseis", "hubiesen",
    "hubieses", "hubimos", "hubiste", "hubisteis", "hubiéramos", "hubiésemos", "hubo",
    "la", "las", "le", "les", "lo", "los", "me", "mi", "mis", "mucho", "muchos", "muy",
    "más", "mí", "mía", "mías", "mío", "míos", "nada", "ni", "no", "nos", "nosotras",
    "nosotros", "nuestra", "nuestras", "nuestro", "nuestros", "o", "os", "otra", "otras",
    "otro", "otros", "para", "pero", "poco", "por", "porque", "que", "quien", "quienes",
    "qué", "se", "sea", "seamos", "sean", "seas", "seremos", "será", "serán", "serás",
    "seré", "seréis", "sería", "seríais", "seríamos", "serían", "serías", "seáis", "si",
    "sido", "siendo", "sin", "sobre", "sois", "somos", "son", "soy", "su", "sus", "suya",
    "suyas", "suyo", "suyos", "sí", "también", "tanto", "te", "tendremos", "tendrá",
    "tendrán", "tendrás", "tendré", "tendréis", "tendría", "tendríais", "tendríamos",
    "tendrían", "tendrías", "tened", "tenemos", "tenga", "tengamos", "tengan", "tengas",
    "tengo", "tengáis", "tenida", "tenidas", "tenido", "tenidos", "teniendo", "tenéis",
    "tenía", "teníais", "teníamos", "tenían", "tenías", "ti", "tiene", "tienen", "tienes",
    "todo", "todos", "tu", "tus", "tuve", "tuviera", "tuvierais", "tuvieran", "tuvieras",
    "tuvieron", "tuviese", "tuvieseis", "tuviesen", "tuvieses", "tuvimos", "tuviste",
    "tuvisteis", "tuviéramos", "tuviésemos", "tuvo", "tuya", "tuyas", "tuyo", "tuyos",
    "tú", "un", "una", "uno", "unos", "vosotras", "vosotros", "vuestra", "vuestras",
    "vuestro", "vuestros", "y", "ya", "yo", "él", "éramos"
])

class TextProcessor:
    """Clase para procesamiento y limpieza de texto."""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normaliza un texto: convierte a minúsculas, elimina acentos, 
        espacios múltiples y caracteres especiales.
        
        Args:
            text: Texto a normalizar.
            
        Returns:
            Texto normalizado.
        """
        if not text:
            return ""
            
        try:
            # Convertir a minúsculas
            text = text.lower()
            
            # Normalizar caracteres Unicode (quitar acentos)
            text = unicodedata.normalize('NFKD', text)
            text = ''.join([c for c in text if not unicodedata.combining(c)])
            
            # Eliminar caracteres especiales, conservando letras, números y espacios
            text = re.sub(r'[^\w\s]', ' ', text)
            
            # Eliminar espacios múltiples
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
        except Exception as e:
            logger.error(f"Error al normalizar texto: {str(e)}")
            return text
    
    @staticmethod
    def remove_stopwords(text: str, custom_stopwords: Optional[Set[str]] = None) -> str:
        """
        Elimina stopwords (palabras comunes) de un texto.
        
        Args:
            text: Texto del que eliminar stopwords.
            custom_stopwords: Conjunto adicional de stopwords personalizadas.
            
        Returns:
            Texto sin stopwords.
        """
        if not text:
            return ""
            
        try:
            # Combinar stopwords predefinidas y personalizadas
            stopwords = SPANISH_STOPWORDS.copy()
            if custom_stopwords:
                stopwords.update(custom_stopwords)
                
            # Dividir en palabras y eliminar stopwords
            words = text.split()
            filtered_words = [word for word in words if word not in stopwords]
            
            return ' '.join(filtered_words)
        except Exception as e:
            logger.error(f"Error al eliminar stopwords: {str(e)}")
            return text
    
    @staticmethod
    def extract_keywords(text: str, num_keywords: int = 5) -> List[str]:
        """
        Extrae las palabras clave más relevantes de un texto.
        
        Args:
            text: Texto del que extraer palabras clave.
            num_keywords: Número máximo de palabras clave a extraer.
            
        Returns:
            Lista de palabras clave ordenadas por relevancia.
        """
        if not text:
            return []
            
        try:
            # Normalizar y eliminar stopwords
            normalized_text = TextProcessor.normalize_text(text)
            clean_text = TextProcessor.remove_stopwords(normalized_text)
            
            # Dividir en palabras
            words = clean_text.split()
            
            # Contar frecuencia de palabras
            word_freq = {}
            for word in words:
                if len(word) > 2:  # Ignorar palabras muy cortas
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Ordenar por frecuencia y obtener las top keywords
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            keywords = [word for word, _ in sorted_words[:num_keywords]]
            
            return keywords
        except Exception as e:
            logger.error(f"Error al extraer palabras clave: {str(e)}")
            return []
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Limpia un texto aplicando normalización y eliminación de stopwords.
        
        Args:
            text: Texto a limpiar.
            
        Returns:
            Texto limpio.
        """
        if not text:
            return ""
            
        try:
            # Aplicar normalización
            normalized_text = TextProcessor.normalize_text(text)
            
            # Eliminar stopwords
            clean_text = TextProcessor.remove_stopwords(normalized_text)
            
            return clean_text
        except Exception as e:
            logger.error(f"Error al limpiar texto: {str(e)}")
            return text

# Crear una instancia global del procesador de texto
text_processor = TextProcessor()