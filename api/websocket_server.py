"""
WebSocket Alert Server — Phase 4
Runs on port 8080, pushes fraud alerts to connected dashboard clients.
Consumes from sentra.alerts.fraud Kafka topic.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Set

import websockets
from dotenv import load_dotenv
from kafka import KafkaConsumer

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BOOTSTRAP      = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
ALERT_TOPIC    = "sentra.alerts.fraud"
WS_HOST        = "0.0.0.0"
WS_PORT        = 8080

# SASL config
SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
SASL_MECHANISM    = os.getenv("KAFKA_SASL_MECHANISM", "PLAIN")
SASL_USERNAME     = os.getenv("KAFKA_SASL_USERNAME", "")
SASL_PASSWORD     = os.getenv("KAFKA_SASL_PASSWORD", "")


def kafka_sasl_config():
    if SECURITY_PROTOCOL == "SASL_PLAINTEXT":
        return {
            "security_protocol": SECURITY_PROTOCOL,
            "sasl_mechanism":    SASL_MECHANISM,
            "sasl_plain_username": SASL_USERNAME,
            "sasl_plain_password": SASL_PASSWORD,
        }
    return {}


# Connected clients: websocket -> {client_id, api_key, connected_at}
connected_clients: Dict = {}
alert_queue: asyncio.Queue = None


async def handle_client(websocket, path):
    """Handle a new WebSocket client connection"""
    client_info = {
        "client_id": None,
        "api_key": None,
        "connected_at": datetime.utcnow().isoformat()
    }
    connected_clients[websocket] = client_info
    log.info(f"Client connected. Total: {len(connected_clients)}")

    try:
        # Wait for auth message
        try:
            auth_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
            auth_data = json.loads(auth_msg)

            if auth_data.get("type") == "auth":
                client_info["client_id"] = auth_data.get("client_id")
                client_info["api_key"]   = auth_data.get("api_key")

                await websocket.send(json.dumps({
                    "type": "auth_success",
                    "data": {"message": "Authenticated successfully"}
                }))
                log.info(f"Client {client_info['client_id']} authenticated")

                # Send status
                await websocket.send(json.dumps({
                    "type": "status",
                    "data": {
                        "message": "Connected to Sentra Alert Stream",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }))
        except asyncio.TimeoutError:
            await websocket.send(json.dumps({
                "type": "error",
                "data": {"message": "Authentication timeout"}
            }))
            return

        # Keep connection alive — handle pings and disconnects
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
            except Exception:
                pass

    except websockets.exceptions.ConnectionClosed:
        log.info(f"Client {client_info.get('client_id')} disconnected")
    finally:
        connected_clients.pop(websocket, None)
        log.info(f"Client removed. Total: {len(connected_clients)}")


async def broadcast_alert(alert: dict):
    """Send alert to all connected authenticated clients"""
    if not connected_clients:
        return

    message = json.dumps({
        "type": "fraud_alert",
        "data": alert
    })

    disconnected = []
    for websocket, info in connected_clients.items():
        try:
            await websocket.send(message)
        except Exception:
            disconnected.append(websocket)

    for ws in disconnected:
        connected_clients.pop(ws, None)


async def kafka_consumer_loop():
    """Consume alerts from Kafka and push to WebSocket clients"""
    log.info(f"Starting Kafka consumer on topic: {ALERT_TOPIC}")

    loop = asyncio.get_event_loop()

    def consume():
        import time
        retries = 0
        while True:
            try:
                consumer = KafkaConsumer(
                    ALERT_TOPIC,
                    bootstrap_servers=BOOTSTRAP,
                    group_id="sentra-websocket-server",
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    consumer_timeout_ms=-1,
                    fetch_max_wait_ms=500,
                    **kafka_sasl_config()
                )
                log.info("Kafka consumer connected")
                retries = 0
                for msg in consumer:
                    alert_queue.put_nowait(msg.value)
            except Exception as e:
                retries += 1
                wait = min(30, 2 ** retries)
                log.error(f"Kafka consumer error (retry {retries} in {wait}s): {e}")
                time.sleep(wait)

    # Run Kafka consumer in thread pool
    await loop.run_in_executor(None, consume)


async def queue_processor():
    """Process alerts from queue and broadcast to WebSocket clients"""
    while True:
        try:
            alert = await asyncio.wait_for(alert_queue.get(), timeout=1.0)
            await broadcast_alert(alert)
            log.info(f"Alert broadcast to {len(connected_clients)} clients: {alert.get('transaction_id')}")
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            log.error(f"Queue processor error: {e}")


async def stats_broadcaster():
    """Broadcast server stats every 30 seconds"""
    while True:
        await asyncio.sleep(30)
        if connected_clients:
            stats = {
                "type": "status",
                "data": {
                    "connected_clients": len(connected_clients),
                    "timestamp": datetime.utcnow().isoformat(),
                    "server": "Sentra Alert Stream v1.0"
                }
            }
            message = json.dumps(stats)
            for websocket in list(connected_clients.keys()):
                try:
                    await websocket.send(message)
                except Exception:
                    pass


async def kafka_consumer_loop_safe():
    """Kafka consumer with retry — never crashes the server"""
    while True:
        try:
            await kafka_consumer_loop()
        except Exception as e:
            log.error(f"Kafka consumer error: {e} — retrying in 5s")
            await asyncio.sleep(5)


async def main():
    global alert_queue
    alert_queue = asyncio.Queue(maxsize=1000)

    log.info(f"Starting WebSocket server on ws://{WS_HOST}:{WS_PORT}")

    # Start WebSocket server FIRST — independent of Kafka
    ws_server = await websockets.serve(handle_client, WS_HOST, WS_PORT)
    log.info(f"WebSocket server listening on port {WS_PORT}")

    # Kafka consumer and queue processor run alongside — failures don't kill WS
    await asyncio.gather(
        kafka_consumer_loop_safe(),
        queue_processor(),
        stats_broadcaster(),
    )


if __name__ == "__main__":
    asyncio.run(main())
