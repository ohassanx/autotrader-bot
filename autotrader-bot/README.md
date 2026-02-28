# AutoTrader Car Checker Bot

Automated Telegram bot that monitors AutoTrader UK for new car listings matching specific criteria and sends instant notifications. Focused on finding quality used cars with good resale value.

## Features

- Monitors AutoTrader UK for new car listings
- **Strict filtering criteria:**
  - Year: 2020 and newer
  - Price: Under £15,000
  - Mileage: Under 80,000 miles
  - Transmission: Automatic only
  - Condition: Excludes all write-offs (Cat S, Cat N, damaged, salvage, etc.)
- Sends Telegram notifications for new cars
- Tracks previously seen cars to avoid duplicate notifications
- Customizable search parameters (make, model, location)
- Runs automatically via GitHub Actions every 2 hours
- Can be run manually or scheduled locally

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the instructions
3. Save your bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your Chat ID

1. Start a chat with your new bot
2. Send any message to it
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find the `"chat":{"id":` value (your chat ID)

### 3. Configure GitHub Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

- `BOT_TOKEN`: Your Telegram bot token
- `CHAT_ID`: Your Telegram chat ID

Optional secrets for custom search:
- `CAR_MAKE`: Car make to search for (default: BMW)
- `CAR_MODEL`: Car model to search for (default: 3 Series)
- `POSTCODE`: Search center postcode (default: M15 4FN)
- `RADIUS`: Search radius in miles (default: 1500)

### 4. Enable GitHub Actions

The workflow will automatically run every 2 hours. You can also trigger it manually from the Actions tab.

## Local Usage

### Installation

```bash
cd autotrader-bot
pip install -r requirements.txt
```

### Running Locally

Set environment variables and run:

```bash
export BOT_TOKEN="your_bot_token"
export CHAT_ID="your_chat_id"
export CAR_MAKE="BMW"
export CAR_MODEL="3 Series"
export POSTCODE="E15 4EQ"
export RADIUS="150000"  # Large radius to search all of UK

python3 check_cars.py
```

## How It Works

1. Scrapes AutoTrader UK for listings matching strict criteria (2020+, <£15k, <80k miles, automatic, no write-offs)
2. Filters out any write-offs by checking for keywords in descriptions (Cat S, Cat N, salvage, damaged, etc.)
3. Compares current listings with previously seen cars
4. Sends Telegram notifications for new listings only
5. Updates the state file (`seen_cars.json`) with current listings
6. GitHub Actions automatically commits the updated state file

## Why These Criteria?

The search criteria are designed to find cars that will:
- Hold their value well over the next 5 years
- Be reliable and have low depreciation
- Be in good condition (no accident history)
- Have reasonable mileage for their age
- Be easy to resell in the future

Good makes/models for resale value: BMW, Mercedes, Audi, Lexus, Toyota, Honda, Porsche

## File Structure

```
autotrader-bot/
├── check_cars.py          # Main bot script
├── requirements.txt       # Python dependencies
├── seen_cars.json        # State file (tracks seen cars)
└── README.md             # This file
```

## Notification Format

When new cars are found, you'll receive a Telegram message with:

- Car title (year, make, model)
- Key specifications (mileage, fuel type, transmission, etc.)
- Price
- Description
- Attention grabber (e.g., "Great price", "Low mileage")
- Direct link to the listing
- Search criteria summary (year, price, mileage, transmission, condition filters)

## Customization

Edit the default values in `check_cars.py`:

```python
DEFAULT_MAKE = "BMW"
DEFAULT_MODEL = "3 Series"
DEFAULT_POSTCODE = "E15 4EQ"
DEFAULT_RADIUS = 150000  # Large radius to cover all of UK
```

Or override them using environment variables.

**Note:** The core filtering criteria (year 2020+, price <£15k, mileage <80k, automatic, no write-offs) are hardcoded in the URL constructor to ensure you only see quality cars with good resale value. To change these, edit the `url_constructor` function in `check_cars.py`.

## Troubleshooting

### No notifications received

- Check that your `BOT_TOKEN` and `CHAT_ID` are correct
- Verify you've started a chat with your bot
- Check GitHub Actions logs for errors

### Duplicate notifications

- Make sure the `seen_cars.json` file is being committed and pushed
- Check that the workflow has write permissions

### Not finding cars

- Verify your search parameters are correct
- Try searching manually on AutoTrader to confirm listings exist
- Check the console output for errors

## Credits

Based on the [autotrader.uk-search](https://github.com/fnazz/autotrader.uk-search) scraper.
