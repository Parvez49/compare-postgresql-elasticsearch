"""
Management command to seed the database with realistic product data.

Usage:
    python manage.py seed_products --count 500
    python manage.py seed_products --count 1000 --clear
"""

import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from faker import Faker

from products.models import Product, Category, Brand, Tag

fake = Faker()

# ─── Realistic Data ─────────────────────────────────────────────
CATEGORIES = [
    ("Electronics", "Phones, laptops, tablets, and accessories"),
    ("Audio", "Headphones, speakers, and audio equipment"),
    ("Computers", "Desktops, laptops, monitors, and peripherals"),
    ("Gaming", "Consoles, games, and gaming accessories"),
    ("Cameras", "Digital cameras, lenses, and photography gear"),
    ("Wearables", "Smartwatches, fitness trackers, and smart glasses"),
    ("Home Appliances", "Kitchen, cleaning, and home electronics"),
    ("Networking", "Routers, switches, and network accessories"),
    ("Storage", "Hard drives, SSDs, and USB drives"),
    ("Software", "Operating systems, productivity, and security software"),
]

BRANDS = [
    ("Samsung", "South Korea"),
    ("Apple", "United States"),
    ("Sony", "Japan"),
    ("LG", "South Korea"),
    ("Dell", "United States"),
    ("HP", "United States"),
    ("Lenovo", "China"),
    ("Asus", "Taiwan"),
    ("Bose", "United States"),
    ("JBL", "United States"),
    ("Canon", "Japan"),
    ("Nikon", "Japan"),
    ("Microsoft", "United States"),
    ("Google", "United States"),
    ("Razer", "United States"),
    ("Logitech", "Switzerland"),
    ("Anker", "China"),
    ("Corsair", "United States"),
    ("Western Digital", "United States"),
    ("Seagate", "United States"),
]

TAGS = [
    "wireless", "bluetooth", "usb-c", "portable", "waterproof",
    "noise-cancelling", "4k", "hdr", "gaming", "professional",
    "budget", "premium", "compact", "lightweight", "fast-charging",
    "smart", "ai-powered", "eco-friendly", "refurbished", "bestseller",
    "new-arrival", "limited-edition", "5g", "wifi-6", "thunderbolt",
]

# Product name templates per category
PRODUCT_TEMPLATES = {
    "Electronics": [
        "{brand} Galaxy S{n} Ultra Smartphone",
        "{brand} {adj} Wireless Charger Pro",
        "{brand} USB-C Hub {n}-in-1",
        "{brand} Smart Power Strip {adj}",
        "{brand} Portable Battery Pack {n}mAh",
    ],
    "Audio": [
        "{brand} {adj} Wireless Headphones Pro",
        "{brand} Noise Cancelling Earbuds {n}",
        "{brand} Portable Bluetooth Speaker {adj}",
        "{brand} Studio Monitor Headphone {n}",
        "{brand} Soundbar {n}.1 Channel {adj}",
    ],
    "Computers": [
        "{brand} {adj} Laptop {n}-inch Display",
        "{brand} ProBook Desktop i{n} Processor",
        "{brand} UltraWide Monitor {n}-inch {adj}",
        "{brand} Mechanical Keyboard {adj} Edition",
        "{brand} Ergonomic Mouse {adj} Pro",
    ],
    "Gaming": [
        "{brand} Gaming Console {adj} Edition",
        "{brand} {adj} Gaming Controller Pro",
        "{brand} RGB Gaming Headset {n}.1",
        "{brand} Gaming Mousepad {adj} XL",
        "{brand} {adj} Gaming Chair Pro Series",
    ],
    "Cameras": [
        "{brand} Mirrorless Camera {n}MP {adj}",
        "{brand} {adj} Action Camera {n}K",
        "{brand} Wide Angle Lens {n}mm {adj}",
        "{brand} Camera Tripod {adj} Carbon",
        "{brand} {adj} Ring Light {n}-inch",
    ],
    "Wearables": [
        "{brand} SmartWatch Series {n} {adj}",
        "{brand} Fitness Tracker {adj} Band",
        "{brand} {adj} Smart Ring Gen {n}",
        "{brand} Smart Glasses {adj} Pro",
        "{brand} Health Monitor Watch {n} {adj}",
    ],
    "Home Appliances": [
        "{brand} {adj} Robot Vacuum Pro {n}",
        "{brand} Smart Air Purifier {adj}",
        "{brand} {adj} Coffee Machine Pro {n}",
        "{brand} Smart Thermostat {adj} Gen {n}",
        "{brand} {adj} Blender {n}-Speed Pro",
    ],
    "Networking": [
        "{brand} WiFi {n} Router {adj} Mesh",
        "{brand} {adj} Network Switch {n}-Port",
        "{brand} Range Extender {adj} AC{n}",
        "{brand} {adj} Ethernet Cable Cat{n}",
        "{brand} VPN Router {adj} Pro",
    ],
    "Storage": [
        "{brand} Portable SSD {n}TB {adj}",
        "{brand} {adj} External HDD {n}TB",
        "{brand} USB Flash Drive {n}GB {adj}",
        "{brand} NAS Storage {n}-Bay {adj}",
        "{brand} Memory Card {n}GB {adj} Speed",
    ],
    "Software": [
        "{brand} {adj} Antivirus {n}-Year License",
        "{brand} Office Suite {adj} Edition",
        "{brand} Cloud Backup {n}TB {adj}",
        "{brand} {adj} VPN Service {n}-Device",
        "{brand} Photo Editor {adj} Pro",
    ],
}

ADJECTIVES = [
    "Ultra", "Pro", "Elite", "Advanced", "Premium", "Epic",
    "Essential", "Classic", "Next-Gen", "Max", "Plus", "Turbo",
]

# US warehouse locations (lat, lon)
WAREHOUSE_LOCATIONS = [
    (40.7128, -74.0060),    # New York
    (34.0522, -118.2437),   # Los Angeles
    (41.8781, -87.6298),    # Chicago
    (29.7604, -95.3698),    # Houston
    (33.4484, -112.0740),   # Phoenix
    (39.7392, -104.9903),   # Denver
    (47.6062, -122.3321),   # Seattle
    (25.7617, -80.1918),    # Miami
    (42.3601, -71.0589),    # Boston
    (37.7749, -122.4194),   # San Francisco
]


class Command(BaseCommand):
    help = "Seed database with realistic product data for PG vs ES comparison"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=500, help="Number of products")
        parser.add_argument("--clear", action="store_true", help="Clear existing data first")

    def handle(self, *args, **options):
        count = options["count"]
        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            Product.objects.all().delete()
            Tag.objects.all().delete()
            Brand.objects.all().delete()
            Category.objects.all().delete()

        # Create categories
        self.stdout.write("Creating categories...")
        categories = []
        for name, desc in CATEGORIES:
            cat, _ = Category.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name), "description": desc},
            )
            categories.append(cat)

        # Create brands
        self.stdout.write("Creating brands...")
        brands = []
        for name, country in BRANDS:
            brand, _ = Brand.objects.get_or_create(
                name=name,
                defaults={"country": country},
            )
            brands.append(brand)

        # Create tags
        self.stdout.write("Creating tags...")
        tags = []
        for name in TAGS:
            tag, _ = Tag.objects.get_or_create(name=name)
            tags.append(tag)

        # Create products
        self.stdout.write(f"Creating {count} products...")
        products_created = 0
        used_slugs = set(Product.objects.values_list("slug", flat=True))

        for i in range(count):
            category = random.choice(categories)
            brand = random.choice(brands)
            adj = random.choice(ADJECTIVES)
            n = random.randint(2, 99)

            templates = PRODUCT_TEMPLATES.get(category.name, PRODUCT_TEMPLATES["Electronics"])
            template = random.choice(templates)
            name = template.format(brand=brand.name, adj=adj, n=n)

            slug = slugify(name)
            # Ensure unique slug
            if slug in used_slugs:
                slug = f"{slug}-{fake.unique.random_int(min=1000, max=99999)}"
            if slug in used_slugs:
                continue
            used_slugs.add(slug)

            price = Decimal(str(round(random.uniform(9.99, 2999.99), 2)))
            warehouse = random.choice(WAREHOUSE_LOCATIONS)

            product = Product.objects.create(
                name=name,
                slug=slug,
                description=fake.paragraph(nb_sentences=5),
                short_description=fake.sentence(nb_words=12),
                price=price,
                discount_percent=random.choice([0, 0, 0, 5, 10, 15, 20, 25, 30, 50]),
                stock=random.randint(0, 500),
                is_active=random.random() > 0.1,  # 90% active
                rating=round(random.uniform(1.0, 5.0), 1),
                review_count=random.randint(0, 2000),
                category=category,
                brand=brand,
                warehouse_lat=warehouse[0] + random.uniform(-0.5, 0.5),
                warehouse_lon=warehouse[1] + random.uniform(-0.5, 0.5),
            )

            # Add 1-5 random tags
            product_tags = random.sample(tags, k=random.randint(1, 5))
            product.tags.set(product_tags)

            products_created += 1
            if products_created % 100 == 0:
                self.stdout.write(f"  Created {products_created}/{count} products...")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Created {products_created} products, "
                f"{len(categories)} categories, {len(brands)} brands, {len(tags)} tags.\n"
                f"\nNext steps:\n"
                f"  1. Rebuild ES index:  python manage.py search_index --rebuild\n"
                f"  2. Try the API:       http://localhost:8000/api/\n"
            )
        )
