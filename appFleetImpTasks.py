from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import smtplib
import utylity
from logevent import log_event
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
import re

restart = True

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fleet_management.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
if(restart):
    log_event("Aplikacja zostala zrestartowana lub uruchomiona.")

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
is_logged = False

# Model bazy danych
class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazwa_auta = db.Column(db.String(100), nullable=False)
    data_ubezpieczenia = db.Column(db.Date, nullable=False)
    data_przegladu = db.Column(db.Date, nullable=False)
    data_wymiany_oleju = db.Column(db.Date, nullable=False)
    kilometry_wymiany_oleju = db.Column(db.Integer, nullable=False)
    aktualny_przebieg = db.Column(db.Integer, nullable=False)
    owner_id = db.Column(db.Integer)

class Important_task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(200), nullable=False)
    task_date = db.Column(db.Date, nullable=False)
    owner_id = db.Column(db.Integer)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(100), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def UserInputValidate(user: User, url:str):
    if not user.username or not user.username.strip():
            flash('User name cannot be empty od spaces', 'warning')
            return redirect(url_for(url))

    email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not user.email or not re.match(email_pattern, user.email):
        flash('Enter a valid email address', 'warning')
        return redirect(url_for(url))

    users = User.query.all()

    for userValid in users:
        if userValid.username == user.username and userValid.email == user.email:
            flash('This account already exists', 'warning')
            return redirect(url_for(url))            
        elif userValid.username == user.username:
            flash('This nick already exists', 'warning') 
            return redirect(url_for(url))           
        elif userValid.email == user.email:
            flash('This email already exists', 'warning') 
            return redirect(url_for(url))   
    return user

def get_color(date):
    """Funkcja określająca kolor na podstawie daty."""
    today = datetime.today().date()
    if date <= today + timedelta(days=7):
        return 'red'
    elif date <= today + timedelta(days=30):
        return 'orange'
    else:
        return 'green'

def get_mileage_color(kilometry_wymiany_oleju, aktualny_przebieg):
    """Funkcja określająca kolor na podstawie różnicy przebiegu."""
    if aktualny_przebieg >= kilometry_wymiany_oleju:
        return 'red'
    elif kilometry_wymiany_oleju - aktualny_przebieg <= 1000:
        return 'orange'
    else:
        return 'green'

def send_email(subject, message, mail_to):
    """Funkcja do wysyłania e-maili."""
    #sender_email = "your_email@example.com"
    #sender_password = "your_password"
    #recipient_email = "recipient_email@example.com"

    msg = MIMEMultipart()
    msg['From'] = utylity.mail_from #"MACINTEC FLEET MANAGEMENT"
    msg['To'] = mail_to
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))

    try:
        with smtplib.SMTP('s1.ct8.pl', 587) as server:
            server.starttls()
            server.login(utylity.mail_from, utylity.mail_from_pass)
            server.send_message(msg)
            log_event(f"Wysłano e-mail: {subject} na adres {mail_to}")
    except Exception as e:
        log_event(f"Błąd podczas wysyłania e-maila: {e}")

def check_conditions_and_send_email(user_id: int=None):
    """Funkcja sprawdzająca warunki i wysyłająca odpowiednie maile."""
    if user_id is None:
        users = User.query.all()
    else:
        users = User.query.filter_by(id=user_id).all()

    today = datetime.today().date()
    
    for user in users:
        if user.id != 999:
            if user.id==1000: task_owner_id=2
            else: task_owner_id=user.id

            cars = Car.query.filter_by(owner_id = task_owner_id).all()
    
            mailBody = ""

            for car in cars:
                # Sprawdzanie dat
                for attr, desc in [(car.data_ubezpieczenia, "ubezpieczenia"), 
                                   (car.data_przegladu, "przeglądu"), 
                                   (car.data_wymiany_oleju, "wymiany oleju")]:
                    if attr <= today + timedelta(days=7):
                        if attr < today:
                            mailBody += f"UWAGA, w {car.nazwa_auta} upłynął czas {desc}: {attr} \n\n\n"
                            #send_email(f"UWAGA, upłynął czas {desc}", f"UWAGA, upłynął czas {desc}: {attr}")
                        else:
                            mailBody += f"Do 7 dni, w {car.nazwa_auta} upływa czas {desc}: {attr} \n\n\n"
                            #send_email(f"Do 7 dni upływa czas {desc}", f"Do 7 dni upływa czas {desc}: {attr}")
                    elif attr <= today + timedelta(days=30):
                        mailBody += f"W {car.nazwa_auta} zbliża się termin {desc}: {attr} \n\n\n"
                        #send_email(f"Zbliża się termin {desc}", f"Zbliża się termin {desc}: {attr}")

                # Sprawdzanie przebiegu
                if car.kilometry_wymiany_oleju - car.aktualny_przebieg <= 1000:
                    if car.aktualny_przebieg >= car.kilometry_wymiany_oleju:
                        mailBody += f"UWAGA, w {car.nazwa_auta} upłynął czas wymiany oleju przy przebiegu: {car.kilometry_wymiany_oleju} \n\n\n"
                        #send_email("UWAGA, upłynął czas wymiany oleju", f"UWAGA, upłynął czas wymiany oleju przy przebiegu: {car.kilometry_wymiany_oleju}")
                    else:
                        mailBody += f"W {car.nazwa_auta} zbliża się czas wymiany oleju przy przebiegu: {car.kilometry_wymiany_oleju} \n\n\n"
                        #send_email("Zbliża się czas wymiany oleju", f"Zbliża się czas wymiany oleju przy przebiegu: {car.kilometry_wymiany_oleju}")

            if not mailBody:
                mailBody += f"Na dziś: {today}, z samochodami wszystko w porządku."

            send_email(f"Powiadomienie o stanie floty z dnia {today}", mailBody, user.email)
    

def check_task_conditions_and_send_email(user_id: int=None):
    if user_id is None:
        users = User.query.all()
    else:
        users = User.query.filter_by(id=user_id).all()

    today = datetime.today().date()
    
    for user in users:
        if user.id != 999:
            task_owner_id=user.id 
            
            tasks = Important_task.query.filter_by(owner_id = task_owner_id).all()   
        
            mailBody = ""

            for task in tasks:
                if task.task_date <= today + timedelta(days=7):
                    if task.task_date <= today:
                        mailBody += f"!!!UWAGA czas sprawy: {task.task_name} skończył się w dniu: {task.task_date}!!! \n\n\n"
                    else:
                        mailBody += f"Czas sprawy: {task.task_name} skończy się do 7 dni, w dniu: {task.task_date}!!! \n\n\n"
                elif task.task_date <= today + timedelta(days=30):
                    mailBody += f"Czas sprawy: {task.task_name} skończy się do miesiąca, w dniu: {task.task_date}!!! \n\n\n"
            
            if not mailBody:
                mailBody += f"Na dziś: {today}, nie masz żadnych ważnych spraw."
            
            send_email(f"POWIADOMIENIE O TERMINACH WAŻNYCH SPRAW Z DNIA {today}", mailBody, user.email)
    


@app.route('/')
def index():
    user_id = current_user.id if current_user.is_authenticated else 999
    cars = Car.query.filter_by(owner_id = user_id).all()

    return render_template('index.html', cars=cars, get_color=get_color, get_mileage_color=get_mileage_color, current_user = current_user)

@app.route('/tasks')
def tasks():
    user_id = current_user.id if current_user.is_authenticated else 999
    important_tasks = Important_task.query.filter_by(owner_id = user_id).all()
    
    return render_template('tasks.html', important_tasks = important_tasks, get_color = get_color, current_user = current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            log_event(f"Zalogowal sie uzytkownik: {current_user.username}.")
            return redirect(url_for('manage'))
        else:
            flash('Nieprawidłowa nazwa użytkownika lub hasło.', 'warning')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_event(f"Wylogowal sie uzytkownik: {current_user.username}.")
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']        
        email = request.form['email']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        if User.query.filter_by(username=username).first():
            flash('Użytkownik o takiej nazwie już istnieje.', 'warning')
            return redirect(url_for('register'))

        new_user = User(username=username, password=hashed_password, email=email)
        UserInputValidate(new_user, 'register')
        db.session.add(new_user)
        db.session.commit()
        flash('Konto zostało utworzone. Możesz się teraz zalogować.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', current_user = current_user)

@app.route('/manage')
@login_required
def manage():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    user_id = current_user.id
    if user_id == 2 :
        cars = Car.query.all()
    else:
        cars = Car.query.filter_by(owner_id = user_id).all()
    return render_template('manage.html', cars=cars, current_user = current_user)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    if request.method == 'POST':
        nazwa_auta = request.form['nazwa_auta']
        data_ubezpieczenia = request.form['data_ubezpieczenia']
        data_przegladu = request.form['data_przegladu']
        data_wymiany_oleju = request.form['data_wymiany_oleju']
        kilometry_wymiany_oleju = request.form['kilometry_wymiany_oleju']
        aktualny_przebieg = request.form['aktualny_przebieg']

        new_car = Car(
            nazwa_auta=nazwa_auta,
            data_ubezpieczenia=datetime.strptime(data_ubezpieczenia, '%Y-%m-%d').date(),
            data_przegladu=datetime.strptime(data_przegladu, '%Y-%m-%d').date(),
            data_wymiany_oleju=datetime.strptime(data_wymiany_oleju, '%Y-%m-%d').date(),
            kilometry_wymiany_oleju=int(kilometry_wymiany_oleju),
            aktualny_przebieg=int(aktualny_przebieg),
            owner_id = current_user.id
        )

        db.session.add(new_car)
        db.session.commit()
        flash(f"Car {new_car.nazwa_auta} został pomyślnie dodany do bazy.", 'success')
        return redirect(url_for('manage'))

    return render_template('add.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    car = Car.query.get_or_404(id)

    if request.method == 'POST':
        car.nazwa_auta = request.form['nazwa_auta']
        car.data_ubezpieczenia = datetime.strptime(request.form['data_ubezpieczenia'], '%Y-%m-%d').date()
        car.data_przegladu = datetime.strptime(request.form['data_przegladu'], '%Y-%m-%d').date()
        car.data_wymiany_oleju = datetime.strptime(request.form['data_wymiany_oleju'], '%Y-%m-%d').date()
        car.kilometry_wymiany_oleju = int(request.form['kilometry_wymiany_oleju'])
        car.aktualny_przebieg = int(request.form['aktualny_przebieg'])

        db.session.commit()
        return redirect(url_for('manage'))

    return render_template('edit.html', car=car, current_user = current_user)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    car = Car.query.get_or_404(id)
    db.session.delete(car)
    db.session.commit()
    flash(f"Car {car.nazwa_auta} został pomyślnie usunięty.", 'success')
    return redirect(url_for('manage'))

@app.route('/manage_tasks')
@login_required
def manage_tasks():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    user_id = current_user.id
    if user_id == 2 :
        important_tasks = Important_task.query.all()
    else:
        important_tasks = Important_task.query.filter_by(owner_id = user_id).all()
    return render_template('manage_tasks.html', important_tasks = important_tasks, current_user = current_user)

@app.route('/add_task', methods=['GET', 'POST'])
@login_required
def add_task():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    if request.method == 'POST':
        task_name = request.form['task_name']
        task_date = request.form['task_date']

        new_task = Important_task(
            task_name=task_name,
            task_date=datetime.strptime(task_date, '%Y-%m-%d').date(),
            owner_id = current_user.id
        )

        db.session.add(new_task)
        db.session.commit()
        flash(f"Sprawa: {new_task.task_name} została pomyślnie dodana do bazy.", 'success')
        return redirect(url_for('manage_tasks'))

    return render_template('add_task.html')

@app.route('/edit_task/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_task(id):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    important_task = Important_task.query.get_or_404(id)

    if request.method == 'POST':
        important_task.task_name = request.form['task_name']
        important_task.task_date = datetime.strptime(request.form['task_date'], '%Y-%m-%d').date()

        db.session.commit()
        return redirect(url_for('manage_tasks'))

    return render_template('edit_task.html', important_task=important_task, current_user = current_user)

@app.route('/delete_task/<int:id>', methods=['POST'])
@login_required
def delete_task(id):
    important_task = Important_task.query.get_or_404(id)
    db.session.delete(important_task)
    db.session.commit()
    flash(f"Sprawa {important_task.task_name} została pomyślnie usunięta.", 'success')
    return redirect(url_for('manage_tasks'))

@app.route('/manage_user')
@login_required
def manage_user():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    user_id = current_user.id
    if user_id == 2 :
        users_list = User.query.all()
    else:
        users_list = User.query.filter_by(id = user_id).all()
    return render_template('manage_user.html', users_list = users_list)

@app.route('/edit_user/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    user_to_edit = User.query.get_or_404(id)
    users = User.query.all()
    if request.method == 'POST':
        user_to_edit.username = request.form['username']
        user_to_edit.email = request.form['email']
        for user in users:
            if user_to_edit.username == user.username and user_to_edit.id != user.id:
                flash('Podany Użytkownik już istnieje - zmień nazwę użytkownika na inną!', 'warning')
                return render_template('edit_user.html',user_to_edit = user_to_edit)
            if user_to_edit.email == user.email and user_to_edit.id != user.id:
                flash('Podany email jż istnieje - zmień email na inny!', 'warning')
                return render_template('edit_user.html',user_to_edit = user_to_edit)
        db.session.commit()
        flash(f'Dane użytkwonika {user_to_edit.username} zostały zmienione.', 'warning')
        return redirect(url_for('manage_user'))

    return render_template('edit_user.html',user_to_edit = user_to_edit)

@app.route('/delete_user/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    user_to_del = User.query.get_or_404(id)
    try:
        db.session.delete(user_to_del)
        db.session.commit()
        flash(f"Użytkownik {user_to_del.username} został pomyślnie usunięty.",'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Wystąpił problem z usunięciem użytkownika {user_to_del.username}",'danger')    
    return redirect(url_for('manage_user'))

@app.route('/update_password/<int:id>', methods=['GET', 'POST'])
@login_required
def update_password(id):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    if request.method == 'POST':
        old_password = request.form['old_pasword']
        password_1 = request.form['pasword_1']
        password_2 = request.form['pasword_2']
        user_id = current_user.id
        if user_id == 2:
            user_to_edit = User.query.get_or_404(id)
        else:
            user_to_edit = User.query.get_or_404(user_id)
        if user_to_edit and not check_password_hash(user_to_edit.password, old_password):
            flash('Podane hasło do zmiany nie jest zgodne z istniejącym', 'warning')
            return render_template('update_password.html', id = user_to_edit.id)
        if password_1 != password_2:
            flash('Wpisane hasła nie są identyczne', 'warning')
            return render_template('update_password.html', id = user_to_edit.id)
        user_to_edit.password = generate_password_hash(password_2, method='pbkdf2:sha256')
        db.session.commit()
        
        flash('Twoje hasło zostało zmienione.', 'success')
        return redirect(url_for('manage_user'))
    return render_template('update_password.html', id = id)

@app.route('/send_notification')
@login_required
def send_notification():
    job_1()
    flash(f"Mail został wysłany.", 'success')
    return redirect(url_for('manage'))

@app.route('/send_task_notification')
@login_required
def send_task_notification():
    job_2()
    flash(f"Mail został wysłany.", 'success')
    return redirect(url_for('manage_tasks'))

@app.route('/send_all_notifics')
@login_required
def send_all_notifics():
    check_conditions_and_send_email()
    check_task_conditions_and_send_email()
    flash("Maile zostały wysłane",'success')
    return redirect(url_for('index'))

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def job_1():
    user_id = current_user.id if current_user else None
    with app.app_context():
        check_conditions_and_send_email(user_id)

def job_2():
    user_id = current_user.id if current_user else None
    with app.app_context():
        check_task_conditions_and_send_email(user_id)

# Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(job_1, trigger="cron", hour=8, minute=17)
scheduler.add_job(job_2, trigger="cron", hour=8, minute=18)
scheduler.start()    

# Rejestrowanie funkcji jako filtry Jinja
app.jinja_env.filters['get_color'] = get_color
app.jinja_env.filters['get_mileage_color'] = get_mileage_color

# Tworzenie bazy danych (tylko przy pierwszym uruchomieniu)
#with app.app_context():
#    db.create_all()

# Przykładowe dane (odkomentuj przy pierwszym uruchomieniu)
#    user1 = User(username="admin", password=generate_password_hash("admin", method='pbkdf2:sha256'))
#    db.session.add(user1)
#    db.session.commit()
#     car1 = Car(nazwa_auta="Toyota Corolla", data_ubezpieczenia="2025-02-20", 
#                data_przegladu="2025-03-10", data_wymiany_oleju="2025-01-30", 
#                kilometry_wymiany_oleju=15000, aktualny_przebieg=14000)
#     db.session.add(car1)
#     db.session.commit()

if __name__ == '__main__':
    restart = False
    app.run(debug=True)