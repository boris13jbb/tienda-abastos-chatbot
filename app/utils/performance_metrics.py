"""
Sistema de métricas de rendimiento para el chatbot.
Permite medir y validar tiempos de respuesta y otros indicadores de rendimiento.
"""

import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from statistics import mean, median
from app.utils.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

@dataclass
class PerformanceMetric:
    """Clase para almacenar métricas de rendimiento"""
    timestamp: datetime
    response_time: float
    operation_type: str
    success: bool
    error_message: Optional[str] = None

class PerformanceMonitor:
    """Monitor de rendimiento para el chatbot"""
    
    def __init__(self, max_metrics: int = 1000):
        self.metrics: List[PerformanceMetric] = []
        self.max_metrics = max_metrics
        self.response_time_target = settings.RESPONSE_TIME_TARGET  # 1.73 segundos
        self.max_concurrent_users = settings.MAX_CONCURRENT_USERS  # 100 usuarios
        
    def add_metric(self, response_time: float, operation_type: str, success: bool, error_message: Optional[str] = None):
        """Agrega una nueva métrica de rendimiento"""
        metric = PerformanceMetric(
            timestamp=datetime.now(),
            response_time=response_time,
            operation_type=operation_type,
            success=success,
            error_message=error_message
        )
        
        self.metrics.append(metric)
        
        # Mantener solo las métricas más recientes
        if len(self.metrics) > self.max_metrics:
            self.metrics = self.metrics[-self.max_metrics:]
        
        # Log si el tiempo de respuesta excede el objetivo
        if response_time > self.response_time_target:
            logger.warning(f"Tiempo de respuesta ({response_time:.2f}s) excede el objetivo ({self.response_time_target}s) para operación: {operation_type}")
    
    def get_stats(self, hours: int = 24) -> Dict[str, any]:
        """Obtiene estadísticas de rendimiento para las últimas N horas"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics if m.timestamp > cutoff_time]
        
        if not recent_metrics:
            return {
                "total_operations": 0,
                "success_rate": 0.0,
                "avg_response_time": 0.0,
                "median_response_time": 0.0,
                "target_achievement_rate": 0.0,
                "operations_within_target": 0,
                "total_operations": 0
            }
        
        response_times = [m.response_time for m in recent_metrics]
        successful_ops = [m for m in recent_metrics if m.success]
        
        operations_within_target = len([rt for rt in response_times if rt <= self.response_time_target])
        
        return {
            "total_operations": len(recent_metrics),
            "success_rate": len(successful_ops) / len(recent_metrics) * 100,
            "avg_response_time": mean(response_times),
            "median_response_time": median(response_times),
            "target_achievement_rate": (operations_within_target / len(recent_metrics)) * 100,
            "operations_within_target": operations_within_target,
            "target_response_time": self.response_time_target,
            "max_concurrent_users": self.max_concurrent_users
        }
    
    def check_performance_health(self) -> Dict[str, any]:
        """Verifica la salud del rendimiento del sistema"""
        stats = self.get_stats(hours=1)  # Última hora
        
        # Definir umbrales de salud
        health_status = "healthy"
        issues = []
        
        if stats["avg_response_time"] > self.response_time_target:
            health_status = "degraded"
            issues.append(f"Tiempo de respuesta promedio ({stats['avg_response_time']:.2f}s) excede el objetivo ({self.response_time_target}s)")
        
        if stats["success_rate"] < 95.0:
            health_status = "degraded"
            issues.append(f"Tasa de éxito ({stats['success_rate']:.1f}%) está por debajo del umbral (95%)")
        
        if stats["target_achievement_rate"] < 80.0:
            health_status = "degraded"
            issues.append(f"Tasa de logro del objetivo ({stats['target_achievement_rate']:.1f}%) está por debajo del umbral (80%)")
        
        return {
            "status": health_status,
            "issues": issues,
            "metrics": stats
        }
    
    def get_scalability_metrics(self) -> Dict[str, any]:
        """Obtiene métricas de escalabilidad"""
        # Simular métricas de escalabilidad basadas en el rendimiento actual
        stats = self.get_stats(hours=1)
        
        # Calcular capacidad estimada basada en el rendimiento actual
        if stats["avg_response_time"] > 0:
            estimated_capacity = int(self.max_concurrent_users * (self.response_time_target / stats["avg_response_time"]))
        else:
            estimated_capacity = self.max_concurrent_users
        
        return {
            "current_capacity": estimated_capacity,
            "max_design_capacity": self.max_concurrent_users,
            "capacity_utilization": (estimated_capacity / self.max_concurrent_users) * 100,
            "response_time_efficiency": (self.response_time_target / stats["avg_response_time"]) * 100 if stats["avg_response_time"] > 0 else 0,
            "scalability_status": "good" if estimated_capacity >= self.max_concurrent_users else "limited"
        }
    
    def get_optimization_recommendations(self) -> List[str]:
        """Obtiene recomendaciones de optimización basadas en las métricas"""
        recommendations = []
        stats = self.get_stats(hours=24)
        
        if stats["avg_response_time"] > self.response_time_target:
            recommendations.append("Considerar optimización del modelo LLM o caché más agresivo")
        
        if stats["success_rate"] < 95.0:
            recommendations.append("Revisar logs de errores y mejorar manejo de excepciones")
        
        if stats["target_achievement_rate"] < 80.0:
            recommendations.append("Implementar optimizaciones de consulta SQL y indexación")
        
        if len(recommendations) == 0:
            recommendations.append("El rendimiento está dentro de los parámetros esperados")
        
        return recommendations

# Instancia global del monitor de rendimiento
performance_monitor = PerformanceMonitor() 