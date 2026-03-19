"""
asistente_consultas.py
======================
Asistente inteligente para consultar información en:
  - Bases de datos relacionales (PostgreSQL, MySQL, SQLite, SQL Server)
  - Documentos PDF

Uso:
    python asistente_consultas.py

Requisitos:
    pip install -r requirements.txt
    Crear un archivo .env con OPENAI_API_KEY y DATABASE_URL (ver ASISTENTE_CONFIGURACION.md)
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Carga de variables de entorno desde .env
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("[AVISO] python-dotenv no está instalado. Las variables de entorno deben "
          "configurarse manualmente.")

# ---------------------------------------------------------------------------
# Configuración principal — ajusta estos valores según tu caso de uso
# ---------------------------------------------------------------------------

# Nombre del modelo LLM a usar (OpenAI o Ollama)
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")

# Carpeta donde se encuentran los PDFs a indexar
PDF_FOLDER: str = os.getenv("PDF_FOLDER", "./docs")

# Cadena de conexión a la base de datos (SQLAlchemy)
# Ejemplos:
#   PostgreSQL:  postgresql+psycopg2://user:pass@host:5432/dbname
#   MySQL:       mysql+pymysql://user:pass@host:3306/dbname
#   SQLite:      sqlite:///./mi_base.db
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Pon USE_OLLAMA = True para usar modelos locales gratuitos con Ollama
USE_OLLAMA: bool = os.getenv("USE_OLLAMA", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Importaciones de LangChain y utilidades
# ---------------------------------------------------------------------------
try:
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_community.vectorstores import FAISS
    from langchain_community.utilities import SQLDatabase
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.chains import RetrievalQA
    from langchain_community.agent_toolkits import create_sql_agent
    from langchain.agents import AgentType
    from langchain.tools import Tool
    from langchain.agents import initialize_agent
except ImportError as e:
    print(f"[ERROR] Faltan dependencias de LangChain: {e}")
    print("Ejecuta: pip install -r requirements.txt")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Selección del modelo LLM y embeddings
# ---------------------------------------------------------------------------

def _crear_llm():
    """Crea y devuelve el LLM configurado (OpenAI o Ollama)."""
    if USE_OLLAMA:
        try:
            from langchain_community.llms import Ollama
            print(f"[INFO] Usando Ollama con modelo '{MODEL_NAME}'")
            return Ollama(model=MODEL_NAME, temperature=0)
        except ImportError:
            print("[ERROR] langchain-community no está instalado.")
            sys.exit(1)
    else:
        try:
            from langchain_openai import ChatOpenAI
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                print("[ERROR] OPENAI_API_KEY no está configurada. "
                      "Agrega la clave en el archivo .env o como variable de entorno.")
                sys.exit(1)
            print(f"[INFO] Usando OpenAI con modelo '{MODEL_NAME}'")
            return ChatOpenAI(model=MODEL_NAME, temperature=0, openai_api_key=api_key)
        except ImportError:
            print("[ERROR] langchain-openai no está instalado.")
            sys.exit(1)


def _crear_embeddings():
    """Crea y devuelve el modelo de embeddings configurado."""
    if USE_OLLAMA:
        try:
            from langchain_community.embeddings import OllamaEmbeddings
            return OllamaEmbeddings(model="nomic-embed-text")
        except ImportError:
            print("[ERROR] langchain-community no está instalado.")
            sys.exit(1)
    else:
        try:
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY", ""))
        except ImportError:
            print("[ERROR] langchain-openai no está instalado.")
            sys.exit(1)

# ---------------------------------------------------------------------------
# Módulo PDF: carga, indexación y recuperación
# ---------------------------------------------------------------------------

def cargar_pdfs(carpeta: str):
    """Carga todos los PDFs de una carpeta y devuelve los documentos divididos."""
    ruta = Path(carpeta)
    if not ruta.exists():
        print(f"[AVISO] La carpeta de PDFs '{carpeta}' no existe. "
              "El módulo PDF no estará disponible.")
        return []

    archivos_pdf = list(ruta.glob("*.pdf"))
    if not archivos_pdf:
        print(f"[AVISO] No se encontraron PDFs en '{carpeta}'. "
              "El módulo PDF no estará disponible.")
        return []

    documentos = []
    for pdf_path in archivos_pdf:
        print(f"[INFO] Cargando PDF: {pdf_path.name}")
        loader = PyPDFLoader(str(pdf_path))
        documentos.extend(loader.load())

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    fragmentos = splitter.split_documents(documentos)
    print(f"[INFO] PDFs indexados: {len(archivos_pdf)} archivos → {len(fragmentos)} fragmentos")
    return fragmentos


def crear_cadena_pdf(fragmentos: list, embeddings, llm) -> RetrievalQA | None:
    """Crea una cadena de recuperación y respuesta sobre los PDFs."""
    if not fragmentos:
        return None

    vectorstore = FAISS.from_documents(fragmentos, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    cadena = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=False,
    )
    return cadena

# ---------------------------------------------------------------------------
# Módulo Base de datos: agente SQL
# ---------------------------------------------------------------------------

def crear_agente_sql(database_url: str, llm):
    """Crea un agente SQL capaz de consultar la base de datos."""
    if not database_url:
        print("[AVISO] DATABASE_URL no está configurada. "
              "El módulo de base de datos no estará disponible.")
        return None

    try:
        db = SQLDatabase.from_uri(database_url)
        agente = create_sql_agent(
            llm=llm,
            db=db,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=False,
            handle_parsing_errors=True,
        )
        print(f"[INFO] Conectado a la base de datos: {database_url.split('@')[-1]}")
        return agente
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a la base de datos: {e}")
        return None

# ---------------------------------------------------------------------------
# Agente unificado: combina PDF y BD en un solo asistente
# ---------------------------------------------------------------------------

def crear_agente_unificado(cadena_pdf, agente_sql, llm):
    """
    Crea un agente que decide automáticamente si la pregunta es sobre
    los PDFs o sobre la base de datos.
    """
    herramientas = []

    if cadena_pdf:
        herramientas.append(
            Tool(
                name="ConsultarPDF",
                func=lambda q: cadena_pdf.invoke({"query": q})["result"],
                description=(
                    "Útil para responder preguntas sobre el contenido de los documentos PDF "
                    "disponibles. Úsala cuando la pregunta sea sobre información de archivos PDF."
                ),
            )
        )

    if agente_sql:
        herramientas.append(
            Tool(
                name="ConsultarBaseDeDatos",
                func=lambda q: agente_sql.invoke({"input": q})["output"],
                description=(
                    "Útil para responder preguntas sobre datos almacenados en la base de datos "
                    "relacional. Úsala cuando la pregunta involucre tablas, registros, conteos, "
                    "filtros o estadísticas de la base de datos."
                ),
            )
        )

    if not herramientas:
        return None

    agente = initialize_agent(
        tools=herramientas,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=6,
    )
    return agente

# ---------------------------------------------------------------------------
# Bucle principal de conversación
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("   ASISTENTE DE CONSULTAS - BD y PDF")
    print("=" * 60)

    # Inicializar componentes
    llm = _crear_llm()
    embeddings = _crear_embeddings()

    fragmentos_pdf = cargar_pdfs(PDF_FOLDER)
    cadena_pdf = crear_cadena_pdf(fragmentos_pdf, embeddings, llm)

    agente_sql = crear_agente_sql(DATABASE_URL, llm)

    if not cadena_pdf and not agente_sql:
        print(
            "\n[ERROR] Ningún módulo está disponible.\n"
            "  • Para PDFs: crea la carpeta 'docs/' y copia tus archivos PDF allí.\n"
            "  • Para BD:   configura DATABASE_URL en el archivo .env\n"
        )
        sys.exit(1)

    agente = crear_agente_unificado(cadena_pdf, agente_sql, llm)

    modulos_activos = []
    if cadena_pdf:
        modulos_activos.append("PDF ✅")
    if agente_sql:
        modulos_activos.append("Base de Datos ✅")
    print(f"\nMódulos activos: {' | '.join(modulos_activos)}")
    print("\nEscribe tu pregunta (o 'salir' para terminar):\n")

    while True:
        try:
            pregunta = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[INFO] Hasta luego.")
            break

        if not pregunta:
            continue

        if pregunta.lower() in {"salir", "exit", "quit"}:
            print("[INFO] Hasta luego.")
            break

        try:
            if agente:
                respuesta = agente.invoke({"input": pregunta})["output"]
            elif cadena_pdf:
                respuesta = cadena_pdf.invoke({"query": pregunta})["result"]
            else:
                respuesta = agente_sql.invoke({"input": pregunta})["output"]

            print(f"\n🤖 {respuesta}\n")
        except Exception as e:
            print(f"\n[ERROR] No se pudo procesar la pregunta: {e}\n")


if __name__ == "__main__":
    main()
