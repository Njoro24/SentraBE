/**
 * ════════════════════════════════════════════════════════════════════════════════
 * STREAMING UTILITIES
 * ════════════════════════════════════════════════════════════════════════════════
 * 
 * Common utility functions used across all streaming services.
 * 
 * ════════════════════════════════════════════════════════════════════════════════
 */

const { v4: uuidv4 } = require('uuid');

// ─────────────────────────────────────────────────────────────────────────────
// LOGGING UTILITIES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Format timestamp for logging
 */
function formatTimestamp() {
  return new Date().toISOString();
}

/**
 * Log with timestamp
 */
function log(message, level = 'INFO') {
  const timestamp = formatTimestamp();
  console.log(`[${timestamp}] ${level}: ${message}`);
}

function logInfo(message) {
  log(message, 'INFO');
}

function logError(message) {
  log(message, 'ERROR');
}

function logWarn(message) {
  log(message, 'WARN');
}

function logDebug(message) {
  log(message, 'DEBUG');
}

// ─────────────────────────────────────────────────────────────────────────────
// STATISTICS UTILITIES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Calculate percentile from array of values
 */
function calculatePercentile(values, percentile) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.ceil((percentile / 100) * sorted.length) - 1;
  return sorted[Math.max(0, index)];
}

/**
 * Calculate average
 */
function calculateAverage(values) {
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

/**
 * Calculate statistics from array
 */
function calculateStats(values) {
  if (values.length === 0) {
    return {
      min: 0,
      max: 0,
      avg: 0,
      p50: 0,
      p95: 0,
      p99: 0,
      count: 0
    };
  }

  const sorted = [...values].sort((a, b) => a - b);
  return {
    min: sorted[0],
    max: sorted[sorted.length - 1],
    avg: calculateAverage(values),
    p50: calculatePercentile(values, 50),
    p95: calculatePercentile(values, 95),
    p99: calculatePercentile(values, 99),
    count: values.length
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// FORMATTING UTILITIES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Format bytes to human readable
 */
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Format duration in seconds to human readable
 */
function formatDuration(seconds) {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

/**
 * Format number with commas
 */
function formatNumber(num) {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Format throughput
 */
function formatThroughput(count, durationMs) {
  if (durationMs === 0) return '0 tx/s';
  const throughput = (count / (durationMs / 1000)).toFixed(0);
  return `${formatNumber(throughput)} tx/s`;
}

// ─────────────────────────────────────────────────────────────────────────────
// RETRY UTILITIES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Retry a function with exponential backoff
 */
async function retryWithBackoff(fn, maxRetries = 3, initialDelayMs = 100) {
  let lastError;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt < maxRetries - 1) {
        const delayMs = initialDelayMs * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }
  }

  throw lastError;
}

/**
 * Wait for a condition to be true
 */
async function waitFor(condition, timeoutMs = 30000, intervalMs = 100) {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    if (await condition()) {
      return true;
    }
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  return false;
}

// ─────────────────────────────────────────────────────────────────────────────
// DATA GENERATION UTILITIES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Generate realistic M-Pesa phone number
 */
function generatePhoneNumber() {
  const prefixes = [
    '0701', '0702', '0703', '0704', '0705', '0706', '0707', '0708', '0709',
    '0710', '0711', '0712', '0713', '0714', '0715', '0716', '0717', '0718',
    '0719', '0720', '0721', '0722', '0723', '0724', '0725'
  ];
  const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
  const number = Math.floor(Math.random() * 10000000).toString().padStart(7, '0');
  return prefix + number;
}

/**
 * Generate realistic device ID
 */
function generateDeviceId() {
  const chars = 'ABCDEF0123456789';
  let deviceId = '';
  for (let i = 0; i < 16; i++) {
    deviceId += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return deviceId;
}

/**
 * Generate realistic location
 */
function generateLocation() {
  const locations = [
    'Nairobi CBD', 'Westlands', 'Karen', 'Kilimani', 'Lavington',
    'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret', 'Kericho',
    'Thika', 'Machakos', 'Nyeri', 'Muranga', 'Kiambu',
    'Isiolo', 'Garissa', 'Wajir', 'Mandera', 'Lamu'
  ];
  return locations[Math.floor(Math.random() * locations.length)];
}

/**
 * Generate realistic transaction amount
 */
function generateAmount(isFraud = false) {
  if (isFraud) {
    const fraudAmounts = [50000, 100000, 150000, 200000, 250000, 500000, 1000000];
    return fraudAmounts[Math.floor(Math.random() * fraudAmounts.length)];
  }

  const rand = Math.random();
  if (rand < 0.6) {
    return Math.floor(Math.random() * 4900) + 100;
  } else if (rand < 0.9) {
    return Math.floor(Math.random() * 45000) + 5000;
  } else {
    return Math.floor(Math.random() * 450000) + 50000;
  }
}

/**
 * Generate realistic transaction
 */
function generateTransaction(isFraud = false) {
  return {
    transaction_id: uuidv4(),
    amount: generateAmount(isFraud),
    phone_number: generatePhoneNumber(),
    device_id: generateDeviceId(),
    location: generateLocation(),
    timestamp: new Date().toISOString(),
    is_fraud_pattern: isFraud
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// VALIDATION UTILITIES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Validate transaction object
 */
function validateTransaction(tx) {
  const required = ['transaction_id', 'amount', 'phone_number', 'device_id', 'location', 'timestamp'];
  const missing = required.filter(field => !tx[field]);

  if (missing.length > 0) {
    return {
      valid: false,
      error: `Missing fields: ${missing.join(', ')}`
    };
  }

  if (tx.amount <= 0) {
    return {
      valid: false,
      error: 'Amount must be positive'
    };
  }

  if (!/^0[0-9]{9}$/.test(tx.phone_number)) {
    return {
      valid: false,
      error: 'Invalid phone number format'
    };
  }

  return { valid: true };
}

/**
 * Validate score response
 */
function validateScore(score) {
  const required = ['transaction_id', 'risk_score', 'risk_level', 'recommendation'];
  const missing = required.filter(field => !score[field]);

  if (missing.length > 0) {
    return {
      valid: false,
      error: `Missing fields: ${missing.join(', ')}`
    };
  }

  if (score.risk_score < 0 || score.risk_score > 100) {
    return {
      valid: false,
      error: 'Risk score must be between 0 and 100'
    };
  }

  const validLevels = ['LOW', 'MEDIUM', 'HIGH'];
  if (!validLevels.includes(score.risk_level)) {
    return {
      valid: false,
      error: `Risk level must be one of: ${validLevels.join(', ')}`
    };
  }

  return { valid: true };
}

// ─────────────────────────────────────────────────────────────────────────────
// EXPORT
// ─────────────────────────────────────────────────────────────────────────────

module.exports = {
  // Logging
  log,
  logInfo,
  logError,
  logWarn,
  logDebug,
  formatTimestamp,

  // Statistics
  calculatePercentile,
  calculateAverage,
  calculateStats,

  // Formatting
  formatBytes,
  formatDuration,
  formatNumber,
  formatThroughput,

  // Retry
  retryWithBackoff,
  waitFor,

  // Data generation
  generatePhoneNumber,
  generateDeviceId,
  generateLocation,
  generateAmount,
  generateTransaction,

  // Validation
  validateTransaction,
  validateScore
};
