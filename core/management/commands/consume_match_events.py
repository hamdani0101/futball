"""Consume live football match events from Kafka."""

from django.core.management.base import BaseCommand

from analytics.services.kafka_consumer import KafkaConsumerSettings, MatchEventConsumer


class Command(BaseCommand):
    help = "Consume live match events from Kafka and persist them to the database"

    def add_arguments(self, parser):
        parser.add_argument("--bootstrap-servers", default="localhost:9092")
        parser.add_argument("--topic", default="match_events")
        parser.add_argument("--group-id", default="futball-live-event-writers")
        parser.add_argument("--client-id", default="futball-live-event-consumer")

    def handle(self, *args, **options):
        consumer = MatchEventConsumer(
            KafkaConsumerSettings(
                bootstrap_servers=options["bootstrap_servers"],
                topic=options["topic"],
                group_id=options["group_id"],
                client_id=options["client_id"],
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Consuming Kafka topic {options['topic']} as {options['group_id']}"
            )
        )
        consumer.run_forever()
