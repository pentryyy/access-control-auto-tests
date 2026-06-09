# Запуск Тестов

# Интеграционные Тесты

```
locust -f integration_locustfile.py --users 50 --spawn-rate 10 --run-time 60s --headless --csv=results/locust_results --html=results/locust_report.html
```
