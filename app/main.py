from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd, io
from semhash import SemHash

app = FastAPI(title="SemHash CSV Deduper (JSON output)")

# ── CORS ────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = ["https://aibizsearch.info", "https://www.aibizsearch.info"]        
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)
# ────────────────────────────────────────────────────────────────────────

# ── service-wide defaults ────────────────────────────────────────────────
MAX_DIRECT_BYTES   = 32 * 1024 * 1024   # 32 MiB upload limit
DEFAULT_THRESHOLD  = 0.9                # fallback similarity cut-off
# ─────────────────────────────────────────────────────────────────────────


def dedupe_df(df: pd.DataFrame, threshold: float, skip_cols: list[str]) -> pd.DataFrame:
    """
    Deduplicate `df` using SemHash, ignoring columns in `skip_cols`.
    Returns a new DataFrame containing only the unique rows.
    """
    hash_cols = [c for c in df.columns if c not in skip_cols]
    if not hash_cols:
        raise ValueError("All columns were skipped — nothing left to hash.")

    records = df.to_dict("records")
    sh      = SemHash.from_records(records, columns=hash_cols)
    cleaned = sh.self_deduplicate(threshold=threshold).deduplicated
    return pd.DataFrame(cleaned)


@app.post("/dedupe_csv")
async def dedupe_csv(
    file: UploadFile = File(...),
    threshold: float = Query(
        DEFAULT_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Cosine-similarity cut-off (0 = keep everything, 1 = only perfect uniques).",
    ),
    skip_columns: str = Query(
        "",
        description="Comma-separated list of columns to *exclude* from hashing "
                    "(e.g. 'id,created_at'). These columns remain in the output.",
    ),
):
    # 1  ── Validate upload size & type
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Upload must be a .csv file.")

    raw = await file.read()
    if len(raw) > MAX_DIRECT_BYTES:
        raise HTTPException(
            413,
            "File larger than 32 MiB — upload to GCS & call the large-file endpoint.",
        )

    # 2  ── Load CSV into DataFrame
    try:
        df_in = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(400, f"Could not parse CSV: {exc}")

    # 3  ── Deduplicate
    skip_list = [c.strip() for c in skip_columns.split(",") if c.strip()]
    try:
        df_out = dedupe_df(df_in, threshold, skip_list)
    except ValueError as err:
        raise HTTPException(400, str(err))

    # 4  ── Return JSON array of rows
    return JSONResponse(content=df_out.to_dict(orient="records"))
