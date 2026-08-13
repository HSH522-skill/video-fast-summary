// 最小 License Server (Express + sqlite3)
// 用途：接收 webhook (Stripe/Paddle) 生成 license，提供 /validate 接口校验授权
const express = require('express');
const bodyParser = require('body-parser');
const crypto = require('crypto');
const sqlite3 = require('sqlite3').verbose();
const { v4: uuidv4 } = require('uuid');

const app = express();
app.use(bodyParser.json());

// 配置（或用环境变量）
const PORT = process.env.PORT || 4000;
const SECRET = process.env.LICENSE_SECRET || 'change_this_secret'; // 用于签名/校验

// SQLite 初始化（文件：licenses.db）
const db = new sqlite3.Database('./licenses.db');
db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS licenses (
    id TEXT PRIMARY KEY,
    key TEXT UNIQUE,
    email TEXT,
    product TEXT,
    plan TEXT,
    created_at INTEGER,
    expires_at INTEGER,
    meta TEXT
  )`);
});

// 生成 license key（内部函数）
function generateKey() {
  // 示例：UUID + HMAC 签名简易组合
  const id = uuidv4();
  const h = crypto.createHmac('sha256', SECRET).update(id).digest('hex').slice(0, 16).toUpperCase();
  return `${id.split('-')[0]}-${h}`;
}

// Stripe / Paddle webhook 示例会调用此接口生成 license（或可直接插入 DB）
app.post('/api/licenses/generate', (req, res) => {
  const { email, product='video-fast-summary', plan='pro', days=365, meta } = req.body;
  const key = generateKey();
  const id = uuidv4();
  const now = Date.now();
  const expires = days ? now + days * 24 * 3600 * 1000 : null;
  db.run(
    `INSERT INTO licenses (id, key, email, product, plan, created_at, expires_at, meta) VALUES (?,?,?,?,?,?,?,?)`,
    [id, key, email, product, plan, now, expires, JSON.stringify(meta || {})],
    function(err) {
      if (err) return res.status(500).json({ error: err.message });
      res.json({ id, key, email, product, plan, expires_at: expires });
    }
  );
});

// 校验 license
app.post('/api/licenses/validate', (req, res) => {
  const { key } = req.body;
  if (!key) return res.status(400).json({ valid: false, reason: 'missing_key' });
  db.get(`SELECT * FROM licenses WHERE key = ?`, [key], (err, row) => {
    if (err) return res.status(500).json({ valid: false, reason: err.message });
    if (!row) return res.status(404).json({ valid: false, reason: 'not_found' });
    if (row.expires_at && Date.now() > row.expires_at) return res.json({ valid: false, reason: 'expired' });
    return res.json({ valid: true, data: { product: row.product, plan: row.plan, email: row.email }});
  });
});

// 简单管理接口（列出 licenses）
app.get('/api/licenses', (req, res) => {
  db.all(`SELECT id, key, email, product, plan, created_at, expires_at FROM licenses ORDER BY created_at DESC LIMIT 100`, [], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

app.listen(PORT, () => console.log(`License server running on port ${PORT}`));
