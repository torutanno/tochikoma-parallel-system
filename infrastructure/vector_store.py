"""
infrastructure/vector_store.py
Chroma DB接続と長期記憶の管理
"""
import os
from dotenv import load_dotenv
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

CHROMA_PERSIST_DIR = "chroma_memory"

embeddings = VertexAIEmbeddings(
    model_name="gemini-embedding-2-preview",
    project=os.getenv("PROJECT_ID"),
    location=os.getenv("LOCATION")
)

vector_store = Chroma(
    collection_name="tachikoma_logs",
    embedding_function=embeddings,
    persist_directory=CHROMA_PERSIST_DIR
)
