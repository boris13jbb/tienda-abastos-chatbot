"""
Sistema de Aprendizaje Automático para el Chatbot
Permite que el sistema mejore sus respuestas basándose en las interacciones previas
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np
from collections import defaultdict, Counter
import pickle

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class Interaction:
    """Representa una interacción del usuario con el chatbot"""
    id: str
    user_id: str
    session_id: str
    question: str
    answer: str
    success: bool
    confidence: float
    response_time: float
    timestamp: datetime
    product_mentions: List[str]
    category: str
    user_feedback: Optional[int] = None  # 1-5 rating
    user_comment: Optional[str] = None

@dataclass
class LearningPattern:
    """Patrón de aprendizaje identificado"""
    pattern_type: str  # "question_similarity", "response_improvement", "category_pattern"
    pattern_data: Dict[str, Any]
    confidence: float
    frequency: int
    last_updated: datetime
    success_rate: float

class LearningManager:
    """Gestiona el aprendizaje automático del chatbot"""
    
    def __init__(self, db_path: str = "data/learning/learning.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.patterns_file = self.db_path.parent / "learned_patterns.pkl"
        self.faq_file = self.db_path.parent / "faq_database.json"
        
        self._init_database()
        self.learned_patterns = self._load_patterns()
        self.faq_database = self._load_faq()
        
        logger.info("Sistema de aprendizaje automático inicializado")
    
    def _init_database(self):
        """Inicializa la base de datos de aprendizaje"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Tabla de interacciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    confidence REAL NOT NULL,
                    response_time REAL NOT NULL,
                    timestamp DATETIME NOT NULL,
                    product_mentions TEXT,
                    category TEXT,
                    user_feedback INTEGER,
                    user_comment TEXT
                )
            ''')
            
            # Tabla de patrones aprendidos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    pattern_data TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    frequency INTEGER NOT NULL,
                    last_updated DATETIME NOT NULL,
                    success_rate REAL NOT NULL
                )
            ''')
            
            # Tabla de FAQ dinámico
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS faq_database (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    success_rate REAL DEFAULT 1.0,
                    last_used DATETIME NOT NULL,
                    created_at DATETIME NOT NULL
                )
            ''')
            
            # Índices para optimizar consultas
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_category ON interactions(category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_success ON interactions(success)')
            
            conn.commit()
            conn.close()
            logger.info("Base de datos de aprendizaje inicializada correctamente")
            
        except Exception as e:
            logger.error(f"Error al inicializar base de datos de aprendizaje: {str(e)}")
    
    def record_interaction(self, interaction: Interaction):
        """Registra una nueva interacción para aprendizaje"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO interactions 
                (id, user_id, session_id, question, answer, success, confidence, 
                 response_time, timestamp, product_mentions, category, user_feedback, user_comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                interaction.id,
                interaction.user_id,
                interaction.session_id,
                interaction.question,
                interaction.answer,
                interaction.success,
                interaction.confidence,
                interaction.response_time,
                interaction.timestamp.isoformat(),
                json.dumps(interaction.product_mentions),
                interaction.category,
                interaction.user_feedback,
                interaction.user_comment
            ))
            
            conn.commit()
            conn.close()
            
            # Actualizar patrones después de cada interacción
            self._update_patterns()
            
            logger.debug(f"Interacción registrada: {interaction.id}")
            
        except Exception as e:
            logger.error(f"Error al registrar interacción: {str(e)}")
    
    def _update_patterns(self):
        """Actualiza los patrones de aprendizaje basándose en las interacciones recientes"""
        try:
            # Obtener interacciones recientes (últimas 1000)
            recent_interactions = self._get_recent_interactions(1000)
            
            # Analizar patrones de similitud de preguntas
            self._analyze_question_similarity(recent_interactions)
            
            # Analizar mejoras de respuestas
            self._analyze_response_improvements(recent_interactions)
            
            # Analizar patrones por categoría
            self._analyze_category_patterns(recent_interactions)
            
            # Actualizar FAQ dinámico
            self._update_faq_database(recent_interactions)
            
            # Guardar patrones actualizados
            self._save_patterns()
            
        except Exception as e:
            logger.error(f"Error al actualizar patrones: {str(e)}")
    
    def _get_recent_interactions(self, limit: int = 1000) -> List[Interaction]:
        """Obtiene las interacciones más recientes"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM interactions 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            interactions = []
            for row in rows:
                interaction = Interaction(
                    id=row[0],
                    user_id=row[1],
                    session_id=row[2],
                    question=row[3],
                    answer=row[4],
                    success=bool(row[5]),
                    confidence=row[6],
                    response_time=row[7],
                    timestamp=datetime.fromisoformat(row[8]),
                    product_mentions=json.loads(row[9]) if row[9] else [],
                    category=row[10],
                    user_feedback=row[11],
                    user_comment=row[12]
                )
                interactions.append(interaction)
            
            return interactions
            
        except Exception as e:
            logger.error(f"Error al obtener interacciones recientes: {str(e)}")
            return []
    
    def _analyze_question_similarity(self, interactions: List[Interaction]):
        """Analiza patrones de similitud en preguntas"""
        if len(interactions) < 10:
            return
        
        # Agrupar preguntas similares
        question_groups = defaultdict(list)
        
        for interaction in interactions:
            # Normalizar pregunta para agrupación
            normalized_question = self._normalize_question(interaction.question)
            question_groups[normalized_question].append(interaction)
        
        # Identificar grupos con múltiples interacciones
        for normalized_q, group in question_groups.items():
            if len(group) >= 3:  # Mínimo 3 interacciones similares
                success_rate = sum(1 for i in group if i.success) / len(group)
                avg_confidence = np.mean([i.confidence for i in group])
                
                pattern = LearningPattern(
                    pattern_type="question_similarity",
                    pattern_data={
                        "normalized_question": normalized_q,
                        "original_questions": [i.question for i in group],
                        "best_answer": self._find_best_answer(group),
                        "avg_response_time": np.mean([i.response_time for i in group])
                    },
                    confidence=avg_confidence,
                    frequency=len(group),
                    last_updated=datetime.now(),
                    success_rate=success_rate
                )
                
                self.learned_patterns[f"similarity_{normalized_q}"] = pattern
    
    def _analyze_response_improvements(self, interactions: List[Interaction]):
        """Analiza mejoras potenciales en respuestas"""
        # Agrupar por categoría y analizar respuestas exitosas vs fallidas
        category_responses = defaultdict(lambda: {"success": [], "failure": []})
        
        for interaction in interactions:
            if interaction.success:
                category_responses[interaction.category]["success"].append(interaction)
            else:
                category_responses[interaction.category]["failure"].append(interaction)
        
        for category, responses in category_responses.items():
            if len(responses["success"]) >= 5 and len(responses["failure"]) >= 3:
                # Analizar diferencias entre respuestas exitosas y fallidas
                success_patterns = self._extract_response_patterns(responses["success"])
                failure_patterns = self._extract_response_patterns(responses["failure"])
                
                pattern = LearningPattern(
                    pattern_type="response_improvement",
                    pattern_data={
                        "category": category,
                        "success_patterns": success_patterns,
                        "failure_patterns": failure_patterns,
                        "improvement_suggestions": self._generate_improvement_suggestions(
                            success_patterns, failure_patterns
                        )
                    },
                    confidence=0.8,
                    frequency=len(responses["success"]) + len(responses["failure"]),
                    last_updated=datetime.now(),
                    success_rate=len(responses["success"]) / (len(responses["success"]) + len(responses["failure"]))
                )
                
                self.learned_patterns[f"improvement_{category}"] = pattern
    
    def _analyze_category_patterns(self, interactions: List[Interaction]):
        """Analiza patrones por categoría de consulta"""
        category_stats = defaultdict(lambda: {
            "count": 0,
            "success_count": 0,
            "avg_confidence": [],
            "avg_response_time": [],
            "common_products": Counter(),
            "common_questions": Counter()
        })
        
        for interaction in interactions:
            stats = category_stats[interaction.category]
            stats["count"] += 1
            if interaction.success:
                stats["success_count"] += 1
            stats["avg_confidence"].append(interaction.confidence)
            stats["avg_response_time"].append(interaction.response_time)
            
            for product in interaction.product_mentions:
                stats["common_products"][product] += 1
            
            stats["common_questions"][interaction.question] += 1
        
        for category, stats in category_stats.items():
            if stats["count"] >= 10:  # Mínimo 10 interacciones por categoría
                pattern = LearningPattern(
                    pattern_type="category_pattern",
                    pattern_data={
                        "category": category,
                        "total_interactions": stats["count"],
                        "success_rate": stats["success_count"] / stats["count"],
                        "avg_confidence": np.mean(stats["avg_confidence"]),
                        "avg_response_time": np.mean(stats["avg_response_time"]),
                        "top_products": dict(stats["common_products"].most_common(5)),
                        "top_questions": dict(stats["common_questions"].most_common(5))
                    },
                    confidence=0.9,
                    frequency=stats["count"],
                    last_updated=datetime.now(),
                    success_rate=stats["success_count"] / stats["count"]
                )
                
                self.learned_patterns[f"category_{category}"] = pattern
    
    def _update_faq_database(self, interactions: List[Interaction]):
        """Actualiza la base de datos de FAQ dinámico"""
        # Agrupar preguntas frecuentes
        question_frequency = Counter()
        question_answers = defaultdict(list)
        
        for interaction in interactions:
            normalized_q = self._normalize_question(interaction.question)
            question_frequency[normalized_q] += 1
            question_answers[normalized_q].append(interaction.answer)
        
        # Identificar preguntas frecuentes (más de 5 veces)
        for question, frequency in question_frequency.items():
            if frequency >= 5:
                # Encontrar la mejor respuesta para esta pregunta
                answers = question_answers[question]
                best_answer = self._find_best_answer_for_question(question, answers)
                
                # Actualizar o crear entrada en FAQ
                self._update_faq_entry(question, best_answer, frequency)
    
    def _normalize_question(self, question: str) -> str:
        """Normaliza una pregunta para agrupación"""
        # Convertir a minúsculas y remover puntuación
        normalized = question.lower().strip()
        # Remover palabras comunes que no afectan el significado
        stop_words = {"que", "cual", "cuanto", "como", "donde", "cuando", "por", "para", "con", "sin", "el", "la", "los", "las", "un", "una", "unos", "unas"}
        words = [w for w in normalized.split() if w not in stop_words]
        return " ".join(words)
    
    def _find_best_answer(self, interactions: List[Interaction]) -> str:
        """Encuentra la mejor respuesta basándose en éxito y confianza"""
        successful = [i for i in interactions if i.success]
        if successful:
            # Ordenar por confianza y éxito
            best = max(successful, key=lambda x: (x.confidence, x.user_feedback or 0))
            return best.answer
        else:
            # Si no hay respuestas exitosas, usar la más confiada
            return max(interactions, key=lambda x: x.confidence).answer
    
    def _find_best_answer_for_question(self, question: str, answers: List[str]) -> str:
        """Encuentra la mejor respuesta para una pregunta específica"""
        # Por ahora, usar la respuesta más larga (asumiendo que es más completa)
        return max(answers, key=len)
    
    def _extract_response_patterns(self, interactions: List[Interaction]) -> Dict[str, Any]:
        """Extrae patrones de las respuestas"""
        patterns = {
            "avg_length": np.mean([len(i.answer) for i in interactions]),
            "common_words": Counter(),
            "response_structure": defaultdict(int)
        }
        
        for interaction in interactions:
            words = interaction.answer.lower().split()
            patterns["common_words"].update(words)
            
            # Analizar estructura de respuesta
            if "precio" in interaction.answer.lower():
                patterns["response_structure"]["price_info"] += 1
            if "stock" in interaction.answer.lower():
                patterns["response_structure"]["stock_info"] += 1
            if "disponible" in interaction.answer.lower():
                patterns["response_structure"]["availability_info"] += 1
        
        return patterns
    
    def _generate_improvement_suggestions(self, success_patterns: Dict, failure_patterns: Dict) -> List[str]:
        """Genera sugerencias de mejora basándose en patrones"""
        suggestions = []
        
        # Comparar longitudes de respuesta
        if success_patterns["avg_length"] > failure_patterns["avg_length"]:
            suggestions.append("Respuestas más largas y detalladas tienden a ser más exitosas")
        
        # Comparar estructuras de respuesta
        success_structures = set(success_patterns["response_structure"].keys())
        failure_structures = set(failure_patterns["response_structure"].keys())
        
        missing_in_failures = success_structures - failure_structures
        for structure in missing_in_failures:
            suggestions.append(f"Incluir información de {structure} en respuestas")
        
        return suggestions
    
    def _update_faq_entry(self, question: str, answer: str, frequency: int):
        """Actualiza una entrada en la base de datos FAQ"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Verificar si ya existe
            cursor.execute('SELECT id, frequency FROM faq_database WHERE question = ?', (question,))
            existing = cursor.fetchone()
            
            if existing:
                # Actualizar frecuencia
                new_frequency = existing[1] + frequency
                cursor.execute('''
                    UPDATE faq_database 
                    SET frequency = ?, last_used = ?, answer = ?
                    WHERE id = ?
                ''', (new_frequency, datetime.now().isoformat(), answer, existing[0]))
            else:
                # Crear nueva entrada
                cursor.execute('''
                    INSERT INTO faq_database 
                    (question, answer, frequency, last_used, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (question, answer, frequency, datetime.now().isoformat(), datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error al actualizar FAQ: {str(e)}")
    
    def get_learned_response(self, question: str, category: str) -> Optional[str]:
        """Obtiene una respuesta aprendida para una pregunta"""
        try:
            # Buscar en FAQ dinámico
            faq_answer = self._get_faq_answer(question)
            if faq_answer:
                return faq_answer
            
            # Buscar patrones de similitud
            normalized_q = self._normalize_question(question)
            similarity_pattern = self.learned_patterns.get(f"similarity_{normalized_q}")
            if similarity_pattern and similarity_pattern.confidence > 0.8:
                return similarity_pattern.pattern_data["best_answer"]
            
            # Buscar patrones de categoría
            category_pattern = self.learned_patterns.get(f"category_{category}")
            if category_pattern:
                # Usar la pregunta más similar de la categoría
                top_questions = category_pattern.pattern_data["top_questions"]
                for top_q, freq in top_questions.items():
                    if self._calculate_similarity(question, top_q) > 0.7:
                        return self._get_faq_answer(top_q)
            
            return None
            
        except Exception as e:
            logger.error(f"Error al obtener respuesta aprendida: {str(e)}")
            return None
    
    def _get_faq_answer(self, question: str) -> Optional[str]:
        """Obtiene respuesta de la base de datos FAQ"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT answer FROM faq_database 
                WHERE question = ? AND frequency >= 5
                ORDER BY frequency DESC, last_used DESC
                LIMIT 1
            ''', (question,))
            
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error al obtener respuesta FAQ: {str(e)}")
            return None
    
    def _calculate_similarity(self, question1: str, question2: str) -> float:
        """Calcula similitud entre dos preguntas"""
        # Implementación simple basada en palabras comunes
        words1 = set(self._normalize_question(question1).split())
        words2 = set(self._normalize_question(question2).split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Obtiene insights del aprendizaje automático"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Estadísticas generales
            cursor.execute('SELECT COUNT(*) FROM interactions')
            total_interactions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM interactions WHERE success = 1')
            successful_interactions = cursor.fetchone()[0]
            
            cursor.execute('SELECT AVG(confidence) FROM interactions')
            avg_confidence = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT AVG(response_time) FROM interactions')
            avg_response_time = cursor.fetchone()[0] or 0
            
            # Categorías más populares
            cursor.execute('''
                SELECT category, COUNT(*) as count 
                FROM interactions 
                GROUP BY category 
                ORDER BY count DESC 
                LIMIT 5
            ''')
            top_categories = cursor.fetchall()
            
            # Preguntas más frecuentes
            cursor.execute('''
                SELECT question, COUNT(*) as count 
                FROM interactions 
                GROUP BY question 
                ORDER BY count DESC 
                LIMIT 10
            ''')
            top_questions = cursor.fetchall()
            
            conn.close()
            
            return {
                "total_interactions": total_interactions,
                "success_rate": successful_interactions / total_interactions if total_interactions > 0 else 0,
                "avg_confidence": avg_confidence,
                "avg_response_time": avg_response_time,
                "top_categories": [{"category": cat, "count": count} for cat, count in top_categories],
                "top_questions": [{"question": q, "count": count} for q, count in top_questions],
                "learned_patterns_count": len(self.learned_patterns),
                "faq_entries_count": len(self.faq_database)
            }
            
        except Exception as e:
            logger.error(f"Error al obtener insights: {str(e)}")
            return {}
    
    def _load_patterns(self) -> Dict[str, LearningPattern]:
        """Carga patrones aprendidos desde archivo"""
        try:
            if self.patterns_file.exists():
                with open(self.patterns_file, 'rb') as f:
                    patterns_data = pickle.load(f)
                    return {k: LearningPattern(**v) for k, v in patterns_data.items()}
        except Exception as e:
            logger.error(f"Error al cargar patrones: {str(e)}")
        return {}
    
    def _save_patterns(self):
        """Guarda patrones aprendidos en archivo"""
        try:
            patterns_data = {k: asdict(v) for k, v in self.learned_patterns.items()}
            with open(self.patterns_file, 'wb') as f:
                pickle.dump(patterns_data, f)
        except Exception as e:
            logger.error(f"Error al guardar patrones: {str(e)}")
    
    def _load_faq(self) -> Dict[str, str]:
        """Carga base de datos FAQ desde archivo"""
        try:
            if self.faq_file.exists():
                with open(self.faq_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error al cargar FAQ: {str(e)}")
        return {}
    
    def save_faq(self):
        """Guarda base de datos FAQ en archivo"""
        try:
            with open(self.faq_file, 'w', encoding='utf-8') as f:
                json.dump(self.faq_database, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error al guardar FAQ: {str(e)}")

# Instancia global del sistema de aprendizaje
learning_manager = LearningManager() 