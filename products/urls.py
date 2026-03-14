from django.urls import path
from . import views

urlpatterns = [
    # Overview
    path("", views.api_overview, name="api-overview"),

    # ── 1. Full-Text Search ─────────────────────────────────────
    path("pg/search/", views.PgFullTextSearch.as_view(), name="pg-search"),
    path("es/search/", views.EsFullTextSearch.as_view(), name="es-search"),

    # ── 2. Autocomplete ─────────────────────────────────────────
    path("pg/autocomplete/", views.PgAutocomplete.as_view(), name="pg-autocomplete"),
    path("es/autocomplete/", views.EsAutocomplete.as_view(), name="es-autocomplete"),

    # ── 3. Aggregations / Facets ────────────────────────────────
    path("pg/aggregations/", views.PgAggregations.as_view(), name="pg-aggregations"),
    path("es/aggregations/", views.EsAggregations.as_view(), name="es-aggregations"),

    # ── 4. Filtered Search ──────────────────────────────────────
    path("pg/filter/", views.PgFilteredSearch.as_view(), name="pg-filter"),
    path("es/filter/", views.EsFilteredSearch.as_view(), name="es-filter"),

    # ── 5. Sorting ──────────────────────────────────────────────
    path("pg/sort/", views.PgSortedSearch.as_view(), name="pg-sort"),
    path("es/sort/", views.EsSortedSearch.as_view(), name="es-sort"),

    # ── 6. Geo Search ──────────────────────────────────────────
    path("es/geo/", views.EsGeoSearch.as_view(), name="es-geo"),
]
