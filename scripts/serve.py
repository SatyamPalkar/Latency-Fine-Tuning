"""Start one model-serving process using a local or platform-provided port."""
import os
from pathlib import Path
import sys

import uvicorn
from dotenv import load_dotenv

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
load_dotenv(root / ".env")

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app", host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")), workers=1,
        limit_concurrency=16, timeout_keep_alive=5,
    )
