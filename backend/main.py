from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.scanner import scan_repo
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title = "Repo Analysis and visualisation API",
              version = "0.1.0",
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScanRequest(BaseModel):
    repo_path: str


@app.get("/")
def root():
    return {"status": "ok",
            "message": "backend is running",
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/api/scan")
def scan_repository(request: ScanRequest):
    try:
        result = scan_repo(request.repo_path)
        return result

    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))

    except NotADirectoryError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(error)}")
