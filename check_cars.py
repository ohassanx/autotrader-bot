#!/usr/bin/env python3
"""
AutoTrader Car Checker
Monitors AutoTrader UK for new car listings matching specific criteria.
Sends Telegram notifications when new cars are found.
"""
import os
import json
import requests
from typing import Optional, Set, Dict, List
from pathlib import Path
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import re

BOT_TOKEN: Optional[str] = None
CHAT_ID: Optional[str] = None

# File to store previously seen car IDs
STATE_FILE = Path(__file__).parent / "seen_cars.json"

# Default search parameters - can be customized
DEFAULT_MAKE = "BMW"
DEFAULT_MODEL = "3 Series"
DEFAULT_POSTCODE = "E15 4EQ"
DEFAULT_RADIUS = 150000  # Large radius to cover all of the UK


def startup():
    """Load environment variables"""
    global BOT_TOKEN, CHAT_ID
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    CHAT_ID = os.environ.get("CHAT_ID")
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("BOT_TOKEN and CHAT_ID environment variables must be set.")


def notify(msg: str):
    """Send Telegram notification"""
    startup()

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = None
    try:
        response = requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        print("✓ Notification sent successfully")
    except Exception as e:
        print("Failed to send Telegram message:", e)
        if response is not None:
            print("Telegram response status:", response.status_code)
            print("Telegram response body:", response.text)
        raise


def load_seen_cars() -> Set[str]:
    """Load previously seen car IDs from state file"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get("car_ids", []))
        except Exception as e:
            print(f"Warning: Could not load state file: {e}")
            return set()
    return set()


def save_seen_cars(car_ids: Set[str]):
    """Save seen car IDs to state file"""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({"car_ids": list(car_ids)}, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save state file: {e}")


def url_constructor(make: str, model: str, postcode: str = DEFAULT_POSTCODE, radius: int = DEFAULT_RADIUS) -> str:
    """Construct the base search URL for AutoTrader with specific filters:
    - Year 2020 and above
    - Price under £15,000
    - Mileage under 80k miles
    - Automatic transmission only
    - Exclude write-offs
    """
    base = "https://www.autotrader.co.uk/car-search?"
    params = {
        "sort": "sponsored",
        "radius": radius,
        "postcode": postcode,
        "onesearchad": ["Used", "Nearly New", "New"],
        "make": make,
        "model": model,
        "year-from": 2020,  # 2020 and newer only
        "price-to": 15000,  # Under £15,000
        "maximum-mileage": 80000,  # Under 80k miles
        "transmission": "Automatic",  # Automatic only
        "exclude-writeoff-categories": "on",  # Exclude write-offs
        "page": "",
    }
    return base + urlencode(params, doseq=True)


def bs_setup(url: str) -> BeautifulSoup:
    """Fetch url and return a BeautifulSoup parser."""
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}, timeout=10)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_pages(url: str) -> int:
    """Return the total number of result pages for the base URL."""
    try:
        soup = bs_setup(url)
        page_number = soup.find("li", attrs={"class": "paginationMini__count"})
        if page_number:
            search_string = str(page_number.get_text)
            match = re.search(r"(\d+)(?!.*\d)", search_string)
            if match:
                num_of_pages = match.group(1)
                print(f"Found {num_of_pages} pages of results...")
                return int(num_of_pages)

        # If pagination not found, assume 1 page
        print("Could not find pagination, assuming 1 page")
        return 1
    except Exception as e:
        print(f"Error getting the number of pages: {e}")
        return 1


def extract_car_id(title_element) -> Optional[str]:
    """Extract a unique car ID from the listing.

    We'll use the title text + a hash of the title as the ID.
    This isn't perfect but should work for tracking new listings.
    """
    if title_element:
        title_text = title_element.get_text("|", strip=True)
        # Create a simple hash-like ID from the title
        return str(hash(title_text))
    return None


def is_writeoff(car_details: Dict) -> bool:
    """Check if a car is a write-off by examining its description and details.

    Returns True if the car appears to be a write-off (should be excluded).
    """
    writeoff_keywords = [
        "write-off", "writeoff", "write off",
        "cat s", "cat n", "cat d", "cat c", "cat b", "cat a",
        "category s", "category n", "category d", "category c",
        "salvage", "damaged", "insurance write",
        "accident damage", "repaired damage"
    ]

    # Check description, attention grabber, and details
    text_to_check = " ".join([
        car_details.get("description", "").lower(),
        car_details.get("attention_grabber", "").lower(),
        car_details.get("details", "").lower(),
        car_details.get("title", "").lower()
    ])

    for keyword in writeoff_keywords:
        if keyword in text_to_check:
            print(f"  ⚠️ Excluding car due to keyword: '{keyword}'")
            return True

    return False


def fetch_autotrader_cars(make: str, model: str, postcode: str = DEFAULT_POSTCODE, radius: int = DEFAULT_RADIUS) -> Dict[str, Dict]:
    """
    Fetch current car listings from AutoTrader

    Returns a dict mapping car_id -> car_details
    """
    print(f"Searching AutoTrader for {make} {model}...")

    built_url = url_constructor(make, model, postcode, radius)
    cars = {}

    try:
        pagination_value = get_pages(built_url)
        print(f"Parsing {pagination_value} page(s) of results...")

        for page in range(1, min(pagination_value + 1, 6)):  # Limit to 5 pages max
            print(f"Fetching page {page}...")
            page_url = f"{built_url}{page}"
            soup = bs_setup(page_url)

            titles = soup.find_all("h2", attrs={"class": "listing-title"})
            details = soup.find_all("ul", attrs={"class": "listing-key-specs"})
            costs = soup.find_all("div", attrs={"class": "vehicle-price"})
            descriptions = soup.find_all("p", attrs={"class": "listing-description"})
            atten_grabbers = soup.find_all("p", attrs={"class": "listing-attention-grabber"})

            for i, (title, detail, cost, description, atten_grabber) in enumerate(zip(
                titles, details, costs, descriptions, atten_grabbers
            )):
                if all([title, detail, cost, description, atten_grabber]):
                    car_id = extract_car_id(title)
                    if car_id:
                        # Try to extract URL from title link
                        car_url = ""
                        title_link = title.find("a")
                        if title_link and title_link.get("href"):
                            car_url = "https://www.autotrader.co.uk" + title_link.get("href")

                        car_details = {
                            "title": title.get_text("|", strip=True),
                            "details": detail.get_text("|", strip=True),
                            "cost": cost.get_text(strip=True),
                            "description": description.get_text("|", strip=True),
                            "attention_grabber": atten_grabber.get_text("|", strip=True),
                            "url": car_url
                        }

                        # Filter out write-offs
                        if not is_writeoff(car_details):
                            cars[car_id] = car_details
                        else:
                            print(f"  Filtered out: {car_details['title']}")

        print(f"Found {len(cars)} total listings")
        return cars

    except Exception as e:
        print(f"Error fetching from AutoTrader: {e}")
        import traceback
        traceback.print_exc()
        return {}


def format_car_notification(new_car_ids: Set[str], all_cars: Dict[str, Dict], make: str, model: str) -> List[str]:
    """Format notification message for new cars

    Returns a list of messages (split if too long for Telegram's 4096 char limit)
    """
    messages = []

    if len(new_car_ids) == 0:
        return messages

    # Header
    header = f"🚗 New AutoTrader Alert!\n\n{len(new_car_ids)} new {make} {model}(s) found:\n"
    header += f"\n{'='*40}\n"

    current_msg = header
    car_count = 0

    for car_id in sorted(new_car_ids):
        car = all_cars.get(car_id, {})

        # Format car details
        car_info = f"\n"

        # Title
        title = car.get("title", "Unknown")
        car_info += f"📍 {title}\n"

        # Details (year, mileage, etc.)
        details = car.get("details", "")
        if details:
            car_info += f"   {details}\n"

        # Price
        cost = car.get("cost", "N/A")
        if cost:
            car_info += f"   💰 {cost}\n"

        # Description
        description = car.get("description", "")
        if description:
            car_info += f"   📝 {description}\n"

        # Attention grabber (e.g., "Great price", "Low mileage")
        attention = car.get("attention_grabber", "")
        if attention:
            car_info += f"   ⭐ {attention}\n"

        # URL
        url = car.get("url", "")
        if url:
            car_info += f"   🔗 {url}\n"

        car_info += f"\n{'='*40}\n"

        # Check if adding this car would exceed Telegram's limit (4096 chars)
        if len(current_msg + car_info) > 4000:
            # Save current message and start a new one
            messages.append(current_msg)
            current_msg = f"🚗 Continued ({car_count + 1}/{len(new_car_ids)})...\n\n"
            current_msg += car_info
        else:
            current_msg += car_info

        car_count += 1

    # Add footer with search criteria
    footer = f"\n📋 Search Criteria:\n"
    footer += f"• Make/Model: {make} {model}\n"
    footer += f"• Year: 2020 and newer\n"
    footer += f"• Price: Under £15,000\n"
    footer += f"• Mileage: Under 80,000 miles\n"
    footer += f"• Transmission: Automatic only\n"
    footer += f"• Condition: No write-offs\n"

    # Check if footer fits in current message
    if len(current_msg + footer) > 4000:
        messages.append(current_msg)
        messages.append(footer)
    else:
        current_msg += footer
        messages.append(current_msg)

    return messages


def main():
    """Main execution function"""
    print("="*60)
    print("AUTOTRADER CAR CHECKER")
    print("="*60)

    # Get search parameters from environment or use defaults
    make = os.environ.get("CAR_MAKE", DEFAULT_MAKE)
    model = os.environ.get("CAR_MODEL", DEFAULT_MODEL)
    postcode = os.environ.get("POSTCODE", DEFAULT_POSTCODE)
    radius = int(os.environ.get("RADIUS", DEFAULT_RADIUS))

    print(f"Searching for: {make} {model}")
    print(f"Location: {postcode} (radius: {radius} miles)")
    print(f"\nSearch Criteria:")
    print(f"  • Year: 2020 and newer")
    print(f"  • Price: Under £15,000")
    print(f"  • Mileage: Under 80,000 miles")
    print(f"  • Transmission: Automatic only")
    print(f"  • Condition: No write-offs")
    print()

    # Load previously seen cars (for duplicate prevention)
    seen_cars = load_seen_cars()
    print(f"Previously seen cars: {len(seen_cars)}")

    # Fetch current listings from AutoTrader
    all_cars = fetch_autotrader_cars(make, model, postcode, radius)
    current_cars = set(all_cars.keys())

    print(f"Current cars found: {len(current_cars)}")

    # Detect NEW cars only (current cars that we haven't seen before)
    new_cars = current_cars - seen_cars

    if new_cars:
        print(f"\n🎉 Found {len(new_cars)} new car(s)!")

        # Send notification(s) ONLY for new cars
        try:
            messages = format_car_notification(new_cars, all_cars, make, model)
            for i, message in enumerate(messages):
                print(f"\nSending notification {i+1}/{len(messages)}...")
                notify(message)
        except Exception as e:
            print(f"Failed to send notification: {e}")
    else:
        print("\nℹ No new cars found")

    # Save all current cars to state file
    if current_cars:
        save_seen_cars(current_cars)
        print(f"\n✓ State updated with {len(current_cars)} car(s)")

    print("="*60)

    return {
        "ok": True,
        "new_cars_count": len(new_cars),
        "total_count": len(current_cars),
        "previously_seen": len(seen_cars),
        "currently_seen": len(current_cars)
    }


if __name__ == "__main__":
    result = main()
    print(f"\nResult: {json.dumps(result, indent=2)}")
