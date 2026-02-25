require('dotenv').config({ path: __dirname + '/../.env' });
const { Kafka } = require('kafkajs');
const axios = require('axios');
const config = require('./config');

const API_URL = process.env.SENTRA_API_URL || config.scoringApi.url;
const EMAIL = process.env.SENTRA_EMAIL;
const PASSWORD = process.env.SENTRA_PASSWORD;

// Validate credentials are set
if (!EMAIL || !PASSWORD) {
  console.error('✗ Error: SENTRA_EMAIL and SENTRA_PASSWORD must be set in environment');
  process.exit(1);
}

const kafka = new Kafka({
  clientId: 'sentra-consumer',
  brokers: config.kafka.brokers
});

const consumer = kafka.consumer({ groupId: config.consumer.groupId });
const producer = kafka.producer();

let authToken = null;

async function getToken() {
  try {
    const res = await axios.post(`${API_URL}/auth/login`, {
      email: EMAIL,
      password: PASSWORD
    });
    authToken = res.data.access_token;
    console.log('✓ Auth token obtained');
  } catch (err) {
    console.error('✗ Login failed:', err.message);
    process.exit(1);
  }
}

const velocityWindow = new Map();
const WINDOW_MS = config.velocityDetector.windowSizeMs;
const SPIKE_THRESHOLD = config.velocityDetector.threshold;

function checkVelocity(phoneNumber) {
  const now = Date.now();
  if (!velocityWindow.has(phoneNumber)) velocityWindow.set(phoneNumber, []);
  const timestamps = velocityWindow.get(phoneNumber).filter(t => now - t < WINDOW_MS);
  timestamps.push(now);
  velocityWindow.set(phoneNumber, timestamps);
  return timestamps.length;
}

async function run() {
  await getToken();
  await consumer.connect();
  await producer.connect();
  console.log('✓ Consumer connected. Scoring transactions...');
  
  await consumer.subscribe({ topic: 'sentra.transactions.raw', fromBeginning: false });

  let scored = 0;
  let alerts = 0;

  await consumer.run({
    eachBatch: async ({ batch }) => {
      for (const message of batch.messages) {
        try {
          const tx = JSON.parse(message.value.toString());
          const velocity = checkVelocity(tx.phone_number);

          const response = await axios.post(`${API_URL}/v1/score`, {
            transaction_id: tx.transaction_id,
            amount: tx.amount,
            phone_number: tx.phone_number,
            device_id: tx.device_id,
            location: tx.location,
            timestamp: tx.timestamp
          }, {
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${authToken}`
            },
            timeout: 5000
          });

          const score = response.data;
          scored++;

          await producer.send({
            topic: 'sentra.scores.output',
            messages: [{ value: JSON.stringify({ ...tx, ...score }) }]
          });

          if (score.risk_level === 'HIGH' || velocity >= SPIKE_THRESHOLD) {
            alerts++;
            const alert = {
              type: velocity >= SPIKE_THRESHOLD ? 'VELOCITY_SPIKE' : 'HIGH_RISK',
              transaction_id: tx.transaction_id,
              phone_number: tx.phone_number,
              amount: tx.amount,
              risk_score: score.risk_score,
              risk_level: score.risk_level,
              velocity_count: velocity,
              timestamp: new Date().toISOString()
            };
            
            await producer.send({
              topic: 'sentra.alerts.fraud',
              messages: [{ value: JSON.stringify(alert) }]
            });
            
            console.log(`🚨 ALERT [${alert.type}] Phone: ${tx.phone_number} | Score: ${score.risk_score} | Velocity: ${velocity}`);
          } else {
            console.log(`  TX: ${tx.transaction_id} | Phone: ${tx.phone_number} | Velocity: ${velocity} | Risk: ${score.risk_level}`);
          }

          if (scored % 100 === 0) console.log(`✓ Scored: ${scored} | Alerts: ${alerts}`);
        } catch (err) {
          console.error('Scoring error:', err.message);
        }
      }
    }
  });
}

run().catch(console.error);

process.on('SIGINT', async () => {
  await consumer.disconnect();
  await producer.disconnect();
  process.exit(0);
});
