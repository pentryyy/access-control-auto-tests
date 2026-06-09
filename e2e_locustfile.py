from locust import HttpUser, task, constant, events
import os
import json
import time
import threading
from paho.mqtt import client as mqtt_client
from locust.user.wait_time import constant


class AccessControlE2EUser(HttpUser):
    host = "http://localhost:8082"
    wait_time = constant(0.5)

    MQTT_CONFIG = {
        'broker': 'broker.emqx.io',
        'port': 1883,
        'card_topic': 'vkrtopic_esp_card/mqtt',
        'door_topic': 'vkrtopic_esp_door/mqtt',
        'username': 'pentryyy',
        'password': '12345678',
        'client_id': f'locust_test_{os.getpid()}'
    }

    def on_start(self):
        image_path = r"C:\Users\pentryyy\Desktop\pre_backend_stuff\img\face4.jpg"
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Файл не найден: {image_path}")
        with open(image_path, "rb") as f:
            self.image_bytes = f.read()
        print(f"[OK] Изображение загружено: {len(self.image_bytes)} байт")

        self.mqtt_client = mqtt_client.Client(
            client_id=f"{self.MQTT_CONFIG['client_id']}_{id(self)}",
            userdata=self
        )
        self.mqtt_client.username_pw_set(
            self.MQTT_CONFIG['username'],
            self.MQTT_CONFIG['password']
        )
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_connect = self.on_mqtt_connect

        try:
            self.mqtt_client.connect(
                self.MQTT_CONFIG['broker'],
                self.MQTT_CONFIG['port'],
                keepalive=60
            )
            self.mqtt_client.loop_start()
            print(f"[OK] MQTT подключен к {self.MQTT_CONFIG['broker']}")
        except Exception as e:
            print(f"[ERROR] MQTT подключение не удалось: {e}")
            raise

        self.door_responses = []
        self.response_lock = threading.Lock()

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("[OK] MQTT connected successfully")
            client.subscribe(self.MQTT_CONFIG['door_topic'], qos=2)
        else:
            print(f"[ERROR] MQTT connection failed with code {rc}")

    def on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            with userdata.response_lock:
                userdata.door_responses.append({
                    'topic': msg.topic,
                    'payload': payload,
                    'timestamp': time.time()
                })
            print(f"[MQTT MSG] {msg.topic}: {payload}")
        except Exception as e:
            print(f"[ERROR] MQTT message parse error: {e}")

    @task
    def e2e_access_control(self):
        start_time = time.time()
        card_number = "A2D8F4BC36E971"

        with self.response_lock:
            self.door_responses.clear()

        mqtt_payload = {
            "device_index": 0,
            "device_id": 2,
            "card_number": card_number
        }

        try:
            result = self.mqtt_client.publish(
                self.MQTT_CONFIG['card_topic'],
                json.dumps(mqtt_payload),
                qos=2
            )
            result.wait_for_publish()
            print(f"[SENT] MQTT карта: {card_number}")

            timeout = 5.0
            response_found = False
            door_command = None

            for _ in range(50):
                with self.response_lock:
                    if self.door_responses:
                        response = self.door_responses.pop(0)
                        door_command = response['payload'].get('command')
                        response_found = True
                        break
                time.sleep(0.1)

            elapsed_time = time.time() - start_time

            if response_found:
                if door_command == "opendoor":
                    events.request.fire(
                        request_type="E2E_MQTT",
                        name="/access/verified",
                        response_time=elapsed_time * 1000,  # в мс
                        response_length=len(json.dumps(mqtt_payload)),
                        exception=None
                    )
                    print(f"[SUCCESS] Дверь открыта за {elapsed_time * 1000:.0f}мс")
                else:
                    events.request.fire(
                        request_type="E2E_MQTT",
                        name="/access/denied",
                        response_time=elapsed_time * 1000,
                        response_length=len(json.dumps(mqtt_payload)),
                        exception=None
                    )
                    print(f"[DENIED] Доступ запрещён: {door_command}")
            else:
                events.request.fire(
                    request_type="E2E_MQTT",
                    name="/access/timeout",
                    response_time=timeout * 1000,
                    response_length=len(json.dumps(mqtt_payload)),
                    exception=TimeoutError("No MQTT response within timeout")
                )
                print(f"[TIMEOUT] Нет ответа за {timeout}сек")

        except Exception as e:
            events.request.fire(
                request_type="E2E_MQTT",
                name="/access/error",
                response_time=(time.time() - start_time) * 1000,
                response_length=0,
                exception=e
            )
            print(f"[ERROR] {e}")

    def on_stop(self):
        if hasattr(self, 'mqtt_client'):
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("[OK] MQTT отключен")


if __name__ == "__main__":
    import subprocess

    subprocess.run([
        "locust", "-f", __file__,
        "--users", "10",
        "--spawn-rate", "2",
        "--run-time", "60s",
        "--headless"
    ])