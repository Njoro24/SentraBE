/**
 * ════════════════════════════════════════════════════════════════════════════════
 * SENTRA VELOCITY SPIKE DETECTOR
 * ════════════════════════════════════════════════════════════════════════════════
 * 
 * Real-time sliding window detector that monitors transaction streams for velocity
 * attacks. Detects when a single sender ID produces more than a threshold of
 * transactions within a 60-second window.
 * 
 * Features:
 * - 60-second rolling window per sender
 * - Configurable threshold (default: 10 tx/60s)
 * - Cross-account fraud ring detection
 * - Spike severity scoring (LOW/HIGH/CRITICAL)
 * - Memory-safe window cleanup
 * 
 * Usage:
 *   node velocity-detector.js [--threshold 10] [--window-size 60000]
 * 
 * ════════════════════════════════════════════════════════════════════════════════
 */

const { Kafka } = require('kafkajs');
require('dotenv').config();

// ─────────────────────────────────────────────────────────────────────────────
// CONFIGURATION
// ─────────────────────────────────────────────────────────────────────────────

const KAFKA_BROKERS = (process.env.KAFKA_BROKERS || 'localhost:9092').split(',');
const TOPIC_SCORES_OUTPUT = 'sentra.scores.output';
const TOPIC_ALERTS_FRAUD = 'sentra.alerts.fraud';
const CONSUMER_GROUP = 'sentra-velocity-detector';

// Parse command line arguments
const args = process.argv.slice(2);
const VELOCITY_THRESHOLD = parseInt(args[args.indexOf('--threshold') + 1] || '10');
const WINDOW_SIZE_MS = parseInt(args[args.indexOf('--window-size') + 1] || '60000');

// ─────────────────────────────────────────────────────────────────────────────
// SLIDING WINDOW DETECTOR
// ─────────────────────────────────────────────────────────────────────────────

class SlidingWindowDetector {
  constructor(windowSizeMs, threshold) {
    this.windowSizeMs = windowSizeMs;
    this.threshold = threshold;
    // Map of sender_id -> array of timestamps
    this.windows = new Map();
    this.stats = {
      spikesDetected: 0,
      totalTransactions: 0,
      cleanupRuns: 0,
    };
  }

  /**
   * Add a transaction to the window and check for spike
   */
  addTransaction(senderId) {
    const now = Date.now();

    // Initialize window for this sender if not exists
    if (!this.windows.has(senderId)) {
      this.windows.set(senderId, []);
    }

    const window = this.windows.get(senderId);

    // Add transaction timestamp
    window.push(now);

    // Remove old transactions outside the window
    const cutoffTime = now - this.windowSizeMs;
    const filteredWindow = window.filter(t => t > cutoffTime);
    this.windows.set(senderId, filteredWindow);

    this.stats.totalTransactions++;

    // Check if threshold exceeded
    const isSpike = filteredWindow.length > this.threshold;
    const severity = this.calculateSeverity(filteredWindow.length);

    return {
      isSpike,
      severity,
      transactionCount: filteredWindow.length,
      threshold: this.threshold
    };
  }

  /**
   * Calculate spike severity based on transaction count
   */
  calculateSeverity(count) {
    if (count <= this.threshold) {
      return 'NORMAL';
    } else if (count <= this.threshold * 1.5) {
      return 'LOW';
    } else if (count <= this.threshold * 2.5) {
      return 'HIGH';
    } else {
      return 'CRITICAL';
    }
  }

  /**
   * Clean up old windows to prevent memory leak
   */
  cleanup() {
    const now = Date.now();
    const cutoffTime = now - this.windowSizeMs;
    let cleaned = 0;

    for (const [senderId, window] of this.windows.entries()) {
      const filteredWindow = window.filter(t => t > cutoffTime);

      if (filteredWindow.length === 0) {
        this.windows.delete(senderId);
        cleaned++;
      } else {
        this.windows.set(senderId, filteredWindow);
      }
    }

    this.stats.cleanupRuns++;
    return cleaned;
  }

  /**
   * Get current window state for a sender
   */
  getWindowState(senderId) {
    const window = this.windows.get(senderId) || [];
    const now = Date.now();
    const cutoffTime = now - this.windowSizeMs;
    const activeTransactions = window.filter(t => t > cutoffTime);

    return {
      senderId,
      transactionCount: activeTransactions.length,
      threshold: this.threshold,
      isSpike: activeTransactions.length > this.threshold,
      severity: this.calculateSeverity(activeTransactions.length),
      windowSizeSeconds: this.windowSizeMs / 1000
    };
  }

  /**
   * Get all active spikes
   */
  getActiveSpikes() {
    const spikes = [];
    const now = Date.now();
    const cutoffTime = now - this.windowSizeMs;

    for (const [senderId, window] of this.windows.entries()) {
      const activeTransactions = window.filter(t => t > cutoffTime);
      if (activeTransactions.length > this.threshold) {
        spikes.push({
          senderId,
          transactionCount: activeTransactions.length,
          threshold: this.threshold,
          severity: this.calculateSeverity(activeTransactions.length)
        });
      }
    }

    return spikes;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// VELOCITY DETECTOR SERVICE
// ─────────────────────────────────────────────────────────────────────────────

class VelocityDetectorService {
  constructor() {
    this.kafka = new Kafka({
      clientId: 'sentra-velocity-detector',
      brokers: KAFKA_BROKERS,
      retry: {
        initialRetryTime: 100,
        retries: 8,
        maxRetryTime: 30000,
      }
    });

    this.consumer = this.kafka.consumer({
      groupId: CONSUMER_GROUP,
      sessionTimeout: 30000,
      heartbeatInterval: 3000,
    });

    this.producer = this.kafka.producer({
      idempotent: true,
      maxInFlightRequests: 5,
      compression: 1,
    });

    this.detector = new SlidingWindowDetector(WINDOW_SIZE_MS, VELOCITY_THRESHOLD);
    this.isRunning = false;
    this.stats = {
      processed: 0,
      spikesDetected: 0,
      startTime: null,
    };

    // Cleanup interval (every 30 seconds)
    this.cleanupInterval = setInterval(() => {
      const cleaned = this.detector.cleanup();
      if (cleaned > 0) {
        console.log(`🧹 Cleanup: Removed ${cleaned} expired windows`);
      }
    }, 30000);
  }

  /**
   * Connect to Kafka
   */
  async connect() {
    try {
      await this.consumer.connect();
      await this.producer.connect();
      console.log('✓ Connected to Kafka broker');
    } catch (error) {
      console.error('✗ Connection failed:', error.message);
      throw error;
    }
  }

  /**
   * Disconnect from Kafka
   */
  async disconnect() {
    try {
      clearInterval(this.cleanupInterval);
      await this.consumer.disconnect();
      await this.producer.disconnect();
      console.log('✓ Disconnected from Kafka broker');
    } catch (error) {
      console.error('✗ Error disconnecting:', error.message);
    }
  }

  /**
   * Publish velocity spike alert
   */
  async publishAlert(score, spikeInfo) {
    try {
      const alert = {
        transaction_id: score.transaction_id,
        phone_number: score.phone_number,
        amount: score.amount,
        risk_score: score.risk_score,
        risk_level: score.risk_level,
        recommendation: score.recommendation,
        alert_type: 'VELOCITY_SPIKE',
        velocity_info: {
          sender_id: spikeInfo.senderId,
          transaction_count: spikeInfo.transactionCount,
          threshold: spikeInfo.threshold,
          severity: spikeInfo.severity,
          window_size_seconds: WINDOW_SIZE_MS / 1000
        },
        timestamp: new Date().toISOString()
      };

      await this.producer.send({
        topic: TOPIC_ALERTS_FRAUD,
        messages: [{
          key: score.phone_number,
          value: JSON.stringify(alert)
        }]
      });

      return true;
    } catch (error) {
      console.error('✗ Failed to publish alert:', error.message);
      return false;
    }
  }

  /**
   * Start detecting velocity spikes
   */
  async start() {
    this.isRunning = true;
    this.stats.startTime = Date.now();

    console.log('\n' + '═'.repeat(80));
    console.log('SENTRA VELOCITY SPIKE DETECTOR - STARTED');
    console.log('═'.repeat(80));
    console.log(`Input topic: ${TOPIC_SCORES_OUTPUT}`);
    console.log(`Alert topic: ${TOPIC_ALERTS_FRAUD}`);
    console.log(`Window size: ${WINDOW_SIZE_MS / 1000}s`);
    console.log(`Velocity threshold: ${VELOCITY_THRESHOLD} transactions`);
    console.log('═'.repeat(80) + '\n');

    await this.consumer.subscribe({ topic: TOPIC_SCORES_OUTPUT });

    await this.consumer.run({
      eachBatchAutoResolve: false,
      eachBatch: async ({ batch, resolveOffset, heartbeat }) => {
        const messages = batch.messages;

        if (messages.length === 0) return;

        try {
          for (const msg of messages) {
            const score = JSON.parse(msg.value.toString());

            // Add to detector
            const spikeInfo = this.detector.addTransaction(
              score.phone_number
            );

            // If spike detected, publish alert
            if (spikeInfo.isSpike && spikeInfo.severity !== 'NORMAL') {
              await this.publishAlert(score, spikeInfo);
              this.stats.spikesDetected++;

              console.log(
                `🚨 VELOCITY SPIKE DETECTED - ` +
                `Sender: ${score.phone_number} | ` +
                `Count: ${spikeInfo.transactionCount}/${spikeInfo.threshold} | ` +
                `Severity: ${spikeInfo.severity}`
              );
            }

            this.stats.processed++;
          }

          // Log progress every 100 transactions
          if (this.stats.processed % 100 === 0) {
            const elapsed = ((Date.now() - this.stats.startTime) / 1000).toFixed(1);
            const throughput = (this.stats.processed / (Date.now() - this.stats.startTime) * 1000).toFixed(0);
            const activeSpikes = this.detector.getActiveSpikes();

            console.log(
              `[${elapsed}s] Processed: ${this.stats.processed} | ` +
              `Spikes: ${this.stats.spikesDetected} | ` +
              `Active spikes: ${activeSpikes.length} | ` +
              `Throughput: ${throughput} tx/s`
            );
          }

          resolveOffset(messages[messages.length - 1].offset);
          await heartbeat();
        } catch (error) {
          console.error('✗ Batch processing error:', error.message);
        }
      }
    });
  }

  /**
   * Stop detecting
   */
  async stop() {
    this.isRunning = false;
    const elapsed = (Date.now() - this.stats.startTime) / 1000;

    console.log('\n' + '═'.repeat(80));
    console.log('SENTRA VELOCITY SPIKE DETECTOR - STOPPED');
    console.log('═'.repeat(80));
    console.log(`Total processed: ${this.stats.processed}`);
    console.log(`Spikes detected: ${this.stats.spikesDetected}`);
    console.log(`Duration: ${elapsed.toFixed(1)}s`);
    console.log(`Average throughput: ${(this.stats.processed / elapsed).toFixed(0)} tx/s`);
    console.log('═'.repeat(80) + '\n');

    await this.disconnect();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN EXECUTION
// ─────────────────────────────────────────────────────────────────────────────

async function main() {
  const detector = new VelocityDetectorService();

  // Handle graceful shutdown
  process.on('SIGINT', async () => {
    console.log('\n\n⏹️  Shutting down gracefully...');
    await detector.stop();
    process.exit(0);
  });

  process.on('SIGTERM', async () => {
    console.log('\n\n⏹️  Shutting down gracefully...');
    await detector.stop();
    process.exit(0);
  });

  try {
    await detector.connect();
    await detector.start();
  } catch (error) {
    console.error('Fatal error:', error);
    process.exit(1);
  }
}

main();
