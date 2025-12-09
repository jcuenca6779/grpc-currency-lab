import time
from concurrent import futures
import grpc
import currency_pb2
import currency_pb2_grpc
import requests

# Tasas simuladas: map[from][to] = rate (1 unit of from = rate units of to)
SIMULATED_RATES = {
    "USD": {"EUR": 0.92, "GBP": 0.78, "USD": 1.0, "JPY": 150.0},
    "EUR": {"USD": 1.087, "GBP": 0.85, "EUR": 1.0, "JPY": 163.0},
    "GBP": {"USD": 1.28, "EUR": 1.17, "GBP": 1.0, "JPY": 190.0},
}

SUPPORTED = [
    ("USD", "United States Dollar"),
    ("EUR", "Euro"),
    ("GBP", "British Pound"),
    ("JPY", "Japanese Yen"),
]

class CurrencyConverterServicer(currency_pb2_grpc.CurrencyConverterServicer):
    def Convert(self, request, context):
        from_c = request.from_currency.upper()
        to_c = request.to_currency.upper()
        amt = request.amount

        print(f"[Solicitud] Convertir {amt} {from_c} a {to_c}")
        
        rate = 0.0
        usando_api = False

        # 1. INTENTO CON API REAL (Frankfurter)
        try:
            # La API requiere que from y to sean distintos
            if from_c != to_c:
                url = f"https://api.frankfurter.app/latest?amount=1&from={from_c}&to={to_c}"
                response = requests.get(url, timeout=2) # Timeout corto para no bloquear
                if response.status_code == 200:
                    data = response.json()
                    rate = data['rates'][to_c]
                    usando_api = True
                    print(f"   (Usando API Real: Tasa {rate})")
            else:
                rate = 1.0
        except Exception as e:
            print(f"   (Fallo API, usando datos locales: {e})")

        # 2. FALLBACK: Si la API falló, usar diccionario local
        if not usando_api and rate == 0.0:
            if from_c in SIMULATED_RATES and to_c in SIMULATED_RATES[from_c]:
                rate = SIMULATED_RATES[from_c][to_c]
            elif to_c in SIMULATED_RATES and from_c in SIMULATED_RATES[to_c]:
                rate = 1.0 / SIMULATED_RATES[to_c][from_c]
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Tasa no encontrada para {from_c} -> {to_c}")
                return currency_pb2.ConvertReply()

        return currency_pb2.ConvertReply(
            converted_amount=amt * rate,
            rate=rate,
            from_currency=from_c,
            to_currency=to_c
        )

    def GetSupportedCurrencies(self, request, context):
        for code, name in SUPPORTED:
            yield currency_pb2.Currency(code=code, name=name)

    def StreamRates(self, request, context):
        # Simula envíos periódicos de tasas (ejemplo didáctico)
        while True:
            for from_c, targets in SIMULATED_RATES.items():
                for to_c, rate in targets.items():
                    if from_c == to_c:
                        continue
                    reply = currency_pb2.ConvertReply(
                        converted_amount=rate, # en este stream 'converted_amount' usaremos como valor de tasa
                        rate=rate,
                        from_currency=from_c,
                        to_currency=to_c
                    )
                    yield reply
                    time.sleep(0.5)  # espera simulada
            # repetir (podrías agregar lógica para salir si context.is_active() == False)
            # IMPLEMENTACIÓN DEL DESAFÍO: GetRate
    def GetRate(self, request, context):
        from_c = request.from_currency.upper()
        to_c = request.to_currency.upper()
        
        print(f"[GetRate] Solicitando tasa de {from_c} a {to_c}")

        # Reutilizamos la lógica de búsqueda del diccionario
        rate = 0.0
        if from_c in SIMULATED_RATES and to_c in SIMULATED_RATES[from_c]:
            rate = SIMULATED_RATES[from_c][to_c]
        elif to_c in SIMULATED_RATES and from_c in SIMULATED_RATES[to_c]:
            rate = 1.0 / SIMULATED_RATES[to_c][from_c]
        else:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Tasa no encontrada para {from_c} -> {to_c}")
            return currency_pb2.RateReply()

        return currency_pb2.RateReply(rate=rate)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    currency_pb2_grpc.add_CurrencyConverterServicer_to_server(CurrencyConverterServicer(), server)
    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)
    server.start()
    print(f"gRPC CurrencyConverter server started on {listen_addr}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("Server stopping")

if __name__ == "__main__":
    serve()
