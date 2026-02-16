# Cryphos

Real-time cryptocurrency trading analytics platform with automated bots and market intelligence.

## Overview

Cryphos provides traders with real-time market data, customizable trading bots, and instant Telegram alerts. Built for crypto traders who want data-driven insights.

## Features

**Analytics Dashboard**
- Fear & Greed Index
- Funding rates across exchanges
- Live liquidations feed (WebSocket)
- Long/Short ratio tracking

**Trading Bots**
- RSI — Relative Strength Index with custom thresholds
- EMA — Exponential Moving Average crossovers
- Bollinger Bands — Volatility-based signals
- Support/Resistance — Key price level detection
- Multi-timeframe: 1m, 5m, 15m, 30m, 1h, 1d

**Telegram Integration**
- Instant signal notifications via @cryphos_bot
- Real-time alerts for configured strategies

## Tech Stack

**Backend**
- Python 3.11 / Django 6.0
- Django REST Framework
- PostgreSQL / Redis
- Celery (async tasks)
- Channels + Daphne (WebSockets)
- pandas / pandas-ta (indicators)

**Frontend**
- Next.js 14 / React
- Tailwind CSS
- Framer Motion

**Infrastructure**
- Docker / Docker Compose
- Nginx

## Architecture
```
Frontend (Next.js)
       │
       ▼
API Gateway (Django REST + Channels)
       │
       ├── Auth / Users
       ├── Bots / Signals  
       ├── Analytics
       ├── Payments (Stripe)
       └── Telegram Bot
       │
       ▼
┌──────────────────────────┐
│  PostgreSQL  │  Redis    │
└──────────────────────────┘
       │
       ▼
Celery Workers
  - OHLCV fetching
  - Indicator calculation
  - Signal generation
```

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### Run
```bash
git clone https://github.com/yourusername/cryphos.git
cd cryphos

# Configure your environment variables

docker compose up -d
```

That's it. The entire stack runs in Docker.

### Services
```bash
docker compose ps
```

| Service | Description |
|---------|-------------|
| web | Django + Daphne (API + WebSocket) |
| celery | Background task worker |
| celery-beat | Scheduled tasks |
| db | PostgreSQL |
| redis | Cache + message broker |
| nginx | Reverse proxy |
| frontend | Next.js |

### Useful Commands
```bash
# View logs
docker compose logs -f web

# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Restart services
docker compose restart
```



## Roadmap

- [x] Real-time liquidation feed
- [x] Technical indicators (RSI, EMA, BB, S/R)
- [x] Telegram notifications
- [x] Stripe payments
- [ ] Portfolio tracking


