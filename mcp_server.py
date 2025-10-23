#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import hashlib
from typing import Any, Dict, List, Optional, Tuple

import uvicorn
import requests
try:
    # OpenAI SDK for client-side embeddings
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # lazy optional import

# Allow imports from /mnt/data if you later share business logic there
UPLOAD_DIR = "/mnt/data"
if os.path.isdir(UPLOAD_DIR) and UPLOAD_DIR not in sys.path:
    sys.path.append(UPLOAD_DIR)

# FastMCP
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse

# ==============================================================================
# Helpers
# ==============================================================================
def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in ("1", "true", "yes", "y", "on")

def jlog(event: str, **kwargs):
    payload = {"event": event, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    payload.update(kwargs)
    print(json.dumps(payload, ensure_ascii=False))

def _jdump(obj: Any, limit: int = 2000) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    return s if len(s) <= limit else s[:limit] + "...[truncated]"

def _token_forms(tok: str):
    forms = {
        tok,
        tok.strip(),
        tok.strip('"'),
        tok.strip("'"),
        tok.strip().strip('"').strip("'"),
        f'"{tok}"',
        f"'{tok}'",
    }
    return {t: {"client_id": "client", "scopes": ["tools:call"]} for t in forms if t}

# Client-side text embedding using OpenAI (optional)
from typing import Optional, List  # ensure types available here

def embed_text_with_openai(text: str) -> Optional[List[float]]:
    if not text:
        return None
    if OpenAI is None:
        _log_tool("tool.warn", "openai.embedding_unavailable", error="OpenAI SDK not installed")
        return None
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.embeddings.create(model=OPENAI_EMBED_MODEL, input=text)
        # OpenAI 1.x response structure
        return resp.data[0].embedding  # type: ignore[attr-defined]
    except Exception as e:
        _log_tool("tool.warn", "openai.embedding_failed", error=str(e))
        return None

# ==============================================================================
# Config (Auth + OpenSearch creds)
# ==============================================================================
TOKEN = os.getenv("MCP_TOKEN", "REDACTED")
DISABLE_AUTH = os.getenv("MCP_DISABLE_AUTH", "0") == "1"
LOG_BODY_LIMIT = int(os.getenv("LOG_BODY_LIMIT", "4096"))
LOG_SHOW_TOKENS = os.getenv("LOG_SHOW_TOKENS", "1") == "1"

OS_HOST = os.getenv("OS_HOST", "localhost")
OS_PORT = int(os.getenv("OS_PORT", "9200"))
OS_USER = os.getenv("OS_USER") or os.getenv("OS_USERNAME", "admin")
OS_PASS = os.getenv("OS_PASS") or os.getenv("OS_PASSWORD", "YourStrongP@ssw0rd!")
OS_INSECURE = env_bool("OS_INSECURE", True)
OS_CA_CERT  = os.getenv("OS_CA_CERT")
OS_INDEX    = os.getenv("OS_INDEX", "products_pets_v3")
DISABLE_KNN = os.getenv("DISABLE_KNN", "0") == "1"
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

if OS_INSECURE:
    OS_SCHEME = "http"
    OS_VERIFY: Any = False
else:
    OS_SCHEME = "https"
    OS_VERIFY = OS_CA_CERT if OS_CA_CERT else True

BASE_URL = f"{OS_SCHEME}://{OS_HOST}:{OS_PORT}"

def _auth_tuple() -> Optional[Tuple[str, str]]:
    if OS_USER or OS_PASS:
        return (OS_USER, OS_PASS)
    return None

# ==============================================================================
# OpenSearch helpers
# ==============================================================================
def os_search(body: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BASE_URL}/{OS_INDEX}/_search"
    jlog("os.request", url=url, index=OS_INDEX, query_preview=_jdump(body, 500))
    try:
        resp = requests.post(url, json=body, auth=_auth_tuple(), verify=OS_VERIFY, timeout=30)
        try:
            data = resp.json()
        except Exception:
            data = {"status_code": resp.status_code, "text": resp.text}
        jlog("os.response", status=resp.status_code, took=(data.get("took") if isinstance(data, dict) else None),
             hits_count=(data.get("hits", {}).get("total", {}).get("value") if isinstance(data, dict) else None))
        if resp.status_code >= 300:
            raise RuntimeError(f"OpenSearch error {resp.status_code}: {data}")
        return data
    except Exception as e:
        jlog("os.error", error=str(e), url=url)
        raise RuntimeError(f"OpenSearch connection error: {e}")

def terms_agg(field: str, species: str, size: int = 1000) -> Dict[str, Any]:
    return {
        "size": 0,
        "query": {"term": {"species": species}},
        "aggs": {
            "unique_values": {
                "terms": {"field": field, "size": size, "order": {"_key": "asc"}}
            }
        }
    }

def extract_terms(resp_json: Dict[str, Any]) -> List[str]:
    try:
        buckets = (resp_json.get("aggregations") or {}).get("unique_values", {}).get("buckets", [])
        return [b["key"] for b in buckets]
    except Exception:
        return []

# ==============================================================================
# MCP server + tools
# ==============================================================================
_auth = None if DISABLE_AUTH else StaticTokenVerifier(tokens=_token_forms(TOKEN))
mcp = FastMCP("pet_products_server", auth=_auth)
_knn_available = {"ok": not DISABLE_KNN}  # runtime cache to stop retrying if cluster rejects KNN

def _log_tool(event: str, name: str, **data):
    print(json.dumps({"event": event, "tool": name, **data}, ensure_ascii=False))

def _normalize_species(species: str) -> str:
    s = (species or "").strip().capitalize()
    if s not in ("Dog", "Cat"):
        raise ValueError("species must be 'Dog' or 'Cat'")
    return s

# ==============================================================================
# Existing taxonomy tools
# ==============================================================================
@mcp.tool(name="get_unique_breeds",
    description="Return all unique breeds for a given species ('Dog' or 'Cat') from OpenSearch.")
def get_unique_breeds(species: str = "Dog") -> str:
    t0 = time.time()
    sp = _normalize_species(species)
    body = terms_agg(field="breed", species=sp, size=2000)
    _log_tool("tool.request", "get_unique_breeds", args_preview=_jdump({"species": sp}))
    res = os_search(body)
    breeds = extract_terms(res)
    out = {"species": sp, "breeds": breeds, "count": len(breeds)}
    _log_tool("tool.response", "get_unique_breeds", ms=round((time.time()-t0)*1000, 1),
              result_preview=_jdump(out))
    return json.dumps(out, ensure_ascii=False)

@mcp.tool(name="get_unique_life_stages",
    description="Return all unique life stages for a given species ('Dog' or 'Cat').")
def get_unique_life_stages(species: str = "Dog") -> str:
    t0 = time.time()
    sp = _normalize_species(species)
    body = terms_agg(field="life_stage", species=sp, size=100)
    _log_tool("tool.request", "get_unique_life_stages", args_preview=_jdump({"species": sp}))
    res = os_search(body)
    stages = extract_terms(res)
    out = {"species": sp, "life_stages": stages, "count": len(stages)}
    _log_tool("tool.response", "get_unique_life_stages", ms=round((time.time()-t0)*1000, 1),
              result_preview=_jdump(out))
    return json.dumps(out, ensure_ascii=False)

@mcp.tool(name="get_taxonomy",
    description="Return both unique breeds and life stages for a species ('Dog' or 'Cat').")
def get_taxonomy(species: str = "Dog") -> str:
    t0 = time.time()
    sp = _normalize_species(species)
    _log_tool("tool.request", "get_taxonomy", args_preview=_jdump({"species": sp}))
    res_b = os_search(terms_agg(field="breed", species=sp, size=2000))
    res_l = os_search(terms_agg(field="life_stage", species=sp, size=100))
    breeds = extract_terms(res_b)
    stages = extract_terms(res_l)
    out = {"species": sp, "breeds": breeds, "life_stages": stages}
    _log_tool("tool.response", "get_taxonomy", ms=round((time.time()-t0)*1000, 1),
              result_preview=_jdump(out))
    return json.dumps(out, ensure_ascii=False)

# ==============================================================================
# New Tool: search_products
# ==============================================================================
@mcp.tool(
    name="debug_opensearch_data",
    description="Debug OpenSearch data structure and field mappings."
)
def debug_opensearch_data() -> str:
    t0 = time.time()
    _log_tool("tool.request", "debug_opensearch_data", args_preview="{}")
    
    try:
        # Get total count
        count_url = f"{BASE_URL}/{OS_INDEX}/_count"
        count_resp = requests.get(count_url, auth=_auth_tuple(), verify=OS_VERIFY, timeout=10)
        total_docs = count_resp.json().get("count", 0) if count_resp.status_code == 200 else 0
        
        # Get sample documents
        sample_url = f"{BASE_URL}/{OS_INDEX}/_search"
        sample_body = {"size": 3, "query": {"match_all": {}}}
        sample_resp = requests.post(sample_url, json=sample_body, auth=_auth_tuple(), verify=OS_VERIFY, timeout=10)
        
        sample_docs = []
        if sample_resp.status_code == 200:
            hits = sample_resp.json().get("hits", {}).get("hits", [])
            for hit in hits:
                source = hit.get("_source", {})
                sample_docs.append({
                    "id": hit.get("_id"),
                    "fields": list(source.keys()),
                    "sample_data": {k: v for k, v in source.items() if k in ["title", "species", "brand", "life_stage", "food_type", "price_sale"]}
                })
        
        # Get field mappings
        mapping_url = f"{BASE_URL}/{OS_INDEX}/_mapping"
        mapping_resp = requests.get(mapping_url, auth=_auth_tuple(), verify=OS_VERIFY, timeout=10)
        field_mappings = {}
        if mapping_resp.status_code == 200:
            properties = mapping_resp.json().get(OS_INDEX, {}).get("mappings", {}).get("properties", {})
            field_mappings = {k: v.get("type", "unknown") for k, v in properties.items()}
        
        # Test species field values
        species_url = f"{BASE_URL}/{OS_INDEX}/_search"
        species_body = {
            "size": 0,
            "aggs": {
                "species_values": {"terms": {"field": "species.keyword", "size": 10}},
                "species_text": {"terms": {"field": "species", "size": 10}}
            }
        }
        species_resp = requests.post(species_url, json=species_body, auth=_auth_tuple(), verify=OS_VERIFY, timeout=10)
        
        species_values = {"keyword": [], "text": []}
        if species_resp.status_code == 200:
            aggs = species_resp.json().get("aggregations", {})
            species_values["keyword"] = [b["key"] for b in aggs.get("species_values", {}).get("buckets", [])]
            species_values["text"] = [b["key"] for b in aggs.get("species_text", {}).get("buckets", [])]
        
        out = {
            "status": "success",
            "index": OS_INDEX,
            "base_url": BASE_URL,
            "total_documents": total_docs,
            "sample_documents": sample_docs,
            "field_mappings": field_mappings,
            "species_values": species_values
        }
        
    except Exception as e:
        out = {
            "status": "error",
            "error": str(e),
            "index": OS_INDEX,
            "base_url": BASE_URL
        }
    
    _log_tool("tool.response", "debug_opensearch_data", ms=round((time.time()-t0)*1000, 1),
              result_preview=_jdump(out))
    return json.dumps(out, ensure_ascii=False)

@mcp.tool(
    name="test_opensearch_connection",
    description="Test OpenSearch connection and return basic index info."
)
def test_opensearch_connection() -> str:
    t0 = time.time()
    _log_tool("tool.request", "test_opensearch_connection", args_preview="{}")
    
    try:
        # Test basic connection
        url = f"{BASE_URL}/{OS_INDEX}/_count"
        resp = requests.get(url, auth=_auth_tuple(), verify=OS_VERIFY, timeout=10)
        
        if resp.status_code == 200:
            count_data = resp.json()
            total_docs = count_data.get("count", 0)
            
            # Get a sample document
            sample_url = f"{BASE_URL}/{OS_INDEX}/_search"
            sample_body = {"size": 1, "query": {"match_all": {}}}
            sample_resp = requests.post(sample_url, json=sample_body, auth=_auth_tuple(), verify=OS_VERIFY, timeout=10)
            
            sample_data = {}
            if sample_resp.status_code == 200:
                hits = sample_resp.json().get("hits", {}).get("hits", [])
                if hits:
                    sample_data = hits[0].get("_source", {})
            
            out = {
                "status": "connected",
                "index": OS_INDEX,
                "base_url": BASE_URL,
                "total_documents": total_docs,
                "sample_document_fields": list(sample_data.keys()) if sample_data else [],
                "sample_document": sample_data
            }
        else:
            out = {
                "status": "error",
                "status_code": resp.status_code,
                "error": resp.text,
                "index": OS_INDEX,
                "base_url": BASE_URL
            }
    except Exception as e:
        out = {
            "status": "connection_error",
            "error": str(e),
            "index": OS_INDEX,
            "base_url": BASE_URL
        }
    
    _log_tool("tool.response", "test_opensearch_connection", ms=round((time.time()-t0)*1000, 1),
              result_preview=_jdump(out))
    return json.dumps(out, ensure_ascii=False)

@mcp.tool(
    name="search_products",
    description="Search pet products using hybrid BM25 (and optional vector KNN) over the OpenSearch index. Parameters: query (string; free-text query), species (Dog|Cat; required), filters (dict; flexible filters for any schema field), page (1-based), size (page size), embedding_text (string; if provided, enables vector KNN fusion). Available filter fields: life_stage, food_type, flavour, tags_any, price_min/price_max, exclude_ingredients, breed_soft, brand, manufacturer, rating, num_reviews, discount_value, pack_size, availability.in_stock, country_of_origin, etc. Returns JSON with results, total, page, size, and mode (bm25|hybrid)."
)
def search_products(
    query: str,
    species: str = "Dog",
    filters: dict = {},
    page: int = 1,
    size: int = 3,
    embedding_text: str = ""
) -> str:
    t0 = time.time()
    sp = _normalize_species(species)
     
    # Log request with key parameters
    request_args = {
        "query": query, "species": sp, "filters": filters,
        "page": page, "size": size, "embedding_text": bool(embedding_text)
    }
    _log_tool("tool.request", "search_products", args_preview=_jdump(request_args))

    def _csv_list(s: str) -> list:
        return [x.strip() for x in (s or "").split(",") if x.strip()]

    must, should, filt, must_not = [], [], [], []
    
    # Use species field (text type) since species.keyword is empty
    filt.append({"term": {"species": sp}})
    
    # Process flexible filters
    for field, value in filters.items():
        if not value:
            continue
            
        # Handle different filter types
        if field == "life_stage":
            if isinstance(value, str) and value.lower() != "all":
                # Include documents that match the requested stage OR 'All'
                filt.append({"terms": {"life_stage": [value, "All"]}})
            elif isinstance(value, str) and value.lower() == "all":
                should.append({"term": {"life_stage": "All"}})
                
        elif field == "food_type":
            filt.append({"term": {"food_type": value}})
            
        elif field == "flavour":
            filt.append({"term": {"flavour": value}})
            
        elif field == "brand":
            filt.append({"term": {"brand": value}})
            
        elif field == "manufacturer":
            filt.append({"term": {"manufacturer": value}})
            
        elif field == "pack_size":
            filt.append({"term": {"pack_size": value}})
            
        elif field == "country_of_origin":
            filt.append({"term": {"country_of_origin": value}})
            
        elif field == "tags_any":
            if isinstance(value, str):
                tags_list = _csv_list(value)
            elif isinstance(value, list):
                tags_list = value
            else:
                tags_list = [str(value)]
            if tags_list:
                should.append({"terms": {"tags": tags_list}})
                
        elif field in ["price_min", "price_max"]:
            # Handle price range
            price_range = {}
            if "price_min" in filters and filters["price_min"]:
                price_range["gte"] = float(filters["price_min"])
            if "price_max" in filters and filters["price_max"]:
                price_range["lte"] = float(filters["price_max"])
            if price_range:
                filt.append({"range": {"price_sale": price_range}})
                
        elif field == "rating":
            if isinstance(value, dict):
                # Handle range queries like {"gte": 4.0}
                filt.append({"range": {"rating": value}})
            else:
                # Handle simple value like 4.0
                filt.append({"range": {"rating": {"gte": float(value)}}})
                
        elif field == "num_reviews":
            if isinstance(value, dict):
                filt.append({"range": {"num_reviews": value}})
            else:
                filt.append({"range": {"num_reviews": {"gte": int(value)}}})
                
        elif field == "discount_value":
            if isinstance(value, dict):
                filt.append({"range": {"discount_value": value}})
            else:
                filt.append({"range": {"discount_value": {"gt": float(value)}}})
                
        elif field == "availability.in_stock":
            filt.append({"term": {"availability.in_stock": bool(value)}})
            
        elif field == "exclude_ingredients":
            if isinstance(value, str):
                excl_list = _csv_list(value)
            elif isinstance(value, list):
                excl_list = value
            else:
                excl_list = [str(value)]
            for ex in excl_list:
                must_not.append({"match_phrase": {"ingredients": ex}})
                must_not.append({"match_phrase": {"flavour": ex}})
                
        elif field == "breed_soft":
            should.append({"match": {"searchable_text": {"query": value, "operator": "and"}}})
            
        else:
            # Generic term filter for other fields
            filt.append({"term": {field: value}})

    # Build query text from filters if no explicit query provided
    if not query.strip():
        query_parts = [f"best food for {sp.lower()}"]
        if "life_stage" in filters and filters["life_stage"]:
            query_parts.append(filters["life_stage"])
        if "breed_soft" in filters and filters["breed_soft"]:
            query_parts.append(filters["breed_soft"])
        qtext = " ".join(query_parts)
    else:
        qtext = query.strip()
    
    # Try multiple text search approaches
    text_queries = [
        {
            "multi_match": {
                "query": qtext,
                "fields": ["title^5", "brand^3", "tags^3", "food_type^3", "flavour^2", "ingredients", "description", "searchable_text"],
                "type": "best_fields",
                "operator": "and"
            }
        },
        {
            "multi_match": {
                "query": qtext,
                "fields": ["title^5", "brand^3", "tags^3", "food_type^3", "flavour^2", "ingredients", "description"],
                "type": "best_fields",
                "operator": "or"
            }
        },
        {
            "match": {
                "title": {"query": qtext, "boost": 5}
            }
        }
    ]
    must.append({"bool": {"should": text_queries, "minimum_should_match": 1}})

    bm25_body = {
        "size": min(max(size * 3, size), 150),
        "query": {"bool": {"must": must, "filter": filt, "should": should, "must_not": must_not}},
        "_source": True
    }
    bm25_res = os_search(bm25_body)
    bm25_hits = ((bm25_res.get("hits") or {}).get("hits") or [])

    knn_hits = []
    if embedding_text and _knn_available["ok"]:
        vec = embed_text_with_openai(embedding_text)
        if vec:
            try:
                knn_body = {
                    "size": min(max(size * 3, size), 150),
                    "query": {
                        "bool": {
                            "filter": filt,
                            "must_not": must_not,
                            "must": [
                                {
                                    "knn": {
                                        "embedding_product": {
                                            "vector": vec,
                                            "k": 100,
                                            "method_parameters": {"ef_search": 200},
                                            "rescore": {"oversample_factor": 2.0}
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    "_source": True
                }
                _log_tool("tool.request", "search_products.knn", args_preview=_jdump({"vector_len": len(vec)}))
                knn_res = os_search(knn_body)
                knn_hits = ((knn_res.get("hits") or {}).get("hits") or [])
            except Exception as e:
                _log_tool("tool.warn", "search_products.knn_failed", error=str(e))
                if "Unknown key" in str(e) or "parsing_exception" in str(e):
                    _knn_available["ok"] = False

    def rrf(hits, k=60):
        ranks = {}
        for idx, h in enumerate(hits, start=1):
            _id = h.get("_id") or (h.get("_source") or {}).get("variant_id") or ""
            if not _id:
                continue
            ranks[_id] = ranks.get(_id, 0.0) + 1.0 / (k + idx)
        return ranks

    fused = rrf(bm25_hits)
    if knn_hits:
        knn_scores = rrf(knn_hits)
        for did, s in knn_scores.items():
            fused[did] = fused.get(did, 0.0) + s

    docmap = {_h.get("_id"): _h for _h in (bm25_hits + knn_hits) if _h.get("_id")}
    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    ranked_docs = [docmap[i] for i, _ in ranked] if ranked else bm25_hits

    # Return top 5 after fusion
    page_docs = ranked_docs[:5]

    results = []
    for h in page_docs:
        s = h.get("_source", {})
        results.append({
            "id": h.get("_id"),
            "title": s.get("title"),
            "brand": s.get("brand"),
            "price_sale": s.get("price_sale") or (s.get("price") or {}).get("sale"),
            "currency": (s.get("price") or {}).get("currency"),
            "in_stock": (s.get("availability") or {}).get("in_stock"),
            "score": h.get("_score"),
            "life_stage": s.get("life_stage"),
            "flavour": s.get("flavour"),
            "food_type": s.get("food_type"),
            "rating": s.get("rating"),
            "num_reviews": s.get("num_reviews")
        })

    out = {"results": results, "total": len(ranked_docs), "page": page, "size": 5,
           "mode": "hybrid" if knn_hits else "bm25"}
    _log_tool("tool.response", "search_products", ms=round((time.time()-t0)*1000, 1),
              result_preview=_jdump({"returned": len(results), "mode": out["mode"]}))
    return json.dumps(out, ensure_ascii=False)

# ==============================================================================
# HTTP app + middleware
# ==============================================================================
_factory = getattr(mcp, "http_app", None) or getattr(mcp, "streamable_http_app", None)
if _factory is None:
    raise RuntimeError("Your fastmcp version lacks http_app/streamable_http_app. Upgrade fastmcp.")
app = _factory(path="/mcp")

# --- BEGIN: swallow DELETE /mcp so sessions aren't torn down by the client ---
class IgnoreDeleteMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Match DELETE exactly on /mcp (ignore trailing slash)
        if request.method == "DELETE" and request.url.path.rstrip("/") == "/mcp":
            # Optional: gate on MCP header if you want
            # if "mcp-session-id" in request.headers:
            #     ...
            return JSONResponse({}, status_code=200)
        return await call_next(request)

app = IgnoreDeleteMiddleware(app)
# --- END: swallow DELETE /mcp ---

class RequestResponseLogger(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        hdr = request.headers
        body = await request.body()

        # Auth header analysis
        auth_header = hdr.get("authorization", "")
        scheme, token = ("", "")
        if auth_header:
            parts = auth_header.split(" ", 1)
            scheme = parts[0]
            token = parts[1] if len(parts) > 1 else ""

        def token_repr(t: str) -> str:
            if not t: return "none"
            if LOG_SHOW_TOKENS: return t
            digest = hashlib.sha256(t.encode()).hexdigest()[:10]
            preview = (t[:6] + "..." + t[-4:]) if len(t) > 12 else "masked"
            return f"{preview} sha256:{digest}"

        print("=== REQUEST ===")
        print(f"{request.client.host} {request.method} {request.url.path}")
        print(f"Headers: {dict(hdr)}")
        print(f"Auth: scheme={scheme or 'none'} received={token_repr(token)}")
        clip_req = body if len(body) <= LOG_BODY_LIMIT else body[:LOG_BODY_LIMIT] + b"\n...[truncated]"
        print("Body:", clip_req.decode("utf-8", errors="replace") if body else "<empty>")

        response = await call_next(request)

        ctype = response.headers.get("content-type", "")
        if ctype.startswith("text/event-stream"):
            print("=== RESPONSE ===")
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            print("Body: <streaming>")
            return response

        resp_body = b""
        async for chunk in response.body_iterator:
            resp_body += chunk

        print("=== RESPONSE ===")
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        clip_resp = resp_body if len(resp_body) <= LOG_BODY_LIMIT else resp_body[:LOG_BODY_LIMIT] + b"\n...[truncated]"
        print("Body:", clip_resp.decode("utf-8", errors="replace") if resp_body else "<empty>")

        return Response(
            content=resp_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
            background=response.background,
        )

app = CORSMiddleware(app, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])
app = RequestResponseLogger(app)

# ==============================================================================
# Main
# ==============================================================================
if __name__ == "__main__":
    jlog("server.config", base_url=BASE_URL, index=OS_INDEX, scheme=OS_SCHEME,
         verify=str(OS_VERIFY), auth_enabled=not DISABLE_AUTH)
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=True)
