from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.ai_summary import (
    SummaryConfigurationError,
    SummaryProviderError,
    summarize_file,
)
from app.scanner import scan_repo

app = FastAPI(
    title="Repository Structure Analysis API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScanRequest(BaseModel):
    repo_path: str = Field(min_length=1)


class SummaryRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    file_id: str = Field(min_length=1)
    provider: str = "auto"


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Repository analysis backend is running",
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


@app.post("/api/summarize")
def summarize_repository_file(request: SummaryRequest):
    try:
        return summarize_file(
            repo_path=request.repo_path,
            file_id=request.file_id,
            provider=request.provider,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except (NotADirectoryError, ValueError, SummaryConfigurationError) as error:
        raise HTTPException(status_code=400, detail=str(error))
    except SummaryProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Summary failed: {str(error)}",
        )
