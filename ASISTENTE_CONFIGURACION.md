# 🤖 Guía de Configuración: Asistente de Consultas en Bases de Datos y PDFs

Esta guía explica paso a paso cómo configurar un **asistente inteligente** (basado en RAG –
*Retrieval-Augmented Generation*) capaz de responder preguntas sobre:

- 📄 **Documentos PDF** (hojas de vida, informes, manuales, etc.)
- 🗄️ **Bases de datos** (PostgreSQL, MySQL, SQLite, SQL Server)

---

## 📋 Requisitos previos

| Requisito | Versión mínima |
|-----------|---------------|
| Python | 3.9+ |
| pip | 23+ |
| Una clave de API de OpenAI (u otro LLM) | — |
| Acceso a tu base de datos | — |

> **Alternativa sin clave de pago**: puedes usar [Ollama](https://ollama.com/) con modelos
> locales gratuitos como `llama3`, `mistral` o `phi3`. Ver sección al final.

---

## 🗂️ Estructura del proyecto

```
asistente/
├── asistente_consultas.py   # Script principal del asistente
├── requirements.txt         # Dependencias Python
├── .env                     # Variables de entorno (API keys, cadena de conexión)
├── docs/                    # Carpeta donde se guardan los PDFs a indexar
│   └── mi_documento.pdf
└── ASISTENTE_CONFIGURACION.md  # Este archivo
```

---

## ⚙️ Paso 1 — Instalar dependencias

```bash
# Crea y activa un entorno virtual
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# Instala todas las dependencias
pip install -r requirements.txt
```

---

## 🔑 Paso 2 — Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto con el siguiente contenido
(reemplaza los valores según tu configuración):

```dotenv
# === LLM ===
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# === Base de datos ===
# Ejemplos de cadenas de conexión:
# PostgreSQL:   postgresql+psycopg2://usuario:contraseña@host:5432/nombre_bd
# MySQL:        mysql+pymysql://usuario:contraseña@host:3306/nombre_bd
# SQLite:       sqlite:///ruta/a/mi_base.db
# SQL Server:   mssql+pyodbc://usuario:contraseña@servidor/nombre_bd?driver=ODBC+Driver+17+for+SQL+Server
DATABASE_URL=postgresql+psycopg2://usuario:contraseña@localhost:5432/mi_base

# === PDFs ===
PDF_FOLDER=./docs
```

> ⚠️ **Nunca subas el archivo `.env` a GitHub.** Agrega `.env` a tu `.gitignore`.

---

## 📄 Paso 3 — Preparar los PDFs

Copia todos los archivos PDF que quieres consultar dentro de la carpeta `docs/`:

```bash
mkdir -p docs
cp /ruta/a/mi_documento.pdf docs/
```

El asistente los indexará automáticamente al iniciar.

---

## 🗄️ Paso 4 — Preparar la base de datos

No necesitas modificar tu base de datos. El asistente lee el esquema (tablas y columnas)
y genera consultas SQL de forma automática. Solo asegúrate de que:

1. El usuario de la base de datos tenga permiso de **SELECT**.
2. La cadena de conexión en `.env` sea correcta.
3. La base de datos sea accesible desde la máquina donde corre el script.

---

## 🚀 Paso 5 — Ejecutar el asistente

```bash
python asistente_consultas.py
```

Verás un menú como este:

```
============================================================
   ASISTENTE DE CONSULTAS - BD y PDF
============================================================
Escribe tu pregunta (o 'salir' para terminar):
> ¿Cuántos registros hay en la tabla clientes?
> ¿Qué dice el PDF sobre los horizontes de suelo?
> salir
```

---

## 🧩 Arquitectura del asistente

```
Usuario
   │
   ▼
Pregunta en lenguaje natural
   │
   ├─► Módulo PDF (LangChain + FAISS)
   │      • Carga y divide los PDFs en fragmentos
   │      • Crea embeddings y los guarda en un índice vectorial
   │      • Recupera los fragmentos más relevantes
   │
   └─► Módulo BD (LangChain SQL Agent)
          • Lee el esquema de la base de datos
          • Genera la consulta SQL adecuada
          • Ejecuta y devuelve el resultado
   │
   ▼
LLM (OpenAI / Ollama)
   │
   ▼
Respuesta en lenguaje natural
```

---

## 🛠️ Personalización avanzada

### Cambiar el modelo de LLM

En `asistente_consultas.py`, ajusta la variable `MODEL_NAME`:

```python
# OpenAI
MODEL_NAME = "gpt-4o-mini"   # económico y rápido
MODEL_NAME = "gpt-4o"        # más potente

# Si usas Ollama (modelo local, gratuito):
# Instala Ollama: https://ollama.com/
# Descarga el modelo: ollama pull llama3
MODEL_NAME = "llama3"        # ver sección Ollama más abajo
```

### Ajustar el tamaño de los fragmentos de PDF

```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,    # caracteres por fragmento (aumenta para más contexto)
    chunk_overlap=200,  # solapamiento entre fragmentos
)
```

### Limitar las tablas que puede consultar el agente SQL

```python
sql_agent = create_sql_agent(
    llm=llm,
    db=db,
    include_tables=["clientes", "pedidos", "productos"],  # solo estas tablas
    verbose=True,
)
```

---

## 🦙 Opción gratuita con Ollama (sin clave de pago)

1. Instala Ollama desde [https://ollama.com/](https://ollama.com/)
2. Descarga un modelo:
   ```bash
   ollama pull llama3          # modelo general
   ollama pull nomic-embed-text  # modelo de embeddings
   ```
3. En `asistente_consultas.py`, cambia el proveedor:
   ```python
   USE_OLLAMA = True   # Cambia esta variable a True
   ```
4. No necesitas `OPENAI_API_KEY` en el `.env`.

---

## ❓ Preguntas frecuentes

**¿Qué pasa si el PDF tiene imágenes o texto escaneado?**  
El asistente extrae texto digital. Si el PDF es una imagen escaneada, necesitas aplicar
OCR primero. Puedes usar [`pytesseract`](https://github.com/madmaze/pytesseract) o
[`ocrmypdf`](https://github.com/ocrmypdf/OCRmyPDF).

**¿Puedo conectar varias bases de datos a la vez?**  
Sí. Crea múltiples instancias de `SQLDatabase` y un agente por cada una, o usa
un agente multi-herramienta con `AgentType.OPENAI_FUNCTIONS`.

**¿El asistente modifica datos en mi base de datos?**  
No, solo ejecuta consultas `SELECT`. Si quieres restringirlo explícitamente, crea
un usuario de BD con permisos solo de lectura.

**¿Puedo desplegarlo como API o chatbot web?**  
Sí, puedes envolver el asistente con [FastAPI](https://fastapi.tiangolo.com/) o
integrarlo con [Streamlit](https://streamlit.io/) para tener una interfaz web sencilla.

---

## 📚 Recursos adicionales

- [LangChain Docs](https://python.langchain.com/)
- [LangChain SQL Agent](https://python.langchain.com/docs/use_cases/sql/)
- [LangChain PDF / Document Loaders](https://python.langchain.com/docs/modules/data_connection/document_loaders/)
- [FAISS – Facebook AI Similarity Search](https://github.com/facebookresearch/faiss)
- [Ollama – LLMs locales](https://ollama.com/)

---

<p align="center">
  Desarrollado por <strong>Carlos Eduardo Gómez Rico</strong> · 
  <a href="mailto:ing.carlosgomez0219@gmail.com">ing.carlosgomez0219@gmail.com</a>
</p>
