Payment aggregator integration (demo)

This folder contains a demo implementation of a payment "aggregator" webhook and a lightweight order flow suitable for plugging in to the license-server in this repo.

Files:
- aggregator.js  -- express app with /create-order, /webhook/aggregator and /orders/:out_trade_no
- package.json   -- dependencies
- sample_notify.json -- example payload you can POST to /webhook/aggregator to simulate a payment notify

Required repository Secrets (add these in Settings → Secrets → Actions):
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS  (we used QQ SMTP in examples)
- LICENSE_SERVER_URL  (e.g. https://license.example.com or demo http://localhost:4000)
- AGG_WEBHOOK_SECRET  (optional for demo; used to verify HMAC signature)

How to run locally:
1) Install dependencies
   cd payment
   npm ci
2) Start the demo license server (see license-server/README or run: cd ../license-server && npm ci && node server.js)
3) Run the aggregator demo
   npm start

Create an order (demo):
curl -X POST http://localhost:3003/create-order -H "Content-Type: application/json" -d '{"email":"buyer@example.com","product":"video-fast-summary","amount":100}'

This returns an out_trade_no. Simulate the aggregator notify (use sample_notify.json and replace out_trade_no):
curl -X POST http://localhost:3003/webhook/aggregator -H "Content-Type: application/json" -d @sample_notify.json

Check order:
curl http://localhost:3003/orders/<OUT_TRADE_NO>

Notes:
- In production, replace the demo /create-order flow with real aggregator API calls (to generate QR codes or prepay links).
- Always verify aggregator signatures (we demo HMAC-SHA256 using AGG_WEBHOOK_SECRET). Do not skip signature verification in production.
- Replace the demo SQLite storage with a production DB (Postgres/MySQL) and add proper logging/monitoring/ratelimiting.
