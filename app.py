import os
import unicodedata
import re
import requests
from typing import Dict, List, Tuple, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# URL pública del JSON en GitHub
GIST_URL = (
    "https://raw.githubusercontent.com/sebastianmiras/ocnos-googlecloud/main/articulo.json"
)

# Modelos de petición
class MetadataRequest(BaseModel):
    article_query: str

class SectionRequest(BaseModel):
    article_query: str
    section: str

app = FastAPI(
    title="OCNOS Article Service",
    description="Servicio para custom GPT: obtiene metadatos y secciones de artículos OCNOS",
    version="1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).lower()

def normalize_text(s: str) -> str:
    """Quita tildes, pasa a minúsculas y reemplaza no alfanuméricos por espacios."""
    no_acc = strip_accents(s)
    cleaned = re.sub(r'[^a-z0-9]+', ' ', no_acc)
    return cleaned.strip()

def load_articles_from_gist() -> Dict[str, Dict]:
    try:
        resp = requests.get(GIST_URL)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cargar JSON: {e}")

    if isinstance(raw, dict) and "id" in raw and "sections" in raw:
        db = {raw["id"]: raw}
    elif isinstance(raw, list):
        db = {art.get("id"): art for art in raw}
    else:
        db = {}

    for slug, art in db.items():
        norm_map: Dict[str, List[str]] = {}
        for sec in art.get("sections", []):
            key = strip_accents(sec.get("section", ""))
            norm_map[key] = sec.get("paragraphs", [])
        art["_sections_map"] = norm_map

    return db

def find_article(query: str, db: Dict[str, Dict]) -> Tuple[Optional[str], Optional[Dict]]:
    q = normalize_text(query)
    for slug, art in db.items():
        if q in normalize_text(slug) or q in normalize_text(art.get("title", "")):
            return slug, art
    return None, None

@app.get("/list_articles", summary="Listar títulos de artículos disponibles")
def list_articles():
    db = load_articles_from_gist()
    return [{"id": slug, "title": art.get("title")} for slug, art in db.items()]

@app.post("/get_metadata", summary="Obtener datos bibliográficos del artículo")
def get_metadata(req: MetadataRequest):
    db = load_articles_from_gist()
    slug, art = find_article(req.article_query, db)
    if art is None:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    return {
        "doi": art.get("doi"),
        "title": art.get("title"),
        "authors": art.get("authors"),
        "journal": art.get("journal"),
        "date": art.get("date"),
        "keywords": art.get("keywords"),
    }

@app.post("/get_section", summary="Recuperar párrafos de una sección")
def get_section(req: SectionRequest):
    db = load_articles_from_gist()
    slug, art = find_article(req.article_query, db)
    if art is None:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")

    query_sec = strip_accents(req.section)

    if query_sec in ("abstract", "resumen"):
        abstract = art.get("abstract")
        if not abstract:
            raise HTTPException(status_code=404, detail="Abstract no disponible")
        return {"paragraphs": [abstract]}

    for sec_key, paras in art.get("_sections_map", {}).items():
        if query_sec in sec_key:
            return {"paragraphs": paras}

    raise HTTPException(
        status_code=404,
        detail=f"Sección '{req.section}' no encontrada"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
