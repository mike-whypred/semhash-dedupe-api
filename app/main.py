from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import io, pandas as pd
from semhash import SemHash

###############################################################################
# FastAPI setup + CORS for your production site
###############################################################################
app = FastAPI(title="SemHash CSV Deduper (JSON)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aibizsearch.info", "https://www.aibizsearch.info"],   # add localhost origins when testing
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

###############################################################################
# Constants
###############################################################################
MAX_BYTES         = 32 * 1024 * 1024   # 32 MiB Cloud Run direct-body limit
DEFAULT_THRESHOLD = 0.9

###############################################################################
# Helper function
###############################################################################
def dedupe_df(df: pd.DataFrame, threshold: float, skip_cols: list[str]) -> pd.DataFrame:
    hash_cols = [c for c in df.columns if c not in skip_cols]
    if not hash_cols:
        raise ValueError("All columns skipped; nothing left to hash.")

    cleaned = (
        SemHash
        .from_records(df.to_dict("records"), columns=hash_cols)
        .self_deduplicate(threshold=threshold)
        .deduplicated
    )
    return pd.DataFrame(cleaned)

###############################################################################
# Endpoint (raw CSV body, returns JSON)
###############################################################################
@app.post("/dedupe_csv")
async def dedupe_csv(
    request: Request,
    threshold: float = Query(DEFAULT_THRESHOLD, ge=0.0, le=1.0),
    skip_columns: str = Query(""),
):
    # 1  Read raw body
    raw = await request.body()
    if len(raw) == 0:
        raise HTTPException(400, "Request body is empty")
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "File exceeds 32 MiB limit")

    # 2  Parse CSV
    try:
        df_in = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(400, f"CSV parse error: {exc}")

    # 3  Deduplicate
    skip_list = [c.strip() for c in skip_columns.split(",") if c.strip()]
    try:
        df_out = dedupe_df(df_in, threshold, skip_list)
    except ValueError as ve:
        raise HTTPException(400, str(ve))

    # 4  Return JSON
    return JSONResponse(content=df_out.to_dict(orient="records"))