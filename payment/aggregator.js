const express = require('express');
const bodyParser = require('body-parser');
const sqlite3 = require('sqlite3').verbose();
const { v4: uuidv4 } = require('uuid');
const crypto = require('crypto');
const fetch = require('node-fetch');
const nodemailer = require('nodemailer');

const app = express();
app.use(bodyParser.json());

const PORT = process.env.PORT || 3003;
const LICENSE_SERVER_URL = process.env.LICENSE_SERVER_URL || 'http://localhost:4000';
const AGG_WEBHOOK_SECRET = process.env.AGG_WEBHOOK_SECRET || 'change_me';

// SMTP config taken from repository secrets at runtime
const SMTP_HOST = process.env.SMTP_HOST;
const SMTP_PORT = process.env.SMTP_PORT || 465;
const SMTP_USER = process.env.SMTP_USER;
const SMTP_PASS = process.env.SMTP_PASS;

if (!SMTP_HOST || !SMTP_USER || !SMTP_PASS) {
  console.warn('Warning: SMTP credentials not fully set. Email sending will fail until SMTP_HOST/SMTP_USER/SMTP_PASS are provided as env variables or repository Secrets.');
}

// DB
const db = new sqlite3.Database('./payments.db');
db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    out_trade_no TEXT UNIQUE,
    email TEXT,
    product TEXT,
    amount INTEGER,
    status TEXT,
    agg_trade_no TEXT,
    license_key TEXT,
    created_at INTEGER
  )`);
});

// Helper: create transporter (nodemailer)
function createTransporter() {
  if (!SMTP_HOST || !SMTP_USER || !SMTP_PASS) return null;
  return nodemailer.createTransport({
    host: SMTP_HOST,
    port: Number(SMTP_PORT),
    secure: Number(SMTP_PORT) === 465, // true for 465, false for 587
    auth: {
      user: SMTP_USER,
      pass: SMTP_PASS
    }
  });
}

// Create simple order and return a placeholder qrUrl (for demo)
app.post('/create-order', async (req, res) => {
  const { email, product = 'video-fast-summary', amount = 100 } = req.body;
  if (!email) return res.status(400).json({ error: 'missing email' });
  const out_trade_no = uuidv4();
  const now = Date.now();
  const id = uuidv4();
  db.run(`INSERT INTO orders (id, out_trade_no, email, product, amount, status, created_at) VALUES (?,?,?,?,?,?,?)`,
    [id, out_trade_no, email, product, amount, 'pending', now], function(err) {
      if (err) return res.status(500).json({ error: err.message });
      // In a real integration we'd call the aggregator API to get a qrUrl or payment link.
      const qrUrl = `https://example.com/pay?out_trade_no=${out_trade_no}`;
      res.json({ id, out_trade_no, email, product, amount, qrUrl, note: 'This is a demo qrUrl. Use the /webhook/aggregator endpoint to simulate a payment notify.' });
    });
});

// Aggregator notify endpoint (simulate aggregator POSTing payment result)
app.post('/webhook/aggregator', async (req, res) => {
  const payload = req.body;
  // Many aggregators send a signature header; we support HMAC-SHA256 with AGG_WEBHOOK_SECRET
  const sig = req.headers['x-agg-signature'] || req.headers['x-signature'];
  if (!sig) {
    console.warn('No signature header found');
    // For demo mode we allow unsigned (but log a warning)
  } else {
    const expected = crypto.createHmac('sha256', AGG_WEBHOOK_SECRET).update(JSON.stringify(payload)).digest('hex');
    if (sig !== expected) {
      console.warn('Invalid aggregator signature');
      // For demo we still allow, but in production we should return 400
      // return res.status(400).send('invalid signature');
    }
  }

  const out_trade_no = payload.out_trade_no;
  const agg_trade_no = payload.agg_trade_no || ('agg_' + uuidv4());
  const paidAmount = Number(payload.amount || 0);

  db.get(`SELECT * FROM orders WHERE out_trade_no = ?`, [out_trade_no], async (err, order) => {
    if (err) return res.status(500).send('error');
    if (!order) return res.status(404).send('order_not_found');
    if (order.status === 'paid') return res.send('ok'); // idempotent
    // Amount verification
    if (Number(order.amount) !== paidAmount) {
      console.warn('Amount mismatch', order.amount, paidAmount);
      // continue but log
    }

    // Mark paid and generate license
    const now = Date.now();
    db.run(`UPDATE orders SET status = ?, agg_trade_no = ? WHERE out_trade_no = ?`, ['paid', agg_trade_no, out_trade_no], async function(uerr) {
      if (uerr) console.error(uerr);
      // Call license server
      try {
        const resp = await fetch(`${LICENSE_SERVER_URL}/api/licenses/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: order.email, product: order.product, plan: 'pro', days: 365, meta: { orderId: order.id, out_trade_no } })
        });
        const license = await resp.json();
        const licenseKey = license.key || license.id || null;
        // Save license key
        db.run(`UPDATE orders SET license_key = ? WHERE out_trade_no = ?`, [licenseKey, out_trade_no]);

        // Send email with license
        const transporter = createTransporter();
        if (transporter && licenseKey) {
          const mailOptions = {
            from: SMTP_USER,
            to: order.email,
            subject: 'Your Video Fast Summary License',
            text: `Thanks for your purchase. Your license key: ${licenseKey}`,
            html: `<p>Thanks for your purchase.</p><p>Your license key: <b>${licenseKey}</b></p>`
          };
          transporter.sendMail(mailOptions, (mailErr, info) => {
            if (mailErr) console.error('Failed to send email', mailErr);
            else console.log('Sent license email', info && info.messageId);
          });
        } else {
          console.warn('Transporter not configured or license missing; skipping email');
        }

        res.json({ result: 'ok', license });
      } catch (e) {
        console.error('license server error', e);
        res.status(500).send('license_error');
      }
    });
  });
});

app.get('/orders/:out_trade_no', (req, res) => {
  const out_trade_no = req.params.out_trade_no;
  db.get(`SELECT * FROM orders WHERE out_trade_no = ?`, [out_trade_no], (err, row) => {
    if (err) return res.status(500).json({ error: err.message });
    if (!row) return res.status(404).json({ error: 'not_found' });
    res.json(row);
  });
});

app.listen(PORT, () => console.log(`Payment aggregator demo running on port ${PORT}`));
