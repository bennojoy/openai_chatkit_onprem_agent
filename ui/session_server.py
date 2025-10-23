

# server.py
import os
import requests
import json
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any
import logging

# Import OpenAI client for Prompt API
from openai import OpenAI

logger = logging.getLogger("chatkit")
logging.basicConfig(level=logging.INFO)


app = FastAPI()

# Env vars you must set:
#   OPENAI_API_KEY=sk-...
#   CHATKIT_WORKFLOW_ID=wf_...
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
WORKFLOW_ID = os.environ["CHATKIT_WORKFLOW_ID"]
CHATKIT_API_URL = "https://api.openai.com/v1/chatkit/sessions"
REALTIME_CLIENT_SECRETS_URL = "https://api.openai.com/v1/realtime/client_secrets"

# Product Search Prompt Configuration
PRODUCT_SEARCH_PROMPT_ID = "pmpt_68ec7e8ca37c8195aacb20213e52a3bf0e15553ef22084a3"
PRODUCT_SEARCH_PROMPT_VERSION = "2"

# MCP Server Configuration (for prompt tools)
# Set these environment variables with your values:
#   MCP_SERVER_URL=https://your-ngrok-url.ngrok-free.app/your-path
#   MCP_AUTHORIZATION=your-auth-token
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "")
MCP_AUTHORIZATION = os.environ.get("MCP_AUTHORIZATION", "")

# OpenSearch Configuration (matching Python agent)
OS_HOST = os.getenv("OS_HOST", "localhost")
OS_PORT = os.getenv("OS_PORT", "9200")
OS_USER = os.getenv("OS_USER", "admin")
OS_PASS = os.getenv("OS_PASS", "YourStrongP@ssw0rd!")
OS_INDEX = os.getenv("OS_INDEX", "products_pets_v3")

# Initialize OpenAI client for Prompt API
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# =============================================================================
# OPENSEARCH SEARCH FUNCTION (matching Python agent)
# =============================================================================

async def search_products_opensearch(query: str, species: str, filters: str = "{}") -> dict:
    """
    Direct OpenSearch integration matching the Python agent's search_products_tool function.
    """
    logger.info(f"OpenSearch search: species='{species}', query='{query}', filters='{filters}'")
    
    # Parse filters JSON
    try:
        filter_dict = json.loads(filters) if filters else {}
    except json.JSONDecodeError:
        logger.warning(f"Invalid filters JSON: {filters}, using empty filters")
        filter_dict = {}
    
    # Extract parameters from filters with defaults
    life_stage = filter_dict.get("life_stage", "")
    food_type = filter_dict.get("food_type", "")
    flavour = filter_dict.get("flavour", "")
    brand = filter_dict.get("brand", "")
    breed = filter_dict.get("breed", "")
    categories = filter_dict.get("categories", "")
    country_of_origin = filter_dict.get("country_of_origin", "")
    discount_type = filter_dict.get("discount_type", "")
    discount_value = float(filter_dict.get("discount_value", 0.0))
    manufacturer = filter_dict.get("manufacturer", "")
    model = filter_dict.get("model", "")
    pack_size = filter_dict.get("pack_size", "")
    price_min = float(filter_dict.get("price_min", 0.0))
    price_max = float(filter_dict.get("price_max", 0.0))
    rating = float(filter_dict.get("rating", 0.0))
    tags = filter_dict.get("tags", "")
    tags_any = filter_dict.get("tags_any", "")
    exclude_ingredients = filter_dict.get("exclude_ingredients", "")
    breed_soft = filter_dict.get("breed_soft", "")
    availability_in_stock = filter_dict.get("availability_in_stock", None)
    availability_backorderable = filter_dict.get("availability_backorderable", None)
    availability_stock_qty = int(filter_dict.get("availability_stock_qty", 0))
    availability_lead_time_days = int(filter_dict.get("availability_lead_time_days", 0))
    shelf_life = filter_dict.get("shelf_life", "")
    storage_info = filter_dict.get("storage_info", "")
    safety_info = filter_dict.get("safety_info", "")
    uom = filter_dict.get("uom", "")
    dimensions_size_unit = filter_dict.get("dimensions_size_unit", "")
    dimensions_size_value = float(filter_dict.get("dimensions_size_value", 0.0))
    dimensions_volume_unit = filter_dict.get("dimensions_volume_unit", "")
    dimensions_volume_value = float(filter_dict.get("dimensions_volume_value", 0.0))
    dimensions_weight_unit = filter_dict.get("dimensions_weight_unit", "")
    dimensions_weight_value = float(filter_dict.get("dimensions_weight_value", 0.0))
    page = int(filter_dict.get("page", 1))
    size = int(filter_dict.get("size", 3))
    
    # Normalize species
    sp = species.title() if species.lower() in ["dog", "cat"] else "Dog"
    
    # Build simple query with provided parameters
    must, should, filt, must_not = [], [], [], []
    
    # Species filter (required)
    filt.append({"term": {"species": sp}})
    
    # Add other filters if provided
    if life_stage and life_stage.lower() != "all":
        filt.append({"terms": {"life_stage": [life_stage, "All"]}})
    
    if food_type:
        filt.append({"term": {"food_type": food_type}})
        
    if flavour:
        filt.append({"term": {"flavour": flavour}})
        
    if brand:
        filt.append({"term": {"brand": brand}})
        
    if breed:
        filt.append({"term": {"breed": breed}})
        
    if categories:
        filt.append({"term": {"categories": categories}})
        
    if country_of_origin:
        filt.append({"term": {"country_of_origin": country_of_origin}})
        
    if discount_type:
        filt.append({"term": {"discount_type": discount_type}})
        
    if discount_value > 0:
        filt.append({"range": {"discount_value": {"gte": discount_value}}})
        
    if manufacturer:
        filt.append({"term": {"manufacturer": manufacturer}})
        
    if model:
        filt.append({"term": {"model": model}})
        
    if pack_size:
        filt.append({"term": {"pack_size": pack_size}})
        
    if price_min > 0 or price_max > 0:
        price_range = {}
        if price_min > 0:
            price_range["gte"] = price_min
        if price_max > 0:
            price_range["lte"] = price_max
        filt.append({"range": {"price_sale": price_range}})
        
    if rating > 0:
        filt.append({"range": {"rating": {"gte": rating}}})
        
    if tags:
        tags_list = [x.strip() for x in tags.split(",") if x.strip()]
        if tags_list:
            should.append({"terms": {"tags": tags_list}})
        
    if tags_any:
        tags_list = [x.strip() for x in tags_any.split(",") if x.strip()]
        if tags_list:
            should.append({"terms": {"tags": tags_list}})
            
    if exclude_ingredients:
        excl_list = [x.strip() for x in exclude_ingredients.split(",") if x.strip()]
        for ex in excl_list:
            must_not.append({"match_phrase": {"ingredients": ex}})
            
    if breed_soft:
        should.append({"match": {"searchable_text": {"query": breed_soft, "operator": "or"}}})
        
    # Availability filters
    if availability_in_stock is not None:
        filt.append({"term": {"availability.in_stock": availability_in_stock}})
        
    if availability_backorderable is not None:
        filt.append({"term": {"availability.backorderable": availability_backorderable}})
        
    if availability_stock_qty > 0:
        filt.append({"range": {"availability.stock_qty": {"gte": availability_stock_qty}}})
        
    if availability_lead_time_days > 0:
        filt.append({"range": {"availability.lead_time_days": {"lte": availability_lead_time_days}}})
        
    # Product info filters
    if shelf_life:
        filt.append({"term": {"shelf_life": shelf_life}})
        
    if storage_info:
        filt.append({"term": {"storage_info": storage_info}})
        
    if safety_info:
        filt.append({"term": {"safety_info": safety_info}})
        
    if uom:
        filt.append({"term": {"uom": uom}})
        
    # Dimension filters
    if dimensions_size_unit and dimensions_size_value > 0:
        filt.append({"term": {"dimensions.size_unit": dimensions_size_unit}})
        filt.append({"range": {"dimensions.size_value": {"gte": dimensions_size_value}}})
        
    if dimensions_volume_unit and dimensions_volume_value > 0:
        filt.append({"term": {"dimensions.volume_unit": dimensions_volume_unit}})
        filt.append({"range": {"dimensions.volume_value": {"gte": dimensions_volume_value}}})
        
    if dimensions_weight_unit and dimensions_weight_value > 0:
        filt.append({"term": {"dimensions.weight_unit": dimensions_weight_unit}})
        filt.append({"range": {"dimensions.weight_value": {"gte": dimensions_weight_value}}})
    
    # Build query text
    if not query.strip():
        query_parts = [f"best food for {sp.lower()}"]
        if life_stage and life_stage.lower() != "all":
            query_parts.append(life_stage)
        qtext = " ".join(query_parts)
    else:
        qtext = query.strip()
    
    # Simple text search
    text_queries = [
        {"multi_match": {"query": qtext, "fields": ["title^2", "description", "searchable_text"], "type": "best_fields", "fuzziness": "AUTO"}},
        {"match": {"searchable_text": {"query": qtext, "operator": "or"}}}
    ]
    
    # Build final query
    bool_query = {
        "bool": {
            "should": text_queries + should,
            "filter": filt,
            "must_not": must_not
        }
    }
    
    # Execute search
    search_body = {
        "query": bool_query,
        "size": size,
        "from": (page - 1) * size,
        "sort": [{"_score": {"order": "desc"}}],
        "_source": {
            "excludes": ["embedding_product", "searchable_text", "updated_at", "embeddings"]
        }
    }
    
    try:
        # Make request to OpenSearch (using HTTPS)
        url = f"https://{OS_HOST}:{OS_PORT}/{OS_INDEX}/_search"
        auth = (OS_USER, OS_PASS)
        
        logger.info(f"Making OpenSearch request to: {url}")
        logger.info(f"Search body: {json.dumps(search_body, indent=2)}")
        
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(url, json=search_body, auth=auth, timeout=30)
        
        logger.info(f"OpenSearch response status: {response.status_code}")
        
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"OpenSearch response data: {json.dumps(data, indent=2)}")
        
        hits = data.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        
        logger.info(f"OpenSearch found {total} total results, returning {len(hits.get('hits', []))} hits")
        
        results = []
        for hit in hits.get("hits", []):
            source = hit["_source"]
            # Return all fields except embeddings, searchable_text, and updated_at
            result = {
                "title": source.get("title", ""),
                "brand": source.get("brand", ""),
                "breed": source.get("breed", ""),
                "categories": source.get("categories", ""),
                "country_of_origin": source.get("country_of_origin", ""),
                "description": source.get("description", ""),
                "dimensions": source.get("dimensions", {}),
                "discount_type": source.get("discount_type", ""),
                "discount_value": source.get("discount_value", 0),
                "flavour": source.get("flavour", ""),
                "food_type": source.get("food_type", ""),
                "gtin": source.get("gtin", ""),
                "image_url_primary": source.get("image_url_primary", ""),
                "ingredients": source.get("ingredients", ""),
                "life_stage": source.get("life_stage", ""),
                "manufacturer": source.get("manufacturer", ""),
                "model": source.get("model", ""),
                "mpn": source.get("mpn", ""),
                "num_reviews": source.get("num_reviews", 0),
                "pack_size": source.get("pack_size", ""),
                "price": source.get("price", {}),
                "price_list": source.get("price_list", 0),
                "price_mrp": source.get("price_mrp", 0),
                "price_sale": source.get("price_sale", 0),
                "product_id": source.get("product_id", ""),
                "product_url": source.get("product_url", ""),
                "qty_available": source.get("qty_available", 0),
                "rating": source.get("rating", 0),
                "safety_info": source.get("safety_info", ""),
                "shelf_life": source.get("shelf_life", ""),
                "sku": source.get("sku", ""),
                "species": source.get("species", ""),
                "storage_info": source.get("storage_info", ""),
                "subtitle": source.get("subtitle", ""),
                "synonyms": source.get("synonyms", []),
                "tags": source.get("tags", []),
                "uom": source.get("uom", ""),
                "variant_id": source.get("variant_id", ""),
                "availability": source.get("availability", {}),
                "score": hit.get("_score", 0)
            }
            results.append(result)
        
        logger.info(f"Returning {len(results)} results to agent")
        
        return {
            "results": results,
            "total": total,
            "page": page,
            "size": size,
            "mode": "simple_bm25",
            "query": qtext
        }
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {
            "results": [],
            "total": 0,
            "page": page,
            "size": size,
            "mode": "error",
            "error": str(e)
        }

class SessionReq(BaseModel):
    user: str  # your user id or a stable device id

class RealtimeSessionReq(BaseModel):
    model: str = "gpt-4o-realtime-preview-2025-06-03"  # default model
    voice: str = "sage"  # default voice (alloy, echo, sage, shimmer, etc.)

class ProductSearchRequest(BaseModel):
    query: str  # The customer's product query
    species: str  # Required: Dog or Cat
    filters: str = "{}"  # JSON string with search filters

@app.post("/api/chatkit/session")
def create_chatkit_session(payload: SessionReq):
    try:
        logger.info("SESSION start user=%s", payload.user)
        logger.info("Using workflow_id=%s", WORKFLOW_ID)
        
        response = requests.post(
            CHATKIT_API_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "chatkit_beta=v1"
            },
            json={
                "workflow": {"id": WORKFLOW_ID},
                "user": payload.user
            }
        )
        
        logger.info("OpenAI API response status: %s", response.status_code)
        
        if not response.ok:
            error_detail = response.text
            logger.error("OpenAI API error: %s", error_detail)
            raise HTTPException(status_code=response.status_code, detail=error_detail)
        
        data = response.json()
        logger.info("SESSION created successfully, client_secret exists: %s", bool(data.get("client_secret")))
        return {"client_secret": data["client_secret"]}
    except requests.RequestException as e:
        logger.error("SESSION creation failed (network error): %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        logger.error("SESSION creation failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Realtime API Session Endpoint (for voice chat)
# =============================================================================

@app.post("/api/realtime/session")
def create_realtime_session(payload: RealtimeSessionReq = RealtimeSessionReq()):
    """
    Creates an ephemeral client secret for OpenAI Realtime API (voice).
    Returns the ephemeral key that the browser uses to establish WebRTC connection.
    Per official docs: https://openai.github.io/openai-agents-js/guides/voice-agents/quickstart/
    """
    try:
        logger.info("REALTIME SESSION start model=%s voice=%s", payload.model, payload.voice)
        
        # Use the CORRECT endpoint per the official SDK docs
        response = requests.post(
            REALTIME_CLIENT_SECRETS_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "session": {
                    "type": "realtime",
                    "model": "gpt-realtime",
                }
            }
        )
        
        logger.info("OpenAI Realtime API response status: %s", response.status_code)
        
        if not response.ok:
            error_detail = response.text
            logger.error("OpenAI Realtime API error: %s", error_detail)
            raise HTTPException(status_code=response.status_code, detail=error_detail)
        
        data = response.json()
        logger.info("REALTIME CLIENT SECRET created successfully")
        logger.info("Response contains 'value': %s", "value" in data)
        
        # Return just the ephemeral key value
        # The response format is: { "value": "ek_..." }
        return {"client_secret": data}
        
    except requests.RequestException as e:
        logger.error("REALTIME SESSION creation failed (network error): %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        logger.error("REALTIME SESSION creation failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# ChatKit Refresh Endpoint
# =============================================================================

# Optional: refresh endpoint (same call; ChatKit will hit this when token expires)
@app.post("/api/chatkit/refresh")
def refresh_chatkit_session(payload: SessionReq):
    try:
        logger.info("REFRESH session for user=%s", payload.user)
        
        response = requests.post(
            CHATKIT_API_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "chatkit_beta=v1"
            },
            json={
                "workflow": {"id": WORKFLOW_ID},
                "user": payload.user
            }
        )
        
        if not response.ok:
            error_detail = response.text
            logger.error("OpenAI API error on refresh: %s", error_detail)
            raise HTTPException(status_code=response.status_code, detail=error_detail)
        
        data = response.json()
        logger.info("REFRESH successful")
        return {"client_secret": data["client_secret"]}
    except requests.RequestException as e:
        logger.error("REFRESH failed (network error): %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        logger.error("REFRESH failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Product Search Agent Endpoint (uses OpenAI Prompt)
# =============================================================================

@app.post("/api/agents/product-search")
async def search_products(payload: ProductSearchRequest):
    """
    Product search endpoint using direct OpenSearch integration.
    The voice agent calls this when customer asks for specific products.
    """
    try:
        logger.info("=" * 70)
        logger.info("🔧 PRODUCT SEARCH ENDPOINT HIT")
        logger.info("=" * 70)
        logger.info("📥 Received query: %s", payload.query)
        logger.info("📥 Received species: %s", payload.species)
        logger.info("📥 Received filters: %s", payload.filters)
        logger.info("📥 Full payload: %s", payload)
        
        # Call our direct OpenSearch function
        logger.info("🔍 Calling direct OpenSearch integration...")
        search_result = await search_products_opensearch(
            query=payload.query,
            species=payload.species,
            filters=payload.filters
        )
        
        logger.info("📤 OpenSearch result: %s", json.dumps(search_result, indent=2))
        
        # Return the result in the same format as Python agent
        result = {
            "status": "success",
            "response": json.dumps(search_result, ensure_ascii=False),
            "query": payload.query,
            "species": payload.species,
            "filters": payload.filters
        }
        
        logger.info("✅ PRODUCT SEARCH completed successfully")
        logger.info("=" * 70)
        return result
        
    except Exception as e:
        logger.error("PRODUCT SEARCH failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Product search error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # For local dev; in prod run behind a proper ASGI server
    uvicorn.run(app, host="0.0.0.0", port=8000)

