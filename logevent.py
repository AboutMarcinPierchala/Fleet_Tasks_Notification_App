from datetime import datetime



def log_event(log_message):

    today = datetime.today()
    file_path = f"Logs/{today.date()}.txt"
    log_message = f"{today}: -> {log_message}.\n"

    try:
        with open(file_path, 'x') as file:
            file.write(log_message)
    except FileExistsError:
        with open(file_path,'a') as file:
                file.write(log_message)
