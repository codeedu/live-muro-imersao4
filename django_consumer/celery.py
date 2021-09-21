from __future__ import absolute_import, unicode_literals

import os
from celery import Celery, bootsteps
import kombu
import logging
logger = logging.getLogger(__name__)
# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_consumer.settings')
app = Celery('django_consumer')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

def rabbitmq_conn():
    return app.pool.acquire(block=True)


def rabbitmq_producer():
    return app.producer_pool.acquire(block=True)


with rabbitmq_conn() as conn:

    dlx_exchange = kombu.Exchange(
        name='dlx.amq.direct', 
        type='direct',
        channel=conn
    )
    dlx_exchange.declare()

    queue = kombu.Queue(
        name='orders',
        exchange='amq.direct',
        routing_key='orders',
        channel=conn,
        durable=True,
        queue_arguments={
            'x-dead-letter-exchange': 'dlx.amq.direct',
            'x-dead-letter-routing-key': 'orders',
        }
    )
    queue.declare()

    dead_letter_queue = kombu.Queue(
        name='dlx.orders',
        exchange='dlx.amq.direct',
        routing_key='orders',
        channel=conn,
        durable=True,
        queue_arguments={
            'x-dead-letter-exchange': 'amq.direct',
            'x-message-ttl': 20000,
        }
    )
    dead_letter_queue.declare()

class PaymentCreateConsumerStep(bootsteps.ConsumerStep):

    def get_consumers(self, channel):
        return [
            kombu.Consumer(
                channel,
                queues=[queue],
                callbacks=[self.handle_message],
                accept=['json']
            )
        ]

    def handle_message(self, payload, message):

        from app.models import Payment
        from app.serializers import PaymentSerializer
        from rest_framework.exceptions import ValidationError
        from random import randrange

        try:
            count = message.properties['application_headers']['x-death'][0]['count']
            if count >= 4:
                print('deu zica 4 vezes, já era')
                message.ack()
                return
        except KeyError:
            pass

        try:
            print(payload, message.properties)
            serializer = PaymentSerializer(data=payload)
            serializer.is_valid(raise_exception=True)
            data = {**serializer.validated_data, 'amount': serializer.validated_data['amount'] if randrange(10) % 2 == 0 else "fake"}
            print(data)
            payment = Payment.objects.create(**data)
            with rabbitmq_producer() as producer:
                producer.publish(
                    {
                        **serializer.validated_data, 
                        'transaction_id': payment.id,
                    },
                    serializer='json',
                    routing_key="transactions",
                    exchange='amq.direct',
                )
            message.ack()
        except Exception as e:
            logger.exception(e)
            if e.__class__ == ValidationError:
                body = {'status': 'error', 'error_message': e.detail}
                message.ack()
            else:
                body = {'status': 'error', 'error_message': str(e), **serializer.validated_data}
                with rabbitmq_producer() as producer:
                    producer.publish(
                        body,
                        serializer='json',
                        routing_key="transactions",
                        exchange='amq.direct',
                    )
                message.reject()



app.steps['consumer'].add(PaymentCreateConsumerStep)