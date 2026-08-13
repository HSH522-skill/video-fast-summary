// Stripe webhook: 在收到 successful payment intent / invoice.payment_succeeded 时生成 license
const express = require('express');
const bodyParser = require('body-parser');
const fetch = require('node-fetch');
const app = express();

// 注意：对于真实 Stripe webhook，应使用 raw body 验证签名，示例忽略细节
app.use(bodyParser.json());

app.post('/webhook/stripe', async (req, res) => {
  const event = req.body;
  if (event.type === 'checkout.session.completed' || event.type === 'invoice.payment_succeeded') {
    const email = event.data.object.customer_email || (event.data.object.customer_details && event.data.object.customer_details.email);
    if (email) {
      await fetch(process.env.LICENSE_SERVER_URL + '/api/licenses/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, product: 'video-fast-summary', plan: 'pro', days: 365 })
      });
    }
  }
  res.json({ received: true });
});

app.listen(3001, () => console.log('Stripe webhook listener on 3001'));
