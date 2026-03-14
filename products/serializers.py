from rest_framework import serializers
from .models import Product, Category, Brand, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description"]


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "country"]


class ProductSerializer(serializers.ModelSerializer):
    """Full product serializer for PostgreSQL-backed views."""

    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    final_price = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "short_description",
            "price",
            "discount_percent",
            "final_price",
            "stock",
            "is_active",
            "rating",
            "review_count",
            "category",
            "brand",
            "tags",
            "warehouse_lat",
            "warehouse_lon",
            "created_at",
            "updated_at",
        ]


class ProductListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True)
    final_price = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "price",
            "final_price",
            "rating",
            "review_count",
            "category_name",
            "brand_name",
            "is_active",
            "stock",
        ]


# ─── Elasticsearch result serializer ────────────────────────────
class ESProductSerializer(serializers.Serializer):
    """
    Serializer for Elasticsearch results.
    This does NOT hit the database. data comes from ES index.
    """

    id = serializers.IntegerField(source="meta.id")

    name = serializers.CharField()
    slug = serializers.CharField()
    description = serializers.CharField()
    short_description = serializers.CharField()
    price = serializers.FloatField()
    discount_percent = serializers.IntegerField()
    final_price = serializers.FloatField()
    stock = serializers.IntegerField()
    is_active = serializers.BooleanField()
    rating = serializers.FloatField()
    review_count = serializers.IntegerField()

    category = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    created_at = serializers.DateTimeField()

    score = serializers.SerializerMethodField()
    highlights = serializers.SerializerMethodField()

    def get_category(self, obj):
        c = getattr(obj, "category", None)
        if not c:
            return None
        return {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
        }

    def get_brand(self, obj):
        b = getattr(obj, "brand", None)
        if not b:
            return None
        return {
            "id": b.id,
            "name": b.name,
            "country": b.country,
        }

    def get_tags(self, obj):
        tags = getattr(obj, "tags", [])
        return [{"id": t.id, "name": t.name} for t in tags]
    
    def get_score(self, obj):
        """Relevance score from Elasticsearch."""
        return getattr(obj.meta, "score", None)

    def get_highlights(self, obj):
        """Highlighted matching fragments."""
        highlight = getattr(obj.meta, "highlight", None)
        if highlight:
            return {field: list(fragments) for field, fragments in highlight.to_dict().items()}
        return {}
