import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TMDB_BASE = "https://api.themoviedb.org/3"


def get_tmdb_key() -> str:
    key = os.getenv("TMDB_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="TMDB_API_KEY not set in environment")
    return key


def tmdb_get(path: str, params: Optional[dict] = None):
    key = get_tmdb_key()
    params = params or {}
    params["api_key"] = key
    url = f"{TMDB_BASE}{path}"
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"TMDB request failed: {e}")


def map_tmdb_item(item: dict) -> dict:
    title = item.get("title") or item.get("name") or "Untitled"
    date = item.get("release_date") or item.get("first_air_date") or ""
    year = int(date.split("-")[0]) if date else None
    poster_path = item.get("poster_path")
    return {
        "id": item.get("id"),
        "title": title,
        "year": year,
        "rating": item.get("vote_average"),
        "media_type": item.get("media_type"),
        "poster": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None,
        "backdrop": f"https://image.tmdb.org/t/p/w780{item.get('backdrop_path')}" if item.get("backdrop_path") else None,
        "overview": item.get("overview"),
        "original_language": item.get("original_language"),
    }


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    response["tmdb_api_key"] = "✅ Set" if os.getenv("TMDB_API_KEY") else "❌ Not Set"
    
    return response


# TMDB proxy endpoints
@app.get("/api/tmdb/trending")
def tmdb_trending(
    media_type: str = Query("movie", pattern="^(all|movie|tv)$"),
    time_window: str = Query("day", pattern="^(day|week)$"),
    page: int = Query(1, ge=1, le=1000),
):
    data = tmdb_get(f"/trending/{media_type}/{time_window}", params={"page": page})
    results = [map_tmdb_item(i) for i in data.get("results", [])]
    return {"page": data.get("page", 1), "total_pages": data.get("total_pages", 1), "results": results}


@app.get("/api/tmdb/search")
def tmdb_search(query: str, page: int = Query(1, ge=1, le=100), type: str = Query("multi")):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    endpoint = "/search/multi" if type == "multi" else f"/search/{type}"
    data = tmdb_get(endpoint, params={"query": query, "page": page, "include_adult": False})
    results = [map_tmdb_item(i) for i in data.get("results", [])]
    return {"page": data.get("page", 1), "total_pages": data.get("total_pages", 1), "results": results}


@app.get("/api/tmdb/movie/{movie_id}")
def tmdb_movie_details(movie_id: int):
    data = tmdb_get(f"/movie/{movie_id}", params={"append_to_response": "videos,credits"})
    details = map_tmdb_item(data)
    details.update({
        "genres": data.get("genres", []),
        "runtime": data.get("runtime"),
        "videos": data.get("videos", {}).get("results", []),
        "credits": data.get("credits", {}),
        "homepage": data.get("homepage"),
        "status": data.get("status"),
        "release_date": data.get("release_date"),
    })
    return details


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
