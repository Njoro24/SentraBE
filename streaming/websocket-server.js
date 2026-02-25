require('dotenv').config({ path: '../.env' });
const { Kafka } = require('kafkajs');
const WebSocket = require('ws');

const kafka = new Kafka({ clientId: 'sentra-ws', brokers: ['localhost:9092'] });
const consumer = kafka.consumer({ groupId: 'sentra-websocket' });
const wss = new WebSocket.Server({ port: 8080 });

console.log('✓ WebSocket server started on ws://localhost:8080');

wss.on('connection', (ws) => {
  console.log('Dashboard client connected');
  ws.send(JSON.stringify({ type: 'CONNECTED', message: 'Sentra alert stream active' }));
  ws.on('close', () => console.log('Dashboard client disconnected'));
});

function broadcast(data) {
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(data));
    }
  });
}

async function run() {
  await consumer.connect();
  await consumer.subscribe({ topic: 'sentra.alerts.fraud', fromBeginning: false });

  await consumer.run({
    eachMessage: async ({ message }) => {
      const alert = JSON.parse(message.value.toString());
      console.log(`Broadcasting alert: ${alert.type} | ${alert.phone_number}`);
      broadcast({ type: 'FRAUD_ALERT', data: alert });
    }
  });
}

run().catch(console.error);
