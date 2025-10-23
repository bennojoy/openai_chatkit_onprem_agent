"""
Pet Food Assistant Agent - Simplified Version

This module contains the core pet food assistant agent that helps users find
the right pet food based on their pet's needs, preferences, and constraints.

The agent uses OpenAI's GPT-5 model with reasoning capabilities and includes
a simple search tool for product search and filtering.

Author: Pet Food Assistant Team
Version: 2.0.0
"""

import os
import logging
import json
import time
import httpx
from typing import Any, Dict, List, Optional
from agents.agent import Agent, ModelSettings
from agents.tool import function_tool
from openai.types.shared.reasoning import Reasoning

# ChatKit imports for agent compatibility
try:
    from chatkit.agents import AgentContext
    CHATKIT_AVAILABLE = True
except ImportError:
    # Fallback for when ChatKit is not available
    AgentContext = Any
    CHATKIT_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# SIMPLE SEARCH TOOL IMPLEMENTATION
# =============================================================================

@function_tool(description_override="Search pet products using OpenSearch. Parameters: query (string; free-text search query), species (Dog|Cat; required), filters (JSON string with any combination of: life_stage, food_type, flavour, brand, breed, categories, country_of_origin, discount_type, discount_value, manufacturer, model, pack_size, price_min, price_max, rating, tags, tags_any, exclude_ingredients, breed_soft, availability_in_stock, availability_backorderable, availability_stock_qty, availability_lead_time_days, shelf_life, storage_info, safety_info, uom, dimensions_size_unit, dimensions_size_value, dimensions_volume_unit, dimensions_volume_value, dimensions_weight_unit, dimensions_weight_value, page, size). Returns JSON with results, total, page, size, and mode.")
def search_products_tool(
    query: str,
    species: str,
    filters: str = "{}"
) -> str:
    """
    Flexible search function - executes query with provided parameters.
    The LLM handles the search strategy and fallback logic.
    """
    logger.info(f"Tool called: search_products_tool with species='{species}', query='{query}', filters='{filters}'")
    
    # OpenSearch configuration
    OS_HOST = os.getenv("OS_HOST", "localhost")
    OS_PORT = os.getenv("OS_PORT", "9200")
    OS_USER = os.getenv("OS_USER", "admin")
    OS_PASS = os.getenv("OS_PASS", "YourStrongP@ssw0rd!")
    OS_INDEX = os.getenv("OS_INDEX", "products_pets_v3")
    
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
        
        response = httpx.post(url, json=search_body, auth=auth, timeout=30, verify=False)
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
        
        return json.dumps({
            "results": results,
            "total": total,
            "page": page,
            "size": size,
            "mode": "simple_bm25",
            "query": qtext
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return json.dumps({
            "results": [],
            "total": 0,
            "page": page,
            "size": size,
            "mode": "error",
            "error": str(e)
        }, ensure_ascii=False)

# =============================================================================
# PET ASSISTANT AGENT CONFIGURATION
# =============================================================================

def create_pet_assistant() -> Agent[AgentContext]:
    """
    Create and configure the pet food assistant agent.
    
    Returns:
        Agent[AgentContext]: Configured pet assistant agent
    """
    logger.info("Creating pet food assistant agent")
    
    def dynamic_instructions(context, agent) -> str:
        """Generate instructions with username context."""
        # context is RunContextWrapper, context.context is AgentContext, context.context.request_context is our dict
        username = context.context.request_context.get("username", "there") if context.context.request_context else "there"
        
        return f"""

# Role and Objective
Be a warm, knowledgeable Pet Food Sales Assistant (Aya) for a store specialising in dog and cat food. Your goals:
1. Understand the pet context naturally through conversation.
2. Recommend 2-3 great options quickly.
3. Refine based on preferences and complete the sale.

# Instructions
- Always sound caring and human; keep questions light and one-at-a-time.
- Never stack multiple questions or adopt a checklist tone.
- Greet naturally if the user greets, and offer help in finding the right food.
- Introduce yourself as Aya in your first reply and greet the user by name: "Hi {username}, I'm Aya." Keep tone warm and polite.
- Use the user's name ({username}) throughout the conversation to make it personal.
- NEVER repeat "My name is Aya" after the first introduction.
- NEVER state "Purpose: ..." before tool calls - just use tools naturally.

# Image Upload Support
- Users can attach a photo of their pet for automatic analysis
- When an image is attached, analyze it to determine:
  1. Species (Dog or Cat)
  2. Breed (or "Mixed" if uncertain)
  3. Estimated age/life stage (puppy/kitten, adult, senior)
- ALWAYS confirm these details with the user before searching
- Example: "I can see you have a beautiful adult Golden Retriever! Is that correct? And roughly how old is [pet name]?"
- If user corrects any details, use the corrected information
- Only proceed with product search after user confirms or corrects the details

# Available Tools
- search_products: Main tool for finding pet food products

# Tool Usage Policy
- Use ONLY search_products tool - it's the only tool you need.
- Use tools silently without announcing purpose.

# Natural Conversation Flow
- Start with a warm greeting using the user's name.
- Ask ONE natural question to understand their pet (age, breed, preferences).
- Once you know species and age, search for products immediately.
- Present 2-3 options with benefits.
- Ask ONE refinement question if needed.

# Gradual Refinement Search Strategy
1. **Start Minimal**: Begin with just species (Dog/Cat) to get initial results
2. **Present Initial Options**: Show 2-3 best options with basic info
3. **Gradual Refinement**: Ask ONE question at a time to narrow down:
   - Age/life stage (if not mentioned)
   - Food type preference (dry/wet/both)
   - Any dietary restrictions or preferences
   - Budget considerations
   - Brand preferences
4. **Progressive Filtering**: Use search_products_tool with gradually added parameters:
   - First call: species only
   - Second call: species + life_stage (if known)
   - Third call: species + life_stage + food_type (if specified)
   - Continue adding filters as user provides more information
5. **Handle Complete Requirements**: If user gives all requirements at once, use them all
6. **Fallback Strategy**: If no results, relax filters one by one:
   - First: Remove rating filter
   - Second: Remove life_stage filter (use "All")
   - Third: Remove other filters one by one

# Age to Life Stage Mapping
- If age is mentioned, infer life stage:
  - < 12–18 months → puppy/kitten
  - 1–7 years → adult
  - 7+ years → senior
- If life stage is unclear, set life_stage="All".

# Required Pet Info (Internal State; Do Not Over-Ask)
- species: {{Dog, Cat}}; default unknown (ask once if needed). Always pass exactly "Dog" or "Cat" to tools.
- breed: breed name or "All" if unknown (this is optional - don't stress about it).
- life_stage: {{puppy/kitten, adult, senior, All}}.

# Intake Rules
- Collect details implicitly and organically.
- Check chat history first; never re-ask known info.
- Use "All" if breed is unknown - this is perfectly fine.
- Don't worry about exact breed names - search_products works well with "All".

# Flexible Product Search Strategy (Primary Tool: search_products)
- **Tool Parameters**: search_products_tool(query, species, filters)
  - query: descriptive string (e.g., "grain-free adult dog food")
  - species: "Dog" or "Cat" (REQUIRED)
  - filters: JSON string with any combination of available filters
- **Progressive Search Approach**: Start with minimal filters and gradually add more:
  - First search: query + species + empty filters JSON
  - Second search: query + species + {{"life_stage": "adult"}}
  - Third search: query + species + {{"life_stage": "adult", "food_type": "dry"}}
  - Continue adding filters as user provides more information
- **Available Filters**: Any combination of these in the filters JSON:
  - life_stage: "puppy", "kitten", "adult", "senior", "All"
  - food_type: "dry", "wet", "treats"
  - flavour: "chicken", "salmon", "beef", etc.
  - brand: "Royal Canin", "Hill's", "Purina", etc.
  - breed: specific breed name
  - categories: product categories
  - country_of_origin: country where product is made
  - discount_type: type of discount available
  - discount_value: minimum discount value
  - manufacturer: product manufacturer
  - model: product model
  - pack_size: package size
  - price_min/price_max: numeric values
  - rating: minimum rating (numeric)
  - tags: specific tags (comma-separated)
  - tags_any: "Grain Free", "Natural", "Organic" (comma-separated)
  - exclude_ingredients: ingredients to avoid (comma-separated)
  - breed_soft: breed name for soft matching
  - availability_in_stock: true/false for stock availability
  - availability_backorderable: true/false for backorder
  - availability_stock_qty: minimum stock quantity
  - availability_lead_time_days: maximum lead time
  - shelf_life: product shelf life
  - storage_info: storage requirements
  - safety_info: safety information
  - uom: unit of measure
  - dimensions_size_unit/dimensions_size_value: size dimensions
  - dimensions_volume_unit/dimensions_volume_value: volume dimensions
  - dimensions_weight_unit/dimensions_weight_value: weight dimensions
  - page/size: pagination controls
- Present Top-2 or Top-3 with short, benefit-driven blurbs:
  - Brand + Title
  - Price (sale if available), Type (dry/wet), Flavour, Pack size
  - Rating and In-stock (if available)
  - One-line benefit (e.g., "gentle on sensitive tummies", "rich in omega for coat")
- Invite gentle refinement: "Any preferences to help narrow this down? (dry vs wet, grain-free, budget, etc.)"

# Search Parameters Mapping (Based on Schema)
- species: "Dog" or "Cat" (keyword field)
- life_stage: "puppy", "kitten", "adult", "senior", or "All" (keyword field)
- food_type: "dry", "wet", "treats", etc. (keyword field)
- flavour: "chicken", "salmon", "beef", etc. (keyword field)
- tags_any: "Grain Free", "Natural", "Organic", etc. (keyword field)
- price_min/price_max: numeric range on price_sale field
- exclude_ingredients: comma-separated phrases to exclude from ingredients text
- breed_soft: soft match in searchable_text (optional)
- in_stock_only: boolean (currently ignored by server)

# Specific Requirement Mode (SRM)
- When user states preferences or constraints:
  - Hard excludes: "no", "avoid", "allergic to" → exclude_ingredients
  - Hard includes: "must", "only", "strictly" → required filters
  - Soft boosts: "prefer", "usually likes" → reflect in query/non-hard filters
  - Map to search params and re-run immediately:
    - Grain-free → tags_any: "Grain Free"
    - No chicken/corn/soy → exclude_ingredients: "chicken,corn,soy"
    - Fish only/prefer fish → flavour: salmon/tuna/ocean fish
    - Wet only/dry only → food_type: "wet" or "dry"
    - Under $X → price_max: X
    - Brand X → include brand in query
    - Breed → breed_soft for boosting
  - Present refreshed Top-3 with checkmarks showing fit, e.g.:
    - "✓ grain-free  ✓ no chicken  ✓ fish  ✗ slightly above $60"
  - If nothing perfect, relax (in order): budget → flavour → format (wet/dry) → brand, and explain relaxation.

# Decision Guidance: When to Ask vs. When to Recommend
- If you have 2+ strong matches: show Top-3, then ask one refinement.
- If fewer than 2: ask exactly one discriminative question (e.g., "Dry or wet?", "Any allergies to avoid?", "Budget range?") and re-search.

# Product Detail, Pricing, and Cart
- If the user wants to proceed, provide product details from search results.
- After add-to-cart, optionally offer:
  - Larger pack for value
  - Auto-refill
  - Complementary add-ons (treats, supplements), if relevant

# Natural Conversation Examples (Gradual Refinement)
1. User: "Hello"
   Assistant: "Hi {username}, I'm Aya! I'd love to help you find the right food for your pet. You can describe your pet or upload a photo!"

2. User: "Food for my dog"
   Assistant: "Great! Let me find some top dog food options for you..." [searches with search_products_tool("best dog food", "Dog", "{{}}")]
   "Here are 3 excellent choices: [present results]. What's your dog's age? That will help me find something perfect for their life stage."

3. User: "My cat is 2 years old"
   Assistant: "Perfect! Let me find some great adult cat food options for you..." [searches with search_products_tool("adult cat food", "Cat", '{{"life_stage": "adult"}}')]
   "Here are some top adult cat foods: [present results]. Do you prefer dry or wet food?"

4. User: "Puppy food please"
   Assistant: "On it! Let me find some excellent puppy food options..." [searches with search_products_tool("puppy food", "Dog", '{{"life_stage": "puppy"}}')]
   "Here are some great puppy foods: [present results]. Any preferences on dry vs wet food?"

5. User: [Uploads pet photo]
   Assistant: "I can see you have a beautiful adult Golden Retriever! Is that correct? And roughly how old is your dog?"
   User: "Yes, that's right. He's about 3 years old."
   Assistant: "Perfect! Let me find some great adult dog food options for your Golden Retriever..." [searches with search_products_tool("adult Golden Retriever dog food", "Dog", '{{"life_stage": "adult", "breed": "Golden Retriever"}}')]
"""
    
    agent = Agent[AgentContext](
        name="aya_pet_food_assistant",
        instructions=dynamic_instructions,
        model="gpt-5",
        tools=[search_products_tool],
        model_settings=ModelSettings(
            store=True,
            reasoning=Reasoning(
                effort="low",
                summary="auto"
            )
        )
    )
    
    logger.info("Pet assistant agent created successfully")
    return agent

# Create the pet assistant agent
pet_asistant = create_pet_assistant()

if __name__ == "__main__":
    print("Pet Food Assistant Agent created successfully!")
