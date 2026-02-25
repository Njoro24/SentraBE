/**
 * ════════════════════════════════════════════════════════════════════════════════
 * STREAMING SERVICES CONFIGURATION
 * ════════════════════════════════════════════════════════════════════════════════
 * 
 * Centralized configuration for all Phase 2 streaming components.
 * Load from environment variables with sensible defaults.
 * 
 * ════════════════════════════════════════════════════════════════════════════════
 */

require('dotenv').config();

module.exports = {
  // ─────────────────────────────────────────────────────────────────────────────
  // KAFKA CONFIGURATION
  // ─────────────────────────────────────────────────────────────────────────────
  kafka: {
    brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
    clientId: process.env.KAFKA_CLIENT_ID || 'sentra-client',
    connectionTimeout: parseInt(process.env.KAFKA_CONNECTION_TIMEOUT || '10000'),
    requestTimeout: parseInt(process.env.KAFKA_REQUEST_TIMEOUT || '30000'),
    retry: {
      initialRetryTime: 100,
      retries: 8,
      maxRetryTime: 30000,
    }
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // KAFKA TOPICS
  // ─────────────────────────────────────────────────────────────────────────────
  topics: {
    rawTransactions: 'sentra.transactions.raw',
    scoresOutput: 'sentra.scores.output',
    alertsFraud: 'sentra.alerts.fraud',
    scoresDLQ: 'sentra.scores.dlq',
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // PRODUCER CONFIGURATION
  // ─────────────────────────────────────────────────────────────────────────────
  producer: {
    transactionsPerSecond: parseInt(process.env.TRANSACTIONS_PER_SECOND || '100'),
    batchSize: parseInt(process.env.BATCH_SIZE || '10'),
    fraudRatio: parseFloat(process.env.FRAUD_RATIO || '0.02'),
    spikeFrequency: parseInt(process.env.SPIKE_FREQUENCY || '10'),
    spikeDuration: parseInt(process.env.SPIKE_DURATION || '5'),
    idempotent: true,
    maxInFlightRequests: 5,
    compression: 1, // Gzip
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // CONSUMER CONFIGURATION
  // ─────────────────────────────────────────────────────────────────────────────
  consumer: {
    groupId: 'sentra-scorers',
    batchSize: parseInt(process.env.CONSUMER_BATCH_SIZE || '50'),
    maxRetries: parseInt(process.env.MAX_RETRIES || '3'),
    sessionTimeout: 30000,
    heartbeatInterval: 3000,
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // VELOCITY DETECTOR CONFIGURATION
  // ─────────────────────────────────────────────────────────────────────────────
  velocityDetector: {
    groupId: 'sentra-velocity-detector',
    windowSizeMs: parseInt(process.env.WINDOW_SIZE_MS || '60000'),
    threshold: parseInt(process.env.VELOCITY_THRESHOLD || '10'),
    cleanupIntervalMs: 30000,
    sessionTimeout: 30000,
    heartbeatInterval: 3000,
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // WEBSOCKET CONFIGURATION
  // ─────────────────────────────────────────────────────────────────────────────
  websocket: {
    port: parseInt(process.env.WEBSOCKET_PORT || '8080'),
    host: process.env.WEBSOCKET_HOST || '0.0.0.0',
    groupId: 'sentra-websocket-server',
    sessionTimeout: 30000,
    heartbeatInterval: 3000,
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // SCORING API CONFIGURATION
  // ─────────────────────────────────────────────────────────────────────────────
  scoringApi: {
    url: process.env.SCORING_API_URL || 'http://localhost:8000',
    timeout: parseInt(process.env.SCORING_API_TIMEOUT || '10000'),
    healthCheckInterval: 30000,
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // LOGGING CONFIGURATION
  // ─────────────────────────────────────────────────────────────────────────────
  logging: {
    level: process.env.LOG_LEVEL || 'info',
    format: process.env.LOG_FORMAT || 'text', // 'text' or 'json'
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // PERFORMANCE TARGETS
  // ─────────────────────────────────────────────────────────────────────────────
  performance: {
    targetThroughput: 100, // tx/sec
    maxLatencyMs: 200, // p95
    fraudCatchRate: 0.99,
    alertDeliveryLatencyMs: 1000,
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // VALIDATION
  // ─────────────────────────────────────────────────────────────────────────────
  validate() {
    const errors = [];

    if (!this.kafka.brokers || this.kafka.brokers.length === 0) {
      errors.push('KAFKA_BROKERS not configured');
    }

    if (this.producer.transactionsPerSecond <= 0) {
      errors.push('TRANSACTIONS_PER_SECOND must be > 0');
    }

    if (this.velocityDetector.threshold <= 0) {
      errors.push('VELOCITY_THRESHOLD must be > 0');
    }

    if (this.websocket.port < 1024 || this.websocket.port > 65535) {
      errors.push('WEBSOCKET_PORT must be between 1024 and 65535');
    }

    if (errors.length > 0) {
      console.error('Configuration errors:');
      errors.forEach(e => console.error(`  ✗ ${e}`));
      process.exit(1);
    }

    return true;
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // DISPLAY CONFIGURATION
  // ─────────────────────────────────────────────────────────────────────────────
  display() {
    console.log('\n' + '═'.repeat(80));
    console.log('CONFIGURATION LOADED');
    console.log('═'.repeat(80));
    console.log(`Kafka brokers: ${this.kafka.brokers.join(', ')}`);
    console.log(`Producer: ${this.producer.transactionsPerSecond} tx/sec`);
    console.log(`Velocity threshold: ${this.velocityDetector.threshold} tx/${this.velocityDetector.windowSizeMs / 1000}s`);
    console.log(`WebSocket port: ${this.websocket.port}`);
    console.log(`Scoring API: ${this.scoringApi.url}`);
    console.log('═'.repeat(80) + '\n');
  }
};
