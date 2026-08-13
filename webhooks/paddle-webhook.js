const express = require('express');
const bodyParser = require('body-parser');
const fetch = require('node-fetch');
const app = express();
app.use(bodyParser.urlencoded({ extended: true }));

app.post('/webhook/paddle', async (req, res) => {
  const email = req.body.email || req.body['buyer_email'];
  const alert = req.body.alert_name;
  if (alert === 'payment_succeeded' && email) {
    await fetch(process.env.LICENSE_SERVER_URL + '/api/licenses/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, product: 'video-fast-summary', plan: 'pro', days: 365 })
    });
  }
  res.send('OK');
});

app.listen(3002, () => console.log('Paddle webhook listener on 3002'));
