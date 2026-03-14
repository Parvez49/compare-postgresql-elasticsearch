"""
╔══════════════════════════════════════════════════════════════════╗
║           PostgreSQL vs Elasticsearch — API Views                ║
║                                                                  ║
║  This file contains PARALLEL implementations:                    ║
║  • Pg*  endpoints → hit PostgreSQL directly                      ║
║  • Es*  endpoints → hit Elasticsearch directly                   ║
║                                                                  ║
║  Compare response times, result quality, and capabilities.       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import time
from functools import wraps

from django.db.models import Q, Avg, Count, Min, Max, F
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from elasticsearch_dsl import Q as ESQ, Search

from .models import Product, Category, Brand
from .serializers import (
    ProductSerializer,
    ProductListSerializer,
    ESProductSerializer,
    CategorySerializer,
    BrandSerializer,
)
from .documents import ProductDocument


def timed_response(func):
    """Decorator to add query timing to every response."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        response = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if isinstance(response, Response):
            if isinstance(response.data, dict):
                response.data["_query_time_ms"] = round(elapsed_ms, 2)
            else:
                response.data = {
                    "results": response.data,
                    "_query_time_ms": round(elapsed_ms, 2),
                }
        return response
    return wrapper


# ═════════════════════════════════════════════════════════════════
#  1. FULL-TEXT SEARCH
# ═════════════════════════════════════════════════════════════════

class PgFullTextSearch(APIView):
    """
    PostgreSQL full-text search using ILIKE / trigram.

    LIMITATIONS:
    ─────────────
    • ILIKE does sequential scan – slow on large tables
    • No relevance scoring (results aren't ranked by quality)
    • No stemming ("running" won't match "run")
    • No synonym support
    • No typo tolerance / fuzzy matching
    • No highlighting of matched fragments

    TRY:  GET /api/pg/search/?q=laptop
    TRY:  GET /api/pg/search/?q=runnin   (typo – won't work!)
    """

    @timed_response
    def get(self, request):
        q = request.query_params.get("q", "")
        if not q:
            return Response({"error": "Provide ?q= parameter"}, status=400)

        # PostgreSQL approach: ILIKE across multiple fields
        products = Product.objects.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(short_description__icontains=q)
            | Q(category__name__icontains=q)
            | Q(brand__name__icontains=q)
        ).select_related("category", "brand").prefetch_related("tags")[:10]

        serializer = ProductListSerializer(products, many=True)
        return Response({
            "engine": "PostgreSQL",
            "method": "ILIKE (case-insensitive substring match)",
            "query": q,
            "count": len(serializer.data),
            "note": "No relevance ranking, no fuzzy matching, no stemming",
            "results": serializer.data,
        })


class EsFullTextSearch(APIView):
    """
    Elasticsearch full-text search with relevance scoring.

    ADVANTAGES OVER PostgreSQL:
    ───────────────────────────
    • BM25 relevance scoring (best matches first)
    • Stemming ("running" matches "run")
    • Synonym expansion ("laptop" also finds "notebook")
    • Fuzzy matching (typos tolerated)
    • Highlighting of matching fragments
    • Multi-field boosting (name match > description match)

    TRY:  GET /api/es/search/?q=laptop
    TRY:  GET /api/es/search/?q=runnin   (typo – still works!)
    TRY:  GET /api/es/search/?q=notebook  (synonym for laptop)
    """

    @timed_response
    def get(self, request):
        q = request.query_params.get("q", "")
        if not q:
            return Response({"error": "Provide ?q= parameter"}, status=400)

        search = ProductDocument.search()

        # Multi-match with boosting: name is 3× more important than description
        search = search.query(
            "multi_match",
            query=q,
            fields=[
                "name^3",              # Boost name matches
                "name.synonym^2",      # Synonym matches
                "description",
                "short_description^2",
                "category.name^2",
                "brand.name^2",
            ],
            type="best_fields",
            fuzziness="AUTO",          # Typo tolerance!
        )

        # Add highlighting
        search = search.highlight(
            "name", "description", "short_description",
            fragment_size=150,
            pre_tags=["<mark>"],
            post_tags=["</mark>"],
        )

        search = search[:20]
        response = search.execute()

        serializer = ESProductSerializer(response.hits, many=True)
        return Response({
            "engine": "Elasticsearch",
            "method": "multi_match + BM25 scoring + fuzziness + synonyms",
            "query": q,
            "count": response.hits.total.value,
            "max_score": response.hits.max_score,
            "note": "Results ranked by relevance, typos tolerated, synonyms expanded",
            "results": serializer.data,
        })


# ═════════════════════════════════════════════════════════════════
#  2. AUTOCOMPLETE / SEARCH-AS-YOU-TYPE
# ═════════════════════════════════════════════════════════════════

class PgAutocomplete(APIView):
    """
    PostgreSQL autocomplete using ILIKE prefix matching.

    LIMITATIONS:
    ─────────────
    • Only matches from the start of the entire field (not word-level)
    • No partial word matching inside compound words
    • Gets slow without dedicated index

    TRY:  GET /api/pg/autocomplete/?q=sam
    """

    @timed_response
    def get(self, request):
        q = request.query_params.get("q", "")
        if not q:
            return Response({"error": "Provide ?q= parameter"}, status=400)

        products = Product.objects.filter(
            name__istartswith=q
        ).values_list("name", flat=True)[:10]

        return Response({
            "engine": "PostgreSQL",
            "method": "ILIKE prefix match",
            "query": q,
            "suggestions": list(products),
        })


class EsAutocomplete(APIView):
    """
    Elasticsearch autocomplete using edge_ngram tokenizer.

    ADVANTAGES:
    ───────────
    • Matches any word in the field, not just the start
    • Uses pre-computed edge n-grams for instant results
    • Can combine with scoring to show popular items first

    TRY:  GET /api/es/autocomplete/?q=sam
    TRY:  GET /api/es/autocomplete/?q=pro  (matches "pro" anywhere)
    """

    @timed_response
    def get(self, request):
        q = request.query_params.get("q", "")
        if not q:
            return Response({"error": "Provide ?q= parameter"}, status=400)

        search = ProductDocument.search()
        search = search.query(
            "match",
            name__suggest={  # Uses the autocomplete analyzer
                "query": q,
                "analyzer": "autocomplete_search_analyzer",
            },
        )
        # Boost popular products
        search = search.query(
            "function_score",
            functions=[
                {"field_value_factor": {"field": "rating", "modifier": "log1p", "factor": 2}},
            ],
        )
        search = search[:10]
        response = search.execute()

        return Response({
            "engine": "Elasticsearch",
            "method": "edge_ngram + function_score (popularity boost)",
            "query": q,
            "suggestions": [
                {"name": hit.name, "score": hit.meta.score}
                for hit in response
            ],
        })


# ═════════════════════════════════════════════════════════════════
#  3. FACETED SEARCH / AGGREGATIONS
# ═════════════════════════════════════════════════════════════════

class PgAggregations(APIView):
    """
    PostgreSQL aggregations using GROUP BY.

    LIMITATIONS:
    ─────────────
    • Each aggregation is a separate query or subquery
    • Complex facets require multiple JOINs
    • No histogram bucketing without generate_series
    • Coupling aggregations with filtered search is verbose

    TRY:  GET /api/pg/aggregations/
    TRY:  GET /api/pg/aggregations/?q=wireless
    """

    @timed_response
    def get(self, request):
        q = request.query_params.get("q", "")

        qs = Product.objects.filter(is_active=True)
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        # Multiple separate aggregation queries
        category_facets = (
            qs.values("category__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        brand_facets = (
            qs.values("brand__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        price_stats = qs.aggregate(
            min_price=Min("price"),
            max_price=Max("price"),
            avg_price=Avg("price"),
        )
        rating_stats = qs.aggregate(
            avg_rating=Avg("rating"),
        )

        return Response({
            "engine": "PostgreSQL",
            "method": "Multiple GROUP BY queries + aggregate()",
            "query": q or "(all products)",
            "total_matching": qs.count(),
            "facets": {
                "categories": list(category_facets),
                "brands": list(brand_facets),
                "price_stats": price_stats,
                "rating_stats": rating_stats,
            },
            "note": "Each facet is a separate DB query. No histogram support without raw SQL.",
        })


class EsAggregations(APIView):
    """
    Elasticsearch aggregations — single query, multiple facets.

    ADVANTAGES:
    ───────────
    • ALL facets computed in a single request
    • Built-in histogram bucketing (price ranges)
    • Nested aggregations (avg rating per category)
    • Much faster on large datasets
    • Result count per facet for UI filters

    TRY:  GET /api/es/aggregations/
    TRY:  GET /api/es/aggregations/?q=wireless
    """

    @timed_response
    def get(self, request):
        q = request.query_params.get("q", "")

        search = ProductDocument.search()
        search = search.filter("term", is_active=True)

        if q:
            search = search.query(
                "multi_match",
                query=q,
                fields=["name^3", "description", "category.name"],
                fuzziness="AUTO",
            )

        # ALL aggregations in ONE query!
        search.aggs.bucket("categories", "terms", field="category.name.raw", size=10)
        search.aggs.bucket("brands", "terms", field="brand.name.raw", size=10)
        search.aggs.bucket(
            "price_ranges", "range", field="price",
            ranges=[
                {"key": "Budget (< $50)", "to": 50},
                {"key": "Mid ($50-200)", "from": 50, "to": 200},
                {"key": "Premium ($200-500)", "from": 200, "to": 500},
                {"key": "Luxury ($500+)", "from": 500},
            ],
        )
        search.aggs.bucket(
            "price_histogram", "histogram", field="price", interval=50
        )
        search.aggs.metric("avg_price", "avg", field="price")
        search.aggs.metric("avg_rating", "avg", field="rating")
        search.aggs.bucket("ratings", "terms", field="rating")

        # Nested agg: average price PER category
        search.aggs.bucket(
            "category_prices", "terms", field="category.name.raw"
        ).metric("avg_price", "avg", field="price")

        search = search[:0]  # We only want aggregations, not hits
        response = search.execute()

        return Response({
            "engine": "Elasticsearch",
            "method": "Single query with multiple aggregation buckets",
            "query": q or "(all products)",
            "total_matching": response.hits.total.value,
            "facets": {
                "categories": [
                    {"name": b.key, "count": b.doc_count}
                    for b in response.aggregations.categories.buckets
                ],
                "brands": [
                    {"name": b.key, "count": b.doc_count}
                    for b in response.aggregations.brands.buckets
                ],
                "price_ranges": [
                    {"range": b.key, "count": b.doc_count}
                    for b in response.aggregations.price_ranges.buckets
                ],
                "price_histogram": [
                    {"from": b.key, "count": b.doc_count}
                    for b in response.aggregations.price_histogram.buckets
                    if b.doc_count > 0
                ],
                "avg_price": response.aggregations.avg_price.value,
                "avg_rating": response.aggregations.avg_rating.value,
                "category_avg_prices": [
                    {"category": b.key, "avg_price": round(b.avg_price.value, 2), "count": b.doc_count}
                    for b in response.aggregations.category_prices.buckets
                ],
            },
            "note": "All facets computed in a SINGLE Elasticsearch query!",
        })


# ═════════════════════════════════════════════════════════════════
#  4. FILTERED SEARCH (combining filters + full-text)
# ═════════════════════════════════════════════════════════════════

class PgFilteredSearch(APIView):
    """
    PostgreSQL filtered search.

    TRY:  GET /api/pg/filter/?q=wireless&category=Electronics&min_price=10&max_price=100&min_rating=4
    """

    @timed_response
    def get(self, request):
        q = request.query_params.get("q", "")
        category = request.query_params.get("category", "")
        brand = request.query_params.get("brand", "")
        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")
        min_rating = request.query_params.get("min_rating")
        in_stock = request.query_params.get("in_stock")

        qs = Product.objects.filter(is_active=True).select_related("category", "brand")

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        if category:
            qs = qs.filter(category__name__iexact=category)
        if brand:
            qs = qs.filter(brand__name__iexact=brand)
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if min_rating:
            qs = qs.filter(rating__gte=min_rating)
        if in_stock and in_stock.lower() == "true":
            qs = qs.filter(stock__gt=0)

        serializer = ProductListSerializer(qs[:20], many=True)
        return Response({
            "engine": "PostgreSQL",
            "method": "Django ORM filter chaining",
            "count": qs.count(),
            "note": "Filtering works well in PG, but combined with full-text is weak",
            "results": serializer.data,
        })


class EsFilteredSearch(APIView):
    """
    Elasticsearch filtered search with bool query.

    ADVANTAGES:
    ───────────
    • Filters run in "filter context" (cached, no scoring overhead)
    • Full-text runs in "query context" (scored for relevance)
    • Combining both is natural and fast

    TRY:  GET /api/es/filter/?q=wireless&category=Electronics&min_price=10&max_price=100&min_rating=4
    """

    @timed_response
    def get(self, request):
        q = request.query_params.get("q", "")
        category = request.query_params.get("category", "")
        brand = request.query_params.get("brand", "")
        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")
        min_rating = request.query_params.get("min_rating")
        in_stock = request.query_params.get("in_stock")

        search = ProductDocument.search()

        # Bool query: must (scoring) + filter (non-scoring, cached)
        bool_query = ESQ("bool")

        if q:
            bool_query &= ESQ(
                "multi_match",
                query=q,
                fields=["name^3", "name.synonym^2", "description", "short_description^2"],
                fuzziness="AUTO",
            )

        # Filters (non-scoring → cached → fast)
        filters = [ESQ("term", is_active=True)]
        if category:
            filters.append(ESQ("term", **{"category.name.raw": category}))
        if brand:
            filters.append(ESQ("term", **{"brand.name.raw": brand}))
        if min_price or max_price:
            price_range = {}
            if min_price:
                price_range["gte"] = float(min_price)
            if max_price:
                price_range["lte"] = float(max_price)
            filters.append(ESQ("range", price=price_range))
        if min_rating:
            filters.append(ESQ("range", rating={"gte": float(min_rating)}))
        if in_stock and in_stock.lower() == "true":
            filters.append(ESQ("range", stock={"gt": 0}))

        search = search.query(bool_query)
        for f in filters:
            search = search.filter(f)

        search = search.highlight("name", "description", fragment_size=150)
        search = search[:20]
        response = search.execute()

        serializer = ESProductSerializer(response.hits, many=True)
        return Response({
            "engine": "Elasticsearch",
            "method": "bool query (must + filter context)",
            "count": response.hits.total.value,
            "note": "Filters are cached & not scored. Full-text is scored. Best of both worlds.",
            "results": serializer.data,
        })


# ═════════════════════════════════════════════════════════════════
#  5. SORTING — Multi-field & Relevance
# ═════════════════════════════════════════════════════════════════

class PgSortedSearch(APIView):
    """
    PostgreSQL sorting.

    TRY:  GET /api/pg/sort/?q=phone&sort=price_asc
    TRY:  GET /api/pg/sort/?q=phone&sort=rating_desc
    """

    SORT_MAP = {
        "price_asc": "price",
        "price_desc": "-price",
        "rating_desc": "-rating",
        "newest": "-created_at",
        "name_asc": "name",
    }

    @timed_response
    def get(self, request):
        q = request.query_params.get("q", "")
        sort = request.query_params.get("sort", "newest")

        qs = Product.objects.filter(is_active=True).select_related("category", "brand")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        order_field = self.SORT_MAP.get(sort, "-created_at")
        qs = qs.order_by(order_field)

        serializer = ProductListSerializer(qs[:20], many=True)
        return Response({
            "engine": "PostgreSQL",
            "method": f"ORDER BY {order_field}",
            "note": "PG can sort but CANNOT sort by relevance (no scoring)",
            "results": serializer.data,
        })


class EsSortedSearch(APIView):
    """
    Elasticsearch sorting — including by relevance score.

    ADVANTAGES:
    ───────────
    • Can sort by _score (relevance) — PG cannot
    • Can combine relevance + recency
    • Can do script-based custom sorting

    TRY:  GET /api/es/sort/?q=phone&sort=relevance
    TRY:  GET /api/es/sort/?q=phone&sort=price_asc
    TRY:  GET /api/es/sort/?q=phone&sort=best  (custom: relevance + rating)
    """

    @timed_response
    def get(self, request):
        q = request.query_params.get("q", "")
        sort = request.query_params.get("sort", "relevance")

        search = ProductDocument.search()
        search = search.filter("term", is_active=True)

        if q:
            search = search.query(
                "multi_match",
                query=q,
                fields=["name^3", "description"],
                fuzziness="AUTO",
            )

        if sort == "price_asc":
            search = search.sort("price")
        elif sort == "price_desc":
            search = search.sort("-price")
        elif sort == "rating_desc":
            search = search.sort("-rating")
        elif sort == "newest":
            search = search.sort("-created_at")
        elif sort == "best":
            # Custom scoring: combine relevance + rating + recency
            search = search.query(
                "function_score",
                functions=[
                    {"field_value_factor": {"field": "rating", "modifier": "log1p", "factor": 2}},
                    {"gauss": {"created_at": {"origin": "now", "scale": "30d", "decay": 0.5}}},
                ],
                score_mode="multiply",
            )
        # else: sort by _score (default relevance)

        search = search[:20]
        response = search.execute()

        serializer = ESProductSerializer(response.hits, many=True)
        return Response({
            "engine": "Elasticsearch",
            "method": f"sort={sort}",
            "note": "'best' combines relevance + rating + recency using function_score",
            "results": serializer.data,
        })


# ═════════════════════════════════════════════════════════════════
#  6. GEO SEARCH (ES only — PG needs PostGIS extension)
# ═════════════════════════════════════════════════════════════════

class EsGeoSearch(APIView):
    """
    Elasticsearch geo-distance search.

    Find products from warehouses within X km of a location.
    PostgreSQL would require the PostGIS extension for this.

    TRY:  GET /api/es/geo/?lat=40.7128&lon=-74.0060&distance=100km
          (Products near New York City)
    """

    @timed_response
    def get(self, request):
        lat = request.query_params.get("lat")
        lon = request.query_params.get("lon")
        distance = request.query_params.get("distance", "50km")

        if not lat or not lon:
            return Response(
                {"error": "Provide ?lat=&lon=&distance= parameters"},
                status=400,
            )

        search = ProductDocument.search()
        search = search.filter(
            "geo_distance",
            distance=distance,
            warehouse_location={"lat": float(lat), "lon": float(lon)},
        )
        search = search.sort(
            {"_geo_distance": {
                "warehouse_location": {"lat": float(lat), "lon": float(lon)},
                "order": "asc",
                "unit": "km",
            }}
        )
        search = search[:20]
        response = search.execute()

        results = []
        for hit in response:
            data = ESProductSerializer(hit).data
            # Add distance info from sort value
            if hasattr(hit.meta, "sort") and hit.meta.sort:
                data["distance_km"] = round(hit.meta.sort[0], 2)
            results.append(data)

        return Response({
            "engine": "Elasticsearch",
            "method": "geo_distance filter + sort",
            "center": {"lat": float(lat), "lon": float(lon)},
            "max_distance": distance,
            "count": response.hits.total.value,
            "note": "PG would need PostGIS extension. ES has this built-in.",
            "results": results,
        })


# ═════════════════════════════════════════════════════════════════
#  7. COMPARISON OVERVIEW
# ═════════════════════════════════════════════════════════════════

@api_view(["GET"])
def api_overview(request):
    """List all available API endpoints with descriptions."""
    return Response({
        "message": "PostgreSQL vs Elasticsearch — Product Search API",
        "endpoints": {
            "overview": {
                "GET /api/": "This overview",
            },
            "1_full_text_search": {
                "GET /api/pg/search/?q=laptop": "PostgreSQL ILIKE search",
                "GET /api/es/search/?q=laptop": "Elasticsearch multi_match search",
                "lesson": "ES provides relevance scoring, stemming, synonyms, fuzzy matching",
            },
            "2_autocomplete": {
                "GET /api/pg/autocomplete/?q=sam": "PostgreSQL prefix matching",
                "GET /api/es/autocomplete/?q=sam": "Elasticsearch edge_ngram autocomplete",
                "lesson": "ES matches any word, PG only matches from field start",
            },
            "3_aggregations_facets": {
                "GET /api/pg/aggregations/": "PostgreSQL GROUP BY aggregations",
                "GET /api/es/aggregations/": "Elasticsearch bucket aggregations",
                "lesson": "ES computes ALL facets in one query with histograms",
            },
            "4_filtered_search": {
                "GET /api/pg/filter/?q=wireless&category=Electronics&min_price=10&max_price=100": "PostgreSQL filters",
                "GET /api/es/filter/?q=wireless&category=Electronics&min_price=10&max_price=100": "Elasticsearch bool query",
                "lesson": "ES separates filter context (cached) from query context (scored)",
            },
            "5_sorting": {
                "GET /api/pg/sort/?q=phone&sort=price_asc": "PostgreSQL ORDER BY",
                "GET /api/es/sort/?q=phone&sort=best": "Elasticsearch custom scoring",
                "lesson": "ES can sort by relevance and combine multiple scoring factors",
            },
            "6_geo_search": {
                "GET /api/es/geo/?lat=40.7128&lon=-74.0060&distance=100km": "Elasticsearch geo search",
                "lesson": "Built-in geo support. PG needs PostGIS extension.",
            },
            "7_seed_data": {
                "manage.py command": "python manage.py seed_products --count 500",
            },
        },
    })
