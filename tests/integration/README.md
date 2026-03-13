# Sentra Integration Test Suite

Complete, production-grade test suite for the Sentra fraud detection platform covering all 4 layers of testing.

## Quick Start

### Run Full Test Suite

```bash
python tests/integration/run_all.py
```

This runs all 4 layers in sequence and generates a final report.

### Run Individual Layers

```bash
# Layer 4: End-to-End Pipeline
pytest tests/integration/test_layer4_e2e.py -v

# Layer 3: Stress & Chaos Tests
pytest tests/integration/test_layer3_stress.py -v

# Layer 2: Cross-Phase Integration
pytest tests/integration/test_layer2_integration.py -v

# Layer 1: Component Tests
pytest tests/integration/test_layer1_components.py -v
```

### Run Specific Test

```bash
pytest tests/integration/test_layer4_e2e.py::TestEndToEndPipeline::test_full_10_step_pipeline -v
```

## Test Structure

### Layer 4: End-to-End Pipeline (test_layer4_e2e.py)

Full 10-step transaction flow through all system components:

1. JWT generation
2. T24 mock fetch
3. Adapter transformation & encryption
4. Scoring endpoint
5. Kafka publish
6. WebSocket alert
7. Audit log entry
8. Audit chain integrity
9. Alert feedback
10. Graph edge

**Expected Result**: All 10 steps complete in under 10 seconds

### Layer 3: Stress & Chaos Tests (test_layer3_stress.py)

- **TestLoadTest**: 200 concurrent requests, measure p50/p95/p99 latency
- **TestConcurrencyTest**: 100 simultaneous requests at exact same moment
- **TestChaosTest**: Invalid tokens, malformed payloads, expired tokens

**Expected Result**: Zero 500 errors, p95 latency under 500ms

### Layer 2: Cross-Phase Integration (test_layer2_integration.py)

- **TestP1AndP6**: Scoring + Security (JWT validation)
- **TestP5AndP6**: T24 Adapter + Security (field encryption)
- **TestP2AndP4**: Streaming + Dashboard (Kafka + WebSocket)
- **TestP1AndP3**: Scoring + Graph (fraud ring detection)

**Expected Result**: All cross-phase interactions work correctly

### Layer 1: Component Tests (test_layer1_components.py)

- **TestPhase1ScoringAPI**: Required fields, latency, malformed inputs, extreme values
- **TestPhase2Streaming**: Kafka producer/consumer
- **TestPhase3GraphDetection**: Fraud ring detection
- **TestPhase4Dashboard**: WebSocket, feedback
- **TestPhase5T24Adapter**: Transformation, error handling, lossless round-trip
- **TestPhase6Security**: Existing test regression guard

**Expected Result**: All components function correctly in isolation

## External Service Requirements

Some tests require external services. If a service is not running, the test will skip gracefully:

| Service | Tests Affected | Behavior |
|---------|---|---|
| PostgreSQL | Layer 4 Step 4, Layer 3, Layer 2 P1P6, Layer 1 Phase 1 | Skips with warning |
| Kafka | Layer 4 Step 5, Layer 2 P2P4, Layer 1 Phase 2 | Skips with warning |
| Neo4j | Layer 4 Step 10, Layer 2 P1P3, Layer 1 Phase 3 | Skips with warning |
| WebSocket Server | Layer 4 Step 6, Layer 2 P2P4, Layer 1 Phase 4 | Skips with warning |

## Expected Output

### Successful Run

```
================================================================================
SENTRA — Full System Test Suite
================================================================================
Started: 2024-03-13 14:30:00

================================================================================
Running Layer 4: End-to-End Pipeline...
================================================================================

...test output...

Layer 4: End-to-End Pipeline Summary:
  Tests: 1
  Passed: 1
  Failed: 0
  Skipped: 0
  Duration: 2.34s

...more layers...

================================================================================
FINAL TEST REPORT
================================================================================
Layer                                    Tests      Passed     Failed     Skipped    Duration
--------------------------------------------------------------------------------
Layer 4: End-to-End Pipeline             1          1          0          0          2.34s
Layer 3: Stress & Chaos                  4          4          0          0          5.67s
Layer 2: Cross-Phase Integration         8          6          0          2          3.21s
Layer 1: Component Tests                 15         12         0          3          4.56s
--------------------------------------------------------------------------------
TOTAL                                    28         23         0          5          15.78s
================================================================================

================================================================================
ALL SYSTEMS GO
================================================================================

Completed: 2024-03-13 14:30:16
Total Duration: 15.78s
```

### With Failures

```
================================================================================
FAILURES DETECTED — 2 test(s) failed
See table above for details
================================================================================
```

## Fixtures

All tests use shared fixtures from `conftest.py`:

- `async_client`: Async HTTP client for FastAPI testing
- `valid_admin_token`: Valid JWT token with admin role
- `valid_analyst_token`: Valid JWT token with analyst role
- `expired_token`: Expired JWT token
- `sample_transaction_payload`: Valid transaction payload
- `sample_t24_transaction`: Valid T24-format transaction

## Running with Docker

```bash
# Start all services
docker-compose up -d

# Run tests
python tests/integration/run_all.py

# Stop services
docker-compose down
```

## Debugging

### Run with verbose output

```bash
pytest tests/integration/test_layer4_e2e.py -vv -s
```

### Run with logging

```bash
pytest tests/integration/test_layer4_e2e.py -v --log-cli-level=DEBUG
```

### Run specific test class

```bash
pytest tests/integration/test_layer3_stress.py::TestLoadTest -v
```

## Performance Benchmarks

Expected performance on local hardware:

| Metric | Target | Typical |
|--------|--------|---------|
| Single score request | < 200ms | 45-80ms |
| 200 concurrent requests (p95) | < 500ms | 120-250ms |
| Full Layer 4 pipeline | < 10s | 2-4s |
| All 4 layers | < 60s | 15-25s |

## Troubleshooting

### Tests skip with "Database not available"

PostgreSQL is not running. Start it:

```bash
docker-compose up -d postgres
```

### Tests skip with "Kafka not available"

Kafka is not running. Start it:

```bash
docker-compose up -d kafka
```

### Tests skip with "Neo4j not available"

Neo4j is not running. Start it:

```bash
docker-compose up -d neo4j
```

### Tests skip with "WebSocket server not available"

WebSocket server is not running. Start the backend:

```bash
uvicorn api.main:app --reload
```

## CI/CD Integration

The master runner exits with appropriate codes for CI/CD:

```bash
python tests/integration/run_all.py
echo $?  # 0 if all pass, 1 if any fail
```

Use in GitHub Actions:

```yaml
- name: Run Integration Tests
  run: python tests/integration/run_all.py
```

## Notes

- All tests are independent and can run in any order
- Tests gracefully skip when external services are unavailable
- No test modifies existing data outside the test scope
- All async tests use pytest-asyncio
- Fixtures are automatically provided by conftest.py
