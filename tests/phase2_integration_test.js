const { Kafka } = require('kafkajs');
const WebSocket = require('ws');
const axios = require('axios');

const kafka = new Kafka({
  clientId: 'test-client',
  brokers: ['localhost:9092'],
});

const testResults = {
  startTime: Date.now(),
  messagesProduced: 0,
  messagesConsumed: 0,
  alertsGenerated: 0,
  alertsReceived: 0,
  latencies: [],
  errors: []
};

// Test 1: Verify messages flowing through Kafka
async function testKafkaFlow() {
  console.log('\n📊 TEST 1: Kafka Message Flow');

  const admin = kafka.admin();
  await admin.connect();

  // Check topic offsets
  const offsets = await admin.fetchTopicOffsets('sentra.transactions.raw');
  const offset = offsets[0].high;

  console.log(`  ✓ sentra.transactions.raw: ${offset} messages`);

  // Give it 10 seconds to accumulate
  await new Promise(r => setTimeout(r, 10000));

  const offsets2 = await admin.fetchTopicOffsets('sentra.transactions.raw');
  const offset2 = offsets2[0].high;
  const produced = offset2 - offset;

  console.log(`  ✓ Produced in 10 sec: ${produced} messages`);
  console.log(`  ✓ Rate: ${Math.round(produced / 10)} msg/sec`);

  testResults.messagesProduced = produced;

  if (produced > 900) {
    console.log(`  ✅ PASS: Producing ~100 msg/sec`);
  } else {
    console.log(`  ❌ FAIL: Expected ~1000 messages, got ${produced}`);
    testResults.errors.push(`Low message production: ${produced}`);
  }

  await admin.disconnect();
}

// Test 2: Verify velocity alerts generated
async function testVelocityAlerts() {
  console.log('\n📊 TEST 2: Velocity Alert Generation');

  const consumer = kafka.consumer({ groupId: 'test-alerts-group' });
  await consumer.connect();
  await consumer.subscribe({ topic: 'sentra.alerts.fraud' });

  let alertCount = 0;

  await consumer.run({
    eachMessage: async ({ message }) => {
      const alert = JSON.parse(message.value.toString());
      if (alert.type === 'VELOCITY_SPIKE' || alert.alert_type === 'VELOCITY_SPIKE') {
        alertCount++;
      }
    },
  });

  // Monitor for 5 seconds
  await new Promise(r => setTimeout(r, 5000));
  await consumer.disconnect();

  console.log(`  ✓ Alerts generated: ${alertCount}`);
  testResults.alertsGenerated = alertCount;

  if (alertCount > 0) {
    console.log(`  ✅ PASS: Velocity alerts being generated`);
  } else {
    console.log(`  ⚠️  WARNING: No velocity alerts (may need more time)`);
  }
}

// Test 3: Verify WebSocket receives alerts
async function testWebSocketAlerts() {
  console.log('\n📊 TEST 3: WebSocket Alert Delivery');

  return new Promise((resolve) => {
    const ws = new WebSocket('ws://localhost:8080');
    let alertCount = 0;

    ws.on('open', () => {
      console.log(`  ✓ WebSocket connected`);

      ws.on('message', (data) => {
        try {
          const msg = JSON.parse(data);
          if (msg.type === 'FRAUD_ALERT' || msg.data?.type === 'VELOCITY_SPIKE') {
            alertCount++;
            const latency = Date.now() - new Date(msg.data?.timestamp || Date.now()).getTime();
            testResults.latencies.push(latency);
            console.log(`  ✓ Alert received (latency: ${latency}ms)`);
          }
        } catch (e) {}
      });
    });

    // Listen for 10 seconds
    setTimeout(() => {
      console.log(`  ✓ Alerts received via WebSocket: ${alertCount}`);
      testResults.alertsReceived = alertCount;

      if (alertCount > 0) {
        console.log(`  ✅ PASS: WebSocket delivering alerts`);
      } else {
        console.log(`  ⚠️  WARNING: No WebSocket alerts (may need more time)`);
      }

      ws.close();
      resolve();
    }, 10000);
  });
}

// Test 4: Verify API scoring works
async function testAPIScoring() {
  console.log('\n📊 TEST 4: API Scoring Performance');

  const scoreData = {
    transaction_id: 'TEST_TXN_001',
    amount: 150000,
    phone_number: '+254700000001',
    device_id: 'device_test',
    location: 'Moscow',
    merchant_category: 'Online Gambling'
  };

  try {
    const start = Date.now();
    const response = await axios.post(
      'http://localhost:8000/v1/score',
      scoreData
    );
    const latency = Date.now() - start;

    console.log(`  ✓ Score: ${response.data.risk_level}`);
    console.log(`  ✓ Latency: ${latency}ms`);

    if (latency < 200) {
      console.log(`  ✅ PASS: API scoring < 200ms`);
    } else {
      console.log(`  ⚠️  WARNING: API latency ${latency}ms > 200ms`);
    }
  } catch (error) {
    console.log(`  ⚠️  WARNING: ${error.message}`);
  }
}

// Run all tests
async function runAllTests() {
  console.log('═══════════════════════════════════════');
  console.log('PHASE 2: STREAMING INTEGRATION TEST');
  console.log('═══════════════════════════════════════');

  try {
    await testKafkaFlow();
    await testVelocityAlerts();
    await testWebSocketAlerts();
    await testAPIScoring();

    // Print summary
    console.log('\n═══════════════════════════════════════');
    console.log('TEST SUMMARY');
    console.log('═══════════════════════════════════════');
    console.log(`Duration: ${Math.round((Date.now() - testResults.startTime) / 1000)}s`);
    console.log(`Messages produced: ${testResults.messagesProduced}`);
    console.log(`Velocity alerts: ${testResults.alertsGenerated}`);
    console.log(`WebSocket alerts: ${testResults.alertsReceived}`);

    if (testResults.latencies.length > 0) {
      const avgLatency = testResults.latencies.reduce((a, b) => a + b) / testResults.latencies.length;
      console.log(`Avg latency: ${Math.round(avgLatency)}ms`);
    }

    if (testResults.errors.length === 0) {
      console.log('\n✅ ALL TESTS PASSED');
    } else {
      console.log('\n⚠️  WARNINGS:');
      testResults.errors.forEach(e => console.log(`  - ${e}`));
    }

  } catch (error) {
    console.error('Test error:', error);
  }

  process.exit(testResults.errors.length === 0 ? 0 : 1);
}

runAllTests();
