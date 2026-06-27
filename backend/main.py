from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.scanner import scan_repo

app = FastAPI(title = "Repo Analysis and visualisation API",
              version = "0.1.0",
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
