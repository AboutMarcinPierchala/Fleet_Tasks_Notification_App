from app import job_2, job_1
from logevent import log_event

try:
    job_1()
    job_2()
    log_event("Wykonał się scheduler_cron")
except Exception as e:
    log_event(f"Podczas wykoywania scheduler_cron nastąpił błąd: {e}")