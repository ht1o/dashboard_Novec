# api/utils/rag.py  — NOUVEAU FICHIER
from typing import Optional

# Convention : toute la DB stocke en FRANÇAIS (ROUGE/AMBRE/VERT)
# normalize_rag absorbe les valeurs anglaises qui pourraient exister
RAG_NORMALIZE = {
    "ROUGE":  "ROUGE",
    "AMBRE":  "AMBRE",
    "VERT":   "VERT",
    "RED":    "ROUGE",
    "AMBER":  "AMBRE",
    "GREEN":  "VERT",
}

def normalize_rag(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return RAG_NORMALIZE.get(str(value).upper().strip(), value)