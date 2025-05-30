import asyncio
import aio_pika
import json
import os

from services.crud import create_team_request_in_db_sync

RABBITMQ_USER_DEFAULT = "guest"
RABBITMQ_PASSWORD_DEFAULT = "guest"
RABBITMQ_HOST_DEFAULT = "rabbitmq"
RABBITMQ_PORT_DEFAULT = "5672"
RABBITMQ_VHOST_DEFAULT = "/"

RABBITMQ_URL = os.getenv("RABBITMQ_URL")

if not RABBITMQ_URL:
    user = os.getenv("RABBITMQ_USER", RABBITMQ_USER_DEFAULT)
    password = os.getenv("RABBITMQ_PASSWORD", RABBITMQ_PASSWORD_DEFAULT)
    host = os.getenv("RABBITMQ_HOST", RABBITMQ_HOST_DEFAULT)
    port = os.getenv("RABBITMQ_PORT", RABBITMQ_PORT_DEFAULT)
    vhost = os.getenv("RABBITMQ_VHOST", RABBITMQ_VHOST_DEFAULT)

    if not vhost or vhost == "/":
        vhost_path = ""
    elif not vhost.startswith("/"):
        vhost_path = "/" + vhost
    else:
        vhost_path = vhost

    RABBITMQ_URL = f"amqp://{user}:{password}@{host}:{port}{vhost_path}"
    print(f"INFO: RABBITMQ_URL não estava definida no ambiente. URL montada: {RABBITMQ_URL}")
else:
    print(f"INFO: Usando RABBITMQ_URL definida no ambiente: {RABBITMQ_URL}")


TEAMS_COMMANDS_EXCHANGE = "teams_commands_exchange"
REQUESTS_TEAM_CREATION_QUEUE = "requests_service.queue.team_creation"
ROUTING_KEY_TEAM_CREATION = "team.creation.requested"


async def on_message(message: aio_pika.IncomingMessage) -> None:
    async with message.process():
        try:
            data = json.loads(message.body.decode())
            print(f" [requests_service] Received message: {data}")
            print(f" [requests_service] Routing Key: {message.routing_key}")

            if hasattr(asyncio, 'to_thread'):
                db_result = await asyncio.to_thread(create_team_request_in_db_sync, data)
            else:
                loop = asyncio.get_event_loop()
                db_result = await loop.run_in_executor(None, create_team_request_in_db_sync, data)

            print(f" [requests_service] Resultado do processamento do DB: {db_result}")

        except json.JSONDecodeError as e:
            print(f" [requests_service] Erro ao decodificar JSON: {e}. Mensagem será rejeitada.")
            raise
        except Exception as e:
            print(f" [requests_service] Erro inesperado ao processar mensagem ou DB: {e}")
            raise


async def main_consumer():
    connection = None
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)

        async with connection:
            channel = await connection.channel()

            await channel.set_qos(prefetch_count=10)

            exchange = await channel.declare_exchange(
                TEAMS_COMMANDS_EXCHANGE,
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )

            queue = await channel.declare_queue(
                REQUESTS_TEAM_CREATION_QUEUE,
                durable=True
            )

            await queue.bind(exchange, routing_key=ROUTING_KEY_TEAM_CREATION)

            print(
                f" [*] '{REQUESTS_TEAM_CREATION_QUEUE}' está esperando por mensagens com routing key '{ROUTING_KEY_TEAM_CREATION}'. Para sair pressione CTRL+C")

            await queue.consume(on_message)

            await asyncio.Future()

    except aio_pika.exceptions.AMQPConnectionError as e:
        print(f"Erro de conexão com RabbitMQ no consumidor: {e}")
        await asyncio.sleep(5)
    except KeyboardInterrupt:
        print("Consumidor interrompido.")
    finally:
        if connection and not connection.is_closed:
            await connection.close()
        print("Conexão do consumidor fechada.")


if __name__ == "__main__":
    try:
        asyncio.run(main_consumer())
    except KeyboardInterrupt:
        print("Programa encerrado.")