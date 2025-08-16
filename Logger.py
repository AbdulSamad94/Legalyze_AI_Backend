from datetime import datetime


class SimpleLogger:
    @staticmethod
    def log(step: str, details: str = ""):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {step} {details}")
