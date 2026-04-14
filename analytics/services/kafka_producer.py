"""Kafka producer for live football match events."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


class KafkaProducerError(RuntimeError):
    """Raised when a live event cannot be delivered to Kafka."""


@dataclass(frozen=True)
class KafkaProducerSettings:
    bootstrap_servers: str = "localhost:9092"
    topic: str = "match_events"
    client_id: str = "futball-live-event-producer"
    flush_timeout_seconds: float = 10.0
    max_retries: int = 3
    retry_backoff_seconds: float = 0.5
    reconnect_on_failure: bool = True


class MatchEventProducer:
    """Reliable Kafka producer for schema-compliant football events."""

    REQUIRED_FIELDS = {
        "event_id",
        "event_type",
        "match_id",
        "team_id",
        "player_id",
        "period",
        "minute",
        "second",
        "payload",
    }

    def __init__(self, settings: KafkaProducerSettings | None = None, **overrides):
        self.settings = settings or KafkaProducerSettings(**overrides)
        self._producer = self._build_producer()

    def send_event(self, event: dict[str, Any]) -> None:
        """Validate and publish one event JSON object to Kafka."""
        self._validate_event(event)

        payload = self._serialize_event(event)
        key = str(event["match_id"]).encode("utf-8")
        last_error = None

        for attempt in range(1, self.settings.max_retries + 1):
            delivery = _DeliveryState()

            try:
                self._producer.produce(
                    self.settings.topic,
                    key=key,
                    value=payload,
                    on_delivery=delivery.callback,
                    headers={
                        "event_type": str(event["event_type"]).encode("utf-8"),
                        "schema_version": str(event.get("schema_version", "1.0")).encode(
                            "utf-8"
                        ),
                    },
                )
                remaining = self._producer.flush(self.settings.flush_timeout_seconds)

                if remaining == 0 and delivery.delivered and delivery.error is None:
                    logger.info(
                        "Kafka match event delivered",
                        extra={
                            "event_id": event["event_id"],
                            "match_id": event["match_id"],
                            "topic": self.settings.topic,
                            "partition": delivery.partition,
                            "offset": delivery.offset,
                        },
                    )
                    return

                last_error = delivery.error or "delivery timed out"

            except BufferError as exc:
                last_error = exc
                self._producer.poll(0.5)
            except Exception as exc:
                last_error = exc
                if self.settings.reconnect_on_failure:
                    self._reconnect_producer()

            logger.warning(
                "Kafka match event delivery failed; retrying",
                extra={
                    "event_id": event["event_id"],
                    "match_id": event["match_id"],
                    "attempt": attempt,
                    "max_retries": self.settings.max_retries,
                    "error": str(last_error),
                },
            )
            time.sleep(self.settings.retry_backoff_seconds * attempt)

        raise KafkaProducerError(
            f"Failed to publish event {event['event_id']} "
            f"to {self.settings.topic}: {last_error}"
        )

    def close(self) -> None:
        """Flush pending messages before shutdown."""
        self._producer.flush(self.settings.flush_timeout_seconds)

    def _serialize_event(self, event: dict[str, Any]) -> bytes:
        return json.dumps(event, separators=(",", ":"), default=str).encode("utf-8")

    def _reconnect_producer(self) -> None:
        try:
            self._producer.flush(self.settings.flush_timeout_seconds)
        except Exception:
            logger.debug("Kafka producer flush failed during reconnect", exc_info=True)
        self._producer = self._build_producer()

    def _build_producer(self):
        try:
            from confluent_kafka import Producer
        except ImportError as exc:
            raise KafkaProducerError(
                "confluent-kafka is required to publish match events. "
                "Install project dependencies before running the producer."
            ) from exc

        return Producer(
            {
                "bootstrap.servers": self.settings.bootstrap_servers,
                "client.id": self.settings.client_id,
                "acks": "all",
                "enable.idempotence": True,
                "retries": 5,
                "retry.backoff.ms": 500,
                "message.send.max.retries": 5,
                "delivery.timeout.ms": 120000,
                "request.timeout.ms": 30000,
                "linger.ms": 5,
                "compression.type": "snappy",
            }
        )

    def _validate_event(self, event: dict[str, Any]) -> None:
        missing = sorted(field for field in self.REQUIRED_FIELDS if field not in event)
        if missing:
            raise ValueError(f"Missing required event field(s): {', '.join(missing)}")

        if not isinstance(event["payload"], dict):
            raise ValueError("Event payload must be a JSON object")

        if event["event_type"] in {"pass", "shot", "foul"}:
            location = event["payload"].get("location") or event["payload"].get(
                "start_location"
            )
            if not location:
                raise ValueError(f"{event['event_type']} event requires pitch coordinates")


@dataclass
class _DeliveryState:
    error: Any = None
    partition: int | None = None
    offset: int | None = None
    delivered: bool = False

    def callback(self, error, message) -> None:
        self.error = error
        self.delivered = error is None
        if message is not None:
            self.partition = message.partition()
            self.offset = message.offset()


def publish_match_event(event: dict[str, Any], **producer_settings) -> None:
    """Convenience function for publishing one match event."""
    producer = MatchEventProducer(**producer_settings)
    try:
        producer.send_event(event)
    finally:
        producer.close()
