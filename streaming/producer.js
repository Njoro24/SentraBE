const { Kafka } = require('kafkajs');
const { v4: uuidv4 } = require('uuid');
const config = require('./config');

const kafka = new Kafka({
  clientId: config.kafka.clientId,
  brokers: config.kafka.brokers
});

const producer = kafka.producer(config.producer);

const LOCATIONS = ['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret'];
const CHANNELS = ['mpesa', 'bank', 'atm'];

function generateTransaction(isFraud = false) {
  const hour = isFraud ? Math.floor(Math.random() * 5) : Math.floor(Math.random() * 14) + 7;
  return {
    transaction_id: uuidv4(),
    amount: isFraud ? Math.random() * 180000 + 50000 : Math.random() * 20000 + 50,
    phone_number: `2547${Math.floor(Math.random() * 90000000 + 10000000)}`,
    device_id: `DEV${Math.floor(Math.random() * 1000)}`,
    location: LOCATIONS[Math.floor(Math.random() * LOCATIONS.length)],
    channel: CHANNELS[Math.floor(Math.random() * CHANNELS.length)],
    timestamp: new Date().toISOString(),
    hour,
    is_fraud_simulation: isFraud
  };
}

async function run() {
  await producer.connect();
  console.log(`✓ Producer connected. Streaming ${config.producer.transactionsPerSecond} tx/sec...`);

  let count = 0;
  let fraudCount = 0;

  setInterval(async () => {
    const batch = [];
    for (let i = 0; i < config.producer.batchSize; i++) {
      const isFraud = Math.random() < config.producer.fraudRatio;
      if (isFraud) fraudCount++;
      batch.push({
        key: `txn-${count++}`,
        value: JSON.stringify(generateTransaction(isFraud))
      });
    }

    await producer.send({
      topic: config.topics.rawTransactions,
      messages: batch
    });

    console.log(`Sent ${config.producer.batchSize} tx | Total: ${count} | Fraud simulated: ${fraudCount}`);
  }, 1000 / (config.producer.transactionsPerSecond / config.producer.batchSize));
}

run().catch(console.error);

process.on('SIGINT', async () => {
  await producer.disconnect();
  console.log('Producer disconnected');
  process.exit(0);
});
