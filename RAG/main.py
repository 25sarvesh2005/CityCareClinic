import os

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_pdfmuse import PdfmuseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
MONGO_URL = os.environ.get("MONGO_URL")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "cliniccare_rag")
MONGODB_COLLECTION = os.environ.get("MONGODB_COLLECTION", "chunks")
ATLAS_VECTOR_SEARCH_INDEX_NAME = os.environ.get(
    "ATLAS_VECTOR_SEARCH_INDEX_NAME", "vector_index"
)
ATLAS_VECTOR_SEARCH_INDEX_TIMEOUT = int(
    os.environ.get("ATLAS_VECTOR_SEARCH_INDEX_TIMEOUT", "120")
)

if not GOOGLE_API_KEY:
    raise RuntimeError("Please set GOOGLE_API_KEY in the .env file.")
if not MONGO_URL:
    raise RuntimeError("Please set MONGO_URL in the .env file.")


docs = PdfmuseLoader("CityCare-Clinic-Patient-Handbook.pdf", mode="elements").load()

print(f"Loaded {len(docs)} document chunks")
print(docs[0])

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
all_splits = text_splitter.split_documents(docs)
print(f"Split documentation into {len(all_splits)} chunks.")

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001", api_key=GOOGLE_API_KEY
)


vector_store = MongoDBAtlasVectorSearch.from_connection_string(
    connection_string=MONGO_URL,
    namespace=f"{MONGODB_DATABASE}.{MONGODB_COLLECTION}",
    embedding=embeddings,
    index_name=ATLAS_VECTOR_SEARCH_INDEX_NAME,
    relevance_score_fn="cosine",
    auto_create_index=True,
    auto_index_timeout=ATLAS_VECTOR_SEARCH_INDEX_TIMEOUT,
)

inserted_ids = vector_store.add_documents(all_splits)
print(f"Indexed {len(inserted_ids)} chunks in MongoDB Atlas Vector Search.")
