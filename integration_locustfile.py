from locust import HttpUser, task, constant
import os

class AccessControlUser(HttpUser):
    host = "http://localhost:8082"
    wait_time = constant(0.1)
    
    def on_start(self):
        image_path = r"C:\Users\pentryyy\Desktop\pre_backend_stuff\img\face4.jpg"
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Файл не найден: {image_path}")
        with open(image_path, "rb") as f:
            self.image_bytes = f.read()
        print(f"[OK] Изображение загружено в память: {len(self.image_bytes)} байт")
    
    @task
    def verify_access(self):
        with self.client.post(
            "/api/v1/verification/access",
            data=self.image_bytes,
            headers={
                "X-Card-Number": "A2D8F4BC36E971",
                "X-Device-Id": "1",
                "Content-Type": "image/jpeg"
            },
            catch_response=True,
            name="/api/v1/verification/access"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("success") is True:
                        response.success()
                    else:
                        response.failure(f"success=false: {response.text[:100]}")
                except Exception as e:
                    response.failure(f"JSON parse error: {e}")
            else:
                response.failure(f"Status {response.status_code}: {response.text[:100]}")