# TryOnU

**Try It. See You. Shop It.**

AI-powered virtual fashion shopping. Try real products from retailers on your own
photos, then shop from the original store.

This repository is being built as a production-scale, provider-agnostic platform.
It is organised as a monorepo:

```
apps/
  web/      Next.js 15 + React 19 + TypeScript + Tailwind v4   (this session)
  api/      FastAPI async core API                              (planned)
  worker/   AI + product-ingestion background workers            (planned)
packages/
  ai-providers/       AIProvider / VirtualTryOn / ImageGen / Vision / LLM abstractions (planned)
  product-providers/  Amazon / eBay / Flipkart / Daraz ingestion adapters             (planned)
  db/                 PostgreSQL + pgvector schema & migrations                        (planned)
infra/
  docker-compose.yml  Postgres, Redis, MinIO/R2, workers                              (planned)
```

## Current status

`apps/web` — marketing site / landing page. Light, premium FASHN-style visual
identity, TryOnU branding, reusable "fitting profile" photo-upload flow.

## Getting started

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000
