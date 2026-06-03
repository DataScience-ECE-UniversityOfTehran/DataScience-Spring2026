#!/usr/bin/env python3
"""
Ashpaz Producer
- Loads restaurants from CSV
- Generates realistic orders with controlled randomness
- Injects small % of errors
- Simulates user spam (some users order much more frequently)
- Produces to Kafka topic: ashpaz.order
"""

import os
import csv
import ast
import json
import time
import uuid
import random
import logging
import datetime
import re
from collections import namedtuple
from confluent_kafka import Producer

# Logging configuration
# ------------------------------
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")

# Config (env vars)
# ------------------------------
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "ashpaz.order")
CSV_PATH = os.getenv("RESTAURANT_CSV", "zomato.csv")

EVENT_RATE = float(os.getenv("EVENT_RATE", 800))
PEAK_MULTIPLIER = float(os.getenv("PEAK_MULTIPLIER", 3.0))
ERROR_RATE = float(os.getenv("ERROR_RATE", 0.01))
INVALID_PHONE_RATE = float(os.getenv("INVALID_PHONE_RATE", 0.01))
PRICE_ERROR_RATE = float(os.getenv("PRICE_ERROR_RATE", 0.03))
TIME_ACCELERATION = float(os.getenv("TIME_ACCELERATION", 5))
MENU_VIOLATION_RATE = float(os.getenv("MENU_VIOLATION_RATE", 0.07))

SPAM_USER_COUNT = int(os.getenv("SPAM_USER_COUNT", 0))
NORMAL_USER_COUNT = int(os.getenv("NORMAL_USER_COUNT", 500))
SPAM_RATE_MULTIPLIER = float(os.getenv("SPAM_RATE_MULTIPLIER", 8))

LOCATION_ANOMALY_RATE = float(os.getenv("LOCATION_ANOMALY_RATE", 0.007))

class UserPool:
    def __init__(self, normal_count, spam_count, spam_multiplier, cities):
        self.normal_count = normal_count
        self.all_users = [f"user_{i:06d}" for i in range(
            normal_count + spam_count)]
        self.weights = [1.0] * normal_count + [spam_multiplier] * spam_count

        # Assign a home city to each user at creation time
        self.user_cities = {user: random.choice(
            cities) for user in self.all_users}

    def get_random_user(self):
        chosen = random.choices(self.all_users, weights=self.weights, k=1)[0]
        # MODIFIED: Returns the user_id AND their assigned home_city
        return chosen, self.user_cities[chosen]


Restaurant = namedtuple("Restaurant", [
    "restaurant_id", "name", "online_order", "book_table",
    "rate", "votes", "phone_numbers", "city", "cuisines",
    "approx_cost", "menu_items", "menu_catalog"
])

def parse_rate(rate_str: str) -> float:
    try:
        if not rate_str or "NEW" in rate_str or "-" in rate_str:
            return 3.5
        return float(rate_str.split("/")[0].strip())
    except Exception:
        return 3.5


def parse_votes(votes_str: str) -> int:
    try:
        return int(votes_str)
    except Exception:
        return 50


def parse_approx_cost(cost_str: str) -> int:
    try:
        return int(cost_str.replace(",", "").strip())
    except Exception:
        return 600


def parse_menu(menu_str: str):
    try:
        menu = ast.literal_eval(menu_str)
        if not isinstance(menu, list):
            return []
        return menu
    except Exception:
        return []


def extract_phones(phone_str: str):
    if not phone_str:
        return []
    parts = re.split(r"[\n,]+", phone_str)
    phones = [p.strip() for p in parts if p.strip()]
    return phones


def normalize_phone(phone: str) -> str:
    return re.sub(r"\s+", "", phone)


def generate_valid_phone():
    if random.random() < 0.5:
        return "+91" + str(random.randint(6000000000, 9999999999))
    return "080" + str(random.randint(20000000, 99999999))


def generate_invalid_phone():
    options = [
        "091" + str(random.randint(10000000, 99999999)),
        "07" + str(random.randint(10000000, 99999999)),
        "12345",
        "++91" + str(random.randint(100000000, 999999999)),
    ]
    return random.choice(options)


def demand_factor(event_time: datetime.datetime) -> float:
    hour = event_time.hour
    if 8 <= hour < 11:
        return 0.6
    if 12 <= hour < 15:
        return 1.0 * PEAK_MULTIPLIER
    if 19 <= hour < 22:
        return 1.2 * PEAK_MULTIPLIER
    if 23 <= hour or hour < 6:
        return 0.3
    return 1.0


def build_menu_catalog(menu_items, cuisines, approx_cost):
    catalog = {}
    if not cuisines:
        cuisines = ["Misc"]
    for item in menu_items:
        low = max(50, int(approx_cost * 0.15))
        high = max(low + 10, int(approx_cost * 0.4))
        catalog[item] = {
            "unit_price": round(random.uniform(low, high), 2),
            "category": random.choice(cuisines)
        }
    return catalog


def load_restaurants(csv_path: str):
    restaurants = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rid = 1
        for row in reader:
            name = row.get("name", "").strip()
            if not name:
                continue

            online_order = row.get(
                "online_order", "No").strip().lower() == "yes"
            book_table = row.get("book_table", "No").strip().lower() == "yes"
            rate = parse_rate(row.get("rate", ""))
            votes = parse_votes(row.get("votes", "0"))
            phones = extract_phones(row.get("phone", ""))

            city = row.get("listed_in(city)", "").strip()

            cuisines = [c.strip() for c in row.get(
                "cuisines", "").split(",") if c.strip()]
            approx_cost = parse_approx_cost(
                row.get("approx_cost(for two people)", "600"))
            menu_items = parse_menu(row.get("menu_item", ""))

            if len(menu_items) >= 5:
                menu_items = menu_items[:5]
            else:
                while len(menu_items) < 5:
                    menu_items.append(f"Chef Special {len(menu_items)+1}")

            catalog = build_menu_catalog(menu_items, cuisines, approx_cost)

            restaurants.append(Restaurant(
                restaurant_id=rid,
                name=name,
                online_order=online_order,
                book_table=book_table,
                rate=rate,
                votes=votes,
                phone_numbers=phones,
                city=city,
                cuisines=cuisines,
                approx_cost=approx_cost,
                menu_items=menu_items,
                menu_catalog=catalog
            ))
            rid += 1
    return restaurants


def weighted_choice(restaurants):
    weights = [max(1.0, r.rate) * max(1, r.votes) for r in restaurants]
    return random.choices(restaurants, weights=weights, k=1)[0]


def basket_size_for_time(event_time, request_table):
    hour = event_time.hour
    if 12 <= hour < 15:
        size = random.randint(1, 2)
    elif 19 <= hour < 22:
        size = random.randint(2, 4)
    else:
        size = random.randint(1, 2)

    if request_table:
        size += 1
    return min(size, 5)


def is_bread_or_drink(item_name: str):
    keywords = ["bread", "roti", "naan", "paratha", "kulcha",
                "drink", "lassi", "tea", "coffee", "juice", "soda"]
    n = item_name.lower()
    return any(k in n for k in keywords)


def generate_order(restaurant: Restaurant, event_time: datetime.datetime, user_id: str):
    order_id = str(uuid.uuid4())

    if restaurant.phone_numbers:
        base_phone = normalize_phone(random.choice(restaurant.phone_numbers))
    else:
        base_phone = generate_valid_phone()

    if random.random() < INVALID_PHONE_RATE:
        phone = generate_invalid_phone()
    else:
        phone = base_phone
        if not (phone.startswith("+91") or phone.startswith("080")):
            phone = generate_valid_phone()

    request_online = random.random() > 0.3
    request_table = random.random() > 0.8
    if request_table and request_online:
        tie_breaker = random.random() > 0.7
        request_table = tie_breaker
        request_online = not tie_breaker

    if random.random() < ERROR_RATE:
        request_online = True
        request_table = True

    size = basket_size_for_time(event_time, request_table)
    menu = restaurant.menu_items
    items = random.sample(menu, k=size)

    if random.random() < MENU_VIOLATION_RATE:
        items[0] = "Unlisted Mystery Dish"

    order_items = []
    total_price = 0.0
    for item in items:
        if item in restaurant.menu_catalog:
            meta = restaurant.menu_catalog[item]
            unit_price = meta["unit_price"]
            category = meta["category"]
        else:
            unit_price = round(random.uniform(100, 500), 2)
            category = "Unknown"

        quantity = 1
        if is_bread_or_drink(item):
            quantity = random.randint(2, 4)

        order_items.append({
            "food_item": item,
            "category": category,
            "unit_price": unit_price,
            "quantity": quantity
        })
        total_price += unit_price * quantity

    if random.random() < PRICE_ERROR_RATE:
        mode = random.choice(["wrong", "negative", "huge"])
        if mode == "wrong":
            total_price = round(total_price * random.uniform(0.5, 1.5), 2)
        elif mode == "negative":
            total_price = -abs(total_price)
        elif mode == "huge":
            total_price = total_price * 50

    order = {
        "order_id": order_id,
        "user_id": user_id,
        "restaurant_id": restaurant.restaurant_id,
        "restaurant_name": restaurant.name,
        "restaurant_city": restaurant.city,
        "cuisines": restaurant.cuisines,
        "phone_number": phone,
        "request_online": bool(request_online),
        "request_table": bool(request_table),
        "order_time": event_time.replace(tzinfo=datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "items": order_items,
        "order_price": round(total_price, 2)
    }
    return order


def delivery_report(err, msg):
    if err is not None:
        logging.error(f"Delivery failed: {err}")
    else:
        logging.debug(f"Delivered to {msg.topic()} [{msg.partition()}]")


def main():
    restaurants = load_restaurants(CSV_PATH)
    if not restaurants:
        raise RuntimeError("No restaurants loaded. Check CSV_PATH.")

    logging.info(f"Loaded {len(restaurants)} restaurants.")

    unique_cities = list(set(r.city for r in restaurants if r.city))
    if not unique_cities:
        unique_cities = ["Unknown City"]

    restaurants_by_city = {}
    for r in restaurants:
        restaurants_by_city.setdefault(r.city, []).append(r)

    user_pool = UserPool(NORMAL_USER_COUNT, SPAM_USER_COUNT,
                         SPAM_RATE_MULTIPLIER, unique_cities)

    producer = Producer({"bootstrap.servers": KAFKA_BROKER})

    simulated_time = datetime.datetime.utcnow().replace(
        minute=0, second=0, microsecond=0)

    logging.info("Starting order generation...")

    while True:
        factor = demand_factor(simulated_time)
        lambda_per_sec = (EVENT_RATE * factor * TIME_ACCELERATION) / 60.0
        wait = random.expovariate(
            lambda_per_sec) if lambda_per_sec > 0 else 1.0

        time.sleep(wait)
        simulated_time += datetime.timedelta(minutes=wait * TIME_ACCELERATION)

        user_id, home_city = user_pool.get_random_user()

        if random.random() < LOCATION_ANOMALY_RATE and len(unique_cities) > 1:
            other_cities = [c for c in unique_cities if c != home_city]
            target_city = random.choice(other_cities)
        else:
            target_city = home_city

        available_restaurants = restaurants_by_city.get(
            target_city, restaurants)
        restaurant = weighted_choice(available_restaurants)

        order = generate_order(restaurant, simulated_time, user_id)
        producer.produce(
            TOPIC,
            key=order["order_id"],
            value=json.dumps(order),
            callback=delivery_report
        )
        producer.poll(0)


if __name__ == "__main__":
    main()
