from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Category(models.Model):
    """Product category – demonstrates relational joins."""

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(models.Model):
    """Brand/manufacturer – another FK for join demonstration."""

    name = models.CharField(max_length=200, unique=True)
    country = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    """Tags – M2M relationship to show nested Elasticsearch objects."""

    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Central model – stored in PostgreSQL AND indexed in Elasticsearch.

    This model is intentionally rich to demonstrate:
    - Full-text search across multiple fields
    - Numeric range filters (price, rating)
    - Faceted navigation (category, brand, tags)
    - Autocomplete / suggest
    - Geo-fields (warehouse location)
    """

    # ── Basic fields ────────────────────────────────────────────
    name = models.CharField(max_length=500)
    slug = models.SlugField(max_length=500, unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)

    # ── Pricing ─────────────────────────────────────────────────
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # ── Stock ───────────────────────────────────────────────────
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # ── Ratings ─────────────────────────────────────────────────
    rating = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    review_count = models.PositiveIntegerField(default=0)

    # ── Relations ───────────────────────────────────────────────
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )
    brand = models.ForeignKey(
        Brand, on_delete=models.CASCADE, related_name="products"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="products")

    # ── Warehouse location (for geo_point demo) ─────────────────
    warehouse_lat = models.FloatField(null=True, blank=True)
    warehouse_lon = models.FloatField(null=True, blank=True)

    # ── Timestamps ──────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # PostgreSQL indexes for comparison
            models.Index(fields=["name"], name="idx_product_name"),
            models.Index(fields=["price"], name="idx_product_price"),
            models.Index(fields=["rating"], name="idx_product_rating"),
            models.Index(fields=["category"], name="idx_product_category"),
            models.Index(fields=["brand"], name="idx_product_brand"),
            models.Index(fields=["is_active"], name="idx_product_active"),
        ]

    def __str__(self):
        return self.name

    @property
    def final_price(self):
        """Price after discount."""
        return float(self.price) * (1 - self.discount_percent / 100)
