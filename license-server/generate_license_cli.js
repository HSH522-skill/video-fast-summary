// 生成 license 的简单 CLI（可由 webhook 调用或手动使用）
const fetch = require('node-fetch');

async function create(email) {
  const res = await fetch(process.env.LICENSE_SERVER_URL + '/api/licenses/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, product: 'video-fast-summary', plan: 'pro', days: 365 })
  });
  console.log(await res.json());
}

create(process.argv[2] || 'buyer@example.com');
