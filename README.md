# ­ƒñû Chatbot Tienda de Abastos - Sistema Exclusivo para Empleados

## ­ƒôï Descripci├│n

Sistema de chatbot inteligente **exclusivo para el due├▒o de la tienda y sus empleados**, dise├▒ado para optimizar la gesti├│n de inventario, atenci├│n al cliente y operaciones internas. El sistema utiliza tecnolog├¡as de IA avanzadas para proporcionar respuestas precisas sobre productos, stock, precios y gesti├│n de la tienda.

## ­ƒöÉ Sistema Exclusivo para Empleados

### ­ƒÄ» Prop├│sito
- **Acceso restringido**: Solo empleados autorizados pueden acceder al sistema
- **Gesti├│n interna**: Herramientas para el due├▒o y empleados de la tienda
- **Seguridad empresarial**: Autenticaci├│n JWT y roles espec├¡ficos
- **Operaciones internas**: Consultas sobre inventario, productos y gesti├│n

### ­ƒæÑ Roles del Sistema
- **Due├▒o**: Acceso completo a todas las funcionalidades
- **Administrador**: Gesti├│n de empleados y configuraci├│n avanzada
- **Empleado**: Acceso a consultas de productos e inventario

### ­ƒÜ½ No es para Clientes Externos
- El sistema **NO est├í dise├▒ado** para atenci├│n al cliente externo
- **NO permite** acceso p├║blico o an├│nimo
- **Solo empleados registrados** pueden utilizar el chatbot

## ­ƒÜÇ Caracter├¡sticas Principales

### Ô£à Gesti├│n de Consultas Internas
- Consultas sobre disponibilidad de productos
- Informaci├│n de precios y fechas de caducidad
- Uso de t├®cnicas de embedding y RAG para respuestas precisas

### Ô£à Optimizaci├│n del Inventario
- Integraci├│n con sistemas de inventario en tiempo real
- Alertas sobre productos pr├│ximos a vencer o en baja existencia
- Sincronizaci├│n autom├ítica de productos

### Ô£à Atenci├│n Interna Automatizada
- Respuestas en lenguaje natural sobre promociones
- Recomendaciones personalizadas basadas en consultas anteriores
- Historial de conversaciones por empleado

### Ô£à Seguridad y Escalabilidad
- **Autenticaci├│n JWT exclusiva para empleados**
- **Sistema de roles y permisos**
- **Conversaci├│n continua entre mensajes**
- Escalabilidad para m├║ltiples empleados

## ­ƒøá´©Å Tecnolog├¡as Utilizadas

### Backend
- **FastAPI**: Framework web moderno y r├ípido
- **SQLAlchemy**: ORM para gesti├│n de base de datos
- **JWT**: Autenticaci├│n segura para empleados
- **Pydantic**: Validaci├│n de datos

### IA y Machine Learning
- **Ollama**: Modelo local Mistral-7B como principal
- **HuggingFace**: Fallback para consultas SQL
- **Sentence Transformers**: Embeddings para RAG
- **FAISS**: B├║squeda vectorial eficiente

### Base de Datos
- **SQL Server**: Base de datos principal
- **SQLite**: Base de datos local para desarrollo
- **ChromaDB**: Vector store para embeddings

### Optimizaci├│n
- **Cuantizaci├│n de 4 bits**: Optimizaci├│n de memoria
- **Cach├® inteligente**: TTL para respuestas
- **M├®tricas de rendimiento**: Monitoreo en tiempo real

## ­ƒôª Instalaci├│n

### Prerrequisitos
- Python 3.8+
- SQL Server (producci├│n) o SQLite (desarrollo)
- Ollama con modelo Mistral-7B instalado

### Configuraci├│n Inicial

1. **Clonar el repositorio**
```bash
git clone <repository-url>
cd tienda-abastos-chatbot
```

2. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

3. **Configurar variables de entorno**
```bash
# Crear archivo .env
cp .env.example .env

# Configurar variables para empleados
EMPLOYEE_ONLY_SYSTEM=True
ALLOW_ANONYMOUS_ACCESS=False
DEFAULT_EMPLOYEE_ROLE=empleado
ADMIN_EMAILS=admin@tienda.com
OWNER_EMAILS=due├▒o@tienda.com
```

4. **Inicializar base de datos**
```bash
python -m app.database.init_db
```

5. **Crear usuario administrador inicial**
```bash
# El primer usuario debe ser creado directamente en la base de datos
# o mediante script de inicializaci├│n
```

## ­ƒöº Configuraci├│n

### Variables de Entorno Principales

```env
# Sistema exclusivo para empleados
EMPLOYEE_ONLY_SYSTEM=True
ALLOW_ANONYMOUS_ACCESS=False
DEFAULT_EMPLOYEE_ROLE=empleado

# Autenticaci├│n de empleados
JWT_SECRET=your_secure_secret_key
JWT_EXPIRATION_MINUTES=480  # 8 horas
EMPLOYEE_SESSION_TIMEOUT=480

# Base de datos
USE_SQL_SERVER=True
DB_SERVER=localhost
DB_NAME=vmm
DB_USER=sa
DB_PASSWORD=Admin24

# Modelos de IA
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral
OLLAMA_HOST=http://localhost:11434

# Optimizaci├│n
ENABLE_QUANTIZATION=True
QUANTIZATION_BITS=4
MEMORY_OPTIMIZATION=True
```

## ­ƒÜÇ Uso

### Iniciar el Servidor
```bash
python main.py
```

### Acceso al Sistema
1. **Navegar a**: `http://localhost:8000`
2. **Iniciar sesi├│n** con credenciales de empleado
3. **Usar el chatbot** para consultas internas

### Endpoints Principales (Solo Empleados)

#### Autenticaci├│n
- `POST /api/auth/login` - Iniciar sesi├│n de empleado
- `POST /api/auth/registrar` - Registrar nuevo empleado (solo admin)
- `GET /api/auth/perfil` - Obtener perfil de empleado

#### Chatbot (Solo Empleados)
- `POST /api/chatbot/preguntar` - Consultar al chatbot
- `GET /api/chatbot/historial` - Ver historial de conversaciones
- `GET /api/chatbot/estadisticas` - Estad├¡sticas (solo admin)

#### Sincronizaci├│n (Solo Administradores)
- `GET /api/sync/status` - Estado de sincronizaci├│n
- `POST /api/sync/sync-now` - Sincronizaci├│n manual
- `GET /api/sync/logs` - Logs de sincronizaci├│n

## ­ƒöÆ Seguridad

### Autenticaci├│n de Empleados
- **JWT tokens** con expiraci├│n configurable
- **Roles espec├¡ficos**: due├▒o, administrador, empleado
- **Sesiones seguras** con timeout autom├ítico
- **Contrase├▒as fuertes** requeridas

### Acceso Restringido
- **Solo empleados registrados** pueden acceder
- **No hay acceso p├║blico** o an├│nimo
- **Verificaci├│n de roles** en cada endpoint
- **Logs de auditor├¡a** para todas las operaciones

## ­ƒôè Monitoreo y M├®tricas

### M├®tricas de Rendimiento
- Tiempo de respuesta objetivo: 1.73 segundos
- M├®tricas de cach├® y optimizaci├│n
- Monitoreo de uso por empleado

### Evaluaci├│n de Calidad
- Sistema G-Eval integrado
- M├®tricas de satisfacci├│n
- Evaluaci├│n autom├ítica de respuestas

## ­ƒøá´©Å Desarrollo

### Estructura del Proyecto
```
tienda-abastos-chatbot/
Ôö£ÔöÇÔöÇ app/
Ôöé   Ôö£ÔöÇÔöÇ api/           # Endpoints de API
Ôöé   Ôö£ÔöÇÔöÇ config/        # Configuraciones
Ôöé   Ôö£ÔöÇÔöÇ database/      # Base de datos
Ôöé   Ôö£ÔöÇÔöÇ llm/          # Modelos de lenguaje
Ôöé   Ôö£ÔöÇÔöÇ rag/          # Sistema RAG
Ôöé   Ôö£ÔöÇÔöÇ security/     # Autenticaci├│n y seguridad
Ôöé   ÔööÔöÇÔöÇ utils/        # Utilidades
Ôö£ÔöÇÔöÇ frontend/         # Interfaz web
Ôö£ÔöÇÔöÇ data/            # Datos y ├¡ndices
Ôö£ÔöÇÔöÇ logs/            # Logs del sistema
ÔööÔöÇÔöÇ tests/           # Pruebas
```

### Comandos de Desarrollo
```bash
# Ejecutar pruebas
pytest tests/

# Verificar salud del sistema
curl http://localhost:8000/health

# Verificar conectividad con Ollama
curl http://localhost:8000/health/llm
```

## ­ƒôØ Notas Importantes

### ÔÜá´©Å Sistema Exclusivo
- **NO es un chatbot p├║blico** para clientes
- **Solo empleados autorizados** pueden acceder
- **Configurado para operaciones internas** de la tienda

### ­ƒöÉ Seguridad
- **Cambiar JWT_SECRET** en producci├│n
- **Configurar emails de administradores** correctamente
- **Revisar logs** regularmente
- **Actualizar contrase├▒as** peri├│dicamente

### ­ƒÜÇ Producci├│n
- **Usar HTTPS** en producci├│n
- **Configurar firewall** apropiadamente
- **Monitorear uso** de recursos
- **Hacer backups** regulares de la base de datos

## ­ƒô× Soporte

Para soporte t├®cnico o preguntas sobre el sistema exclusivo de empleados, contactar al equipo de desarrollo interno.

---

**ÔÜá´©Å IMPORTANTE**: Este sistema est├í dise├▒ado exclusivamente para el uso interno de empleados de la tienda. No est├í destinado para acceso p├║blico o atenci├│n al cliente externo.


