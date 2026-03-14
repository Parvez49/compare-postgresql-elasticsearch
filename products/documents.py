from django_elasticsearch_dsl import Document, fields, Index
from django_elasticsearch_dsl.registries import registry
from .models import Product, Category, Brand, Tag


# ─── Index Settings ─────────────────────────────────────────────
# These settings demonstrate Elasticsearch analysis capabilities
# that PostgreSQL cannot match natively.

PRODUCT_INDEX = Index("products")
PRODUCT_INDEX.settings(
    number_of_shards=1,
    number_of_replicas=0,
    # Custom analysis chain – THIS is what makes ES powerful for search
    analysis={
        "analyzer": {
            # Standard analyzer with custom stopwords
            "default_analyzer": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "asciifolding", "english_stemmer", "english_stop"],
            },
            # Edge n-gram for autocomplete (as-you-type)
            "autocomplete_analyzer": {
                "type": "custom",
                "tokenizer": "autocomplete_tokenizer",
                "filter": ["lowercase", "asciifolding"],
            },
            # Search analyzer for autocomplete (no edge_ngram on search side)
            "autocomplete_search_analyzer": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "asciifolding"],
            },
            # Synonym analyzer (e.g., "laptop" = "notebook")
            "synonym_analyzer": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "product_synonyms"],
            },
        },
        "tokenizer": {
            "autocomplete_tokenizer": {
                "type": "edge_ngram",
                "min_gram": 2,
                "max_gram": 15,
                "token_chars": ["letter", "digit"],
            },
        },
        "filter": {
            "english_stemmer": {"type": "stemmer", "language": "english"},
            "english_stop": {"type": "stop", "stopwords": "_english_"},
            "product_synonyms": {
                "type": "synonym",
                "synonyms": [
                    "laptop, notebook, portable computer",
                    "phone, mobile, smartphone, cellphone",
                    "headphone, earphone, headset",
                    "tv, television, monitor, display, screen",
                ],
            },
        },
    },
)


# @PRODUCT_INDEX.doc_type
@registry.register_document
@PRODUCT_INDEX.document
class ProductDocument(Document):
    """
    Elasticsearch document for Product model.

    KEY LEARNING POINTS:
    ────────────────────
    1. Each field type maps to an ES field type (text, keyword, integer, etc.)
    2. 'text' fields are analyzed (tokenized, stemmed) → good for full-text search
    3. 'keyword' fields are exact match → good for filtering/aggregations
    4. A single field can have multiple sub-fields (multi-field mapping)
    5. Nested/Object fields handle relationships without JOINs
    """

    # ── Text fields with multiple analyzers ─────────────────────
    name = fields.TextField(
        analyzer="default_analyzer",
        fields={
            "raw": fields.KeywordField(),                    # Exact match / sorting
            "suggest": fields.TextField(                     # Autocomplete
                analyzer="autocomplete_analyzer",
                search_analyzer="autocomplete_search_analyzer",
            ),
            "synonym": fields.TextField(                     # Synonym search
                analyzer="synonym_analyzer",
            ),
        },
    )
    description = fields.TextField(analyzer="default_analyzer")
    short_description = fields.TextField(analyzer="default_analyzer")
    slug = fields.KeywordField()

    # ── Numeric fields ──────────────────────────────────────────
    price = fields.FloatField()
    discount_percent = fields.IntegerField()
    final_price = fields.FloatField()
    stock = fields.IntegerField()
    rating = fields.FloatField()
    review_count = fields.IntegerField()

    # ── Boolean ─────────────────────────────────────────────────
    is_active = fields.BooleanField()

    # ── Date ────────────────────────────────────────────────────
    created_at = fields.DateField()
    updated_at = fields.DateField()

    # ── Nested object: Category (denormalized – no JOIN needed!) ─
    category = fields.ObjectField(
        properties={
            "id": fields.IntegerField(),
            "name": fields.TextField(
                analyzer="default_analyzer",
                fields={"raw": fields.KeywordField()},
            ),
            "slug": fields.KeywordField(),
        }
    )

    # ── Nested object: Brand ────────────────────────────────────
    brand = fields.ObjectField(
        properties={
            "id": fields.IntegerField(),
            "name": fields.TextField(
                analyzer="default_analyzer",
                fields={"raw": fields.KeywordField()},
            ),
            "country": fields.KeywordField(),
        }
    )

    # ── Nested array: Tags ──────────────────────────────────────
    tags = fields.NestedField(
        properties={
            "id": fields.IntegerField(),
            "name": fields.KeywordField(),
        }
    )

    # ── Geo point: warehouse location ───────────────────────────
    warehouse_location = fields.GeoPointField()

    # class Index:
    #     name = "products"

    class Django:
        model = Product
        # Fields from the model to watch for auto-sync
        related_models = [Category, Brand, Tag]

    def get_queryset(self):
        """Optimize queryset for indexing."""
        return super().get_queryset().select_related("category", "brand").prefetch_related("tags")
    
    def get_indexing_queryset(self):
        return self.get_queryset().iterator(chunk_size=500)

    def get_instances_from_related(self, related_instance):
        """Auto-update index when related models change."""
        if isinstance(related_instance, Category):
            return related_instance.products.all()
        elif isinstance(related_instance, Brand):
            return related_instance.products.all()
        elif isinstance(related_instance, Tag):
            return related_instance.products.all()
        return super().get_instances_from_related(related_instance)

    def prepare_final_price(self, instance):
        return instance.final_price

    def prepare_category(self, instance):
        return {
            "id": instance.category.id,
            "name": instance.category.name,
            "slug": instance.category.slug,
        }

    def prepare_brand(self, instance):
        return {
            "id": instance.brand.id,
            "name": instance.brand.name,
            "country": instance.brand.country,
        }

    def prepare_tags(self, instance):
        return [{"id": tag.id, "name": tag.name} for tag in instance.tags.all()]

    def prepare_warehouse_location(self, instance):
        if instance.warehouse_lat and instance.warehouse_lon:
            return {"lat": instance.warehouse_lat, "lon": instance.warehouse_lon}
        return None
