from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask import session, flash
from flask_login import LoginManager, UserMixin
from werkzeug.utils import secure_filename
from db_functions import update_user_info, delete_appointment
from lecturer_calendar import calendar_record, calendar_repeat
import sqlite3
import bcrypt
import random
import os
import json
from datetime import datetime, timedelta


app = Flask(__name__, static_folder="static")
login_manager = LoginManager()
login_manager.init_app(app)
app.secret_key = "jelwin"
UPLOAD_FOLDER = os.path.join(
    app.static_folder, "faculty_pp"
) 
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


def get_db_connection():
    con = sqlite3.connect("database.db")
    con.row_factory = sqlite3.Row
    return con


@login_manager.user_loader
def load_user(id):
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (id,))
    user = cur.fetchone()
    con.close()
    if user:
        return User(user['id'], user['username'])

    return None


def load_pin():
    with open("pin.json", "r") as file:
        return json.load(file)["pin"]


def save_pin(new_pin):
    with open("pin.json", "w") as file:
        json.dump({"pin": new_pin}, file)

def load_content():
    with open("content.json") as f:
        return json.load(f)


def save_content(content):
    with open("content.json", "w") as f:
        json.dump(content, f)


content_data = load_content()
home_content = content_data["home_content"]


@app.route("/")
def home():
    with open("content.json", "r") as file:
        content = json.load(file)

    return render_template(
        "home.html",
        home_content=content["home_content"],
        school_name=content["school_name"],
        school_tel=content["school_tel"],
        school_email=content["school_email"],
        school_logo=content["school_logo"],  
    )


@app.route("/about")
def about():
    return render_template("about.html")


def hash_password(password):
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed_password.decode("utf-8")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        role = request.form.get("role")
        faculty = request.form.get("faculty")
        username = request.form.get("username")
        email = request.form.get("email")
        phone_number = request.form.get("phone_number")
        password = request.form.get("password")
        pin = request.form.get("pin")

        if role == "teacher":
            if not email.endswith("@mmu.edu.my"):
                flash("SIGN UP FAILED. Lecturers must use an @mmu.edu.my email.", "error")
                return redirect("/signup")

            stored_pin = load_pin()
            if pin != stored_pin:
                flash("PIN is incorrect", "error")
                return redirect("/signup")

        elif role == "student":
            if not email.endswith("@student.mmu.edu.my"):
                flash("SIGN UP FAILED. Students must use an @student.mmu.edu.my email.", "error")
                return redirect("/signup")

        if not password:
            flash("Password is required", "error")
            return redirect("/signup")

        hashed_password = hash_password(password)

        con = get_db_connection()
        cur = con.cursor()

        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user_email = cur.fetchone()

        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user_username = cur.fetchone()

        cur.execute("SELECT * FROM users WHERE phone_number = ?", (phone_number,))
        user_phone = cur.fetchone()

        if user_email:
            con.close()
            flash("User with this email already exists", "error")
            return redirect("/signup")
        elif user_username:
            con.close()
            flash("User with this username already exists", "error")
            return redirect("/signup")
        elif user_phone:
            con.close()
            flash("User with this phone number already exists", "error")
            return redirect("/signup")
        else:
            cur.execute(
                "INSERT INTO users (role, faculty, username, email, phone_number, password) VALUES (?, ?, ?, ?, ?, ?)",
                (role, faculty, username, email, phone_number, hashed_password),
            )
            con.commit()
            con.close()
            return redirect("/login")
    else:
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("SELECT faculty_name FROM facultyhub")
        faculties = cur.fetchall()
        con.close()
        return render_template("signup.html", faculties=faculties)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Load admin credentials from admin.json
        with open("admin.json", "r") as admin_file:
            admin_data = json.load(admin_file)

        if email == admin_data["email"] and password == admin_data["password"]:
            session["logged_in"] = True
            return redirect("/admin")
        else:
            con = get_db_connection()
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cur.fetchone()

            if user and bcrypt.checkpw(
                password.encode("utf-8"), user["password"].encode("utf-8")
            ):
                session["logged_in"] = True
                session["id"] = user[0]

                return redirect("/")
            else:
                return render_template(
                    "login.html", message="Invalid email or password"
                )
    else:
        return render_template("login.html")


# student and lecturer
@app.route("/update_user_info", methods=["POST"])
def update_user():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        phone_number = request.form.get("phone_number")
        update_user_info(session["id"], username, email, phone_number)

        return redirect("/profile")

# student and lecturer
@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            return render_template(
                "profile.html", message="New password and confirm password do not match"
            )

        con = get_db_connection()
        cur = con.cursor()
        cur.execute("SELECT password FROM users WHERE id = ?", (session["id"],))
        user_data = cur.fetchone()

        if not user_data or not bcrypt.checkpw(
            current_password.encode("utf-8"), user_data["password"].encode("utf-8")
        ):
            return render_template("profile.html", message="Incorrect current password")


        hashed_new_password = hash_password(new_password)
        cur.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_new_password, session["id"]),
        )
        con.commit()
        con.close()

        return redirect("/profile")
    else:
        return render_template("profile.html")


# student
@app.route("/create_booking", methods=["POST"])
def create_booking():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session["id"],))
    user_data = cursor.fetchone()
    conn.close()

    session["username"] = user_data["username"]

    if request.method == "POST":
        booking_id = random.randint(100000, 999999)
        student = session["username"]
        lecturer = request.form.get("lecturer")
        purpose = request.form.get("purpose")
        appointment_date = request.form.get("appointment_date")
        appointment_time = request.form.get("selected_time_slot")
        

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO appointments (booking_id, student, lecturer, purpose, appointment_date, appointment_time, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (booking_id, student, lecturer, purpose, appointment_date, appointment_time, "Pending"),
            )
            appointment_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        session["appointment_id"] = appointment_id

        start_time = datetime.strptime(appointment_time, "%I:%M %p")
        end_time = (start_time + timedelta(hours=1)).strftime("%H:%M")
        start_time = start_time.strftime("%H:%M")

        event_title = f"Appointment with {user_data['username']} (Booking ID: {booking_id})"
        insert_event_into_db(
            event_title=event_title,
            event_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            repeat_type="", 
            lecturer=lecturer
        )

        flash("Booking created successfully!", "success")
        return redirect("/invoice")


# student
@app.route("/invoice")
def render_template_invoice():
    user_id = session.get("id")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()

    session["username"] = user_data["username"]
    session["role"] = user_data["role"]
    session["faculty"] = user_data["faculty"]
    session["email"] = user_data["email"]
    session["phone_number"] = user_data["phone_number"]

    appointment_id = session.get("appointment_id")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
    appointment = cursor.fetchone()
    conn.close()

    return render_template(
        "invoice.html",
        username=session.get("username"),
        email=user_data["email"],
        faculty=user_data["faculty"],
        phone_number=user_data["phone_number"],
        role=user_data["role"],
        appointment=appointment,
        booking_id=appointment["booking_id"]
    )


# student and lecturer
@app.route("/bookinghistory")
def user_booking_history():
    username = session.get("username")
    role = session.get("role")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        if role == "student":
            cursor.execute("SELECT * FROM appointments WHERE student = ?", (username,))
            display_role = "lecturer"
            role = 'student'
        else:
            cursor.execute("SELECT * FROM appointments WHERE lecturer = ?", (username,))
            display_role = "student"
            role = 'teacher'

        appointments = cursor.fetchall()
    finally:
        conn.close()

    return render_template("booking_history.html", appointments=appointments, display_role=display_role, role=role)


# lecturer
@app.route("/cancel_booking", methods=["POST"])
def cancel_booking():

    booking_id = request.form.get("id")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE appointments SET status = ? WHERE id = ?", ("cancel", booking_id))
        conn.commit()
    finally:
        conn.close()

    return redirect("/bookinghistory")

@app.route("/reject_booking", methods=["POST"])
def reject_booking():

    booking_id = request.form.get("id")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE appointments SET status = ? WHERE id = ?", ("reject", booking_id))
        conn.commit()
    finally:
        conn.close()

    return redirect("/bookinghistory")

# lecturer
@app.route("/accept_booking", methods=["POST"])
def accept_booking():
    booking_id = request.form.get("id")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE appointments SET status = ? WHERE id = ?", ("accept", booking_id))
        conn.commit()
    finally:
        conn.close()

    return redirect("/bookinghistory")


# lecturer
@app.route("/calendar", methods=["GET", "POST"])
def create_calendar():
    if request.method == "POST":
        lecturer = request.form["lecturer"]
        event_title = request.form["event_title"]
        event_date = request.form["event_date"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        
        calendar_record(lecturer, event_title, event_date, start_time, end_time)
        
        return redirect(url_for("calendar"))
    
    return render_template("calendar.html")


@app.route("/calendar", methods=["GET", "POST"])
def repeat_calendar():
    if request.method == "POST":
        event_title = request.form["event_title"]
        repeat_type = request.form["repeat_type"]
        repeat_interval = int(request.form["repeat_interval"])
        repeat_count = int(request.form["repeat_count"])
        
        if repeat_type not in ["No repeat", "Daily", "Weekly", "Monthly"]:
            return render_template("calendar.html", message="Invalid repeat type. Must be No Repeat, Daily, Weekly, or Monthly.")
        
        if repeat_count < 1:
            return render_template("calendar.html", message="Repeat count must be at least 1.")
        
        result = calendar_repeat(event_title, repeat_type, repeat_interval, repeat_count)
        
        if result is None:
            return render_template("calendar.html", message="Event not found or invalid date format.")
        
        return redirect(url_for("calendar"))


@app.route("/calendar")
def calendar():
    con = get_db_connection()
    cur = con.cursor()
    
    cur.execute("SELECT * FROM calendar")
    events = cur.fetchall()
    con.close()
    
    return render_template("calendar.html", events=events)


@app.route("/appointment")
def appointment():
    return render_template("appointment.html")


@app.route("/appointment2")
def appointment2():
    return render_template("appointment2.html")


@app.route("/check_availability", methods=["POST"])
def check_availability():
    # Get form data
    lecturer = request.form["lecturer"]
    event_date = request.form["appointment_date"]
    selected_time_slot = request.form["selected_time_slot"]

    # Combine date and time slot to create event datetime
    event_datetime = f"{event_date} {selected_time_slot}"

    # Query the database to check for existing appointments within the time range
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM calendar WHERE lecturer = ? AND event_date = ?", (lecturer, event_date))
    existing_appointments = cursor.fetchall()
    conn.close()

    # Check availability
    if existing_appointments:
        availability = "unavailable"
    else:
        availability = "available"

    # Return availability status
    return jsonify({"availability": availability})


# admin
@app.route("/appointmentcontrol", methods=["GET", "POST"])
def appointmentcontrol():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, lecturer, student, appointment_date, purpose, status, appointment_time FROM appointments"
    )
    appointments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("appointment_control.html", appointments=appointments)


# admin
def delete_appointment(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments WHERE id=?", (id,))
    conn.commit()
    conn.close()

# admin
@app.route("/delete_booking", methods=["POST"])
def delete_booking():
    id = request.form["id"]
    delete_appointment(id)
    return redirect("/appointmentcontrol")

# admin
@app.route("/admin")
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'teacher'")
    num_teachers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
    num_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM appointments")
    num_appointments = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    num_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT lecturer, student, appointment_date, purpose, status, appointment_time FROM appointments"
    )
    appointments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin.html",
        appointments=appointments,
        num_teachers=num_teachers,
        num_students=num_students,
        num_appointments=num_appointments,
        num_users=num_users,
    )


# admin
@app.route("/usercontrol")
def usercontrol():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    user_data = cursor.fetchall()
    conn.close()

    return render_template("usercontrol.html", users=user_data)


# admin
def delete_user(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()


@app.route("/adminpageeditor", methods=["GET", "POST"])
def admin_page_editor():
    content = load_content()

    if request.method == "POST":
        home_content = request.form.get("home_content")
        school_name = request.form.get("school_name")
        school_tel = request.form.get("school_tel")
        school_email = request.form.get("school_email")
        new_pin = request.form.get("new_pin")
        retype_new_pin = request.form.get("retype_new_pin")

        filename = ""
        if "school_logo" in request.files:
            file = request.files["school_logo"]
            if file.filename != "":
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        content.update(
            {
                "home_content": home_content,
                "school_name": school_name,
                "school_tel": school_tel,
                "school_email": school_email,
                "school_logo": filename,
            }
        )

        save_content(content)

        if new_pin and retype_new_pin:
            if new_pin == retype_new_pin:
                save_pin(new_pin)
            else:
                return render_template(
                    "adminpageeditor.html",
                    **content,
                    pin=load_pin(),
                    message="PINs do not match",
                )

        return redirect(url_for("admin_page_editor"))

    return render_template("adminpageeditor.html", **content, pin=load_pin())


@app.route("/getpin", methods=["GET"])
def get_pin():
    return jsonify({"pin": load_pin()})


@app.route("/update_home_content", methods=["POST"])
def update_home_content():
    content = load_content()
    home_content = request.form["home_content"]
    content["home_content"] = home_content
    save_content(content)
    return redirect("/adminpageeditor")


@app.route("/change_teacher_pin", methods=["POST"])
def change_teacher_pin():
    teacher_pin = request.form.get("teacher_pin")

    # Update pin.json
    with open("pin.json", "w") as pin_file:
        pin_data = {"pin": teacher_pin}
        json.dump(pin_data, pin_file)

    return redirect("/adminpageeditor")


@app.route("/change_admin_credentials", methods=["POST"])
def change_admin_credentials():
    admin_email = request.form.get("admin_email")
    admin_password = request.form.get("admin_password")

    with open("admin.json", "w") as admin_file:
        admin_data = {"email": admin_email, "password": admin_password}
        json.dump(admin_data, admin_file)

    return redirect("/adminpageeditor")


@app.route("/delete_user", methods=["POST"])
def delete_user_route():
    id = request.form["id"]
    delete_user(id)
    return redirect("/usercontrol")


@app.route("/changepassword")
def changepassword():
    return render_template("changepassword.html")


@app.route("/history")
def history():
    return render_template("schedule.html")


@app.route("/faculty")
def faculty():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT faculty_name, faculty_image FROM facultyhub")
    faculty_info = cursor.fetchall()

    faculty_data = []
    for faculty in faculty_info:
        cursor.execute(
            "SELECT username, email FROM users WHERE faculty = ? AND role = 'teacher'",
            (faculty["faculty_name"],),
        )
        lecturers = cursor.fetchall()

        cursor.execute(
            "SELECT username, email FROM users WHERE faculty = ? AND role = 'student'",
            (faculty["faculty_name"],),
        )
        students = cursor.fetchall()

        faculty_data.append(
            {
                "faculty_name": faculty["faculty_name"],
                "faculty_image": faculty["faculty_image"],
                "lecturers": [
                    {"username": lecturer[0], "email": lecturer[1]}
                    for lecturer in lecturers
                ],
                "students": [
                    {"username": student[0], "email": student[1]}
                    for student in students
                ],
            }
        )

    conn.close()

    return render_template("faculty.html", faculty_info=faculty_data)


# admin
@app.route("/facultyhub/<int:hub_id>", methods=["GET"])
def faculty_hub_page(hub_id=None):
    try:
        if hub_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, image_path FROM facultyhub WHERE id = ?", (hub_id,)
            )
            faculty_hub = cursor.fetchone()
            conn.close()

            if faculty_hub:
                return render_template("facultyhub.html", faculty_hub=faculty_hub)
            else:
                return render_template("error.html", message="Faculty Hub Not Found")
        else:
            return render_template(
                "error.html", message="Please provide a valid Faculty Hub ID"
            )
    except Exception as e:
        print("Error in faculty_hub_page:", e)
        return render_template(
            "error.html", message="An error occurred while processing your request"
        )


@app.route("/createfacultyhub", methods=["GET", "POST"])
def create_faculty_hub():
    if request.method == "POST":
        faculty_name = request.form.get("faculty_name")
        faculty_image = request.files.get("faculty_image")

        if not faculty_name or not faculty_image:
            return render_template(
                "createfacultyhub.html", message="Missing required fields"
            )

        try:
            filename = secure_filename(faculty_image.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

 
            faculty_image.save(image_path)

            print(f"Saved file to {image_path}")

            relative_image_path = filename

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO facultyhub (faculty_name, faculty_image) VALUES (?, ?)",
                (faculty_name, relative_image_path),
            )
            conn.commit()
            conn.close()

            return redirect(url_for("create_faculty_hub"))
        except Exception as e:
            print("Error occurred:", e)
            return render_template(
                "createfacultyhub.html",
                message="An error occurred while creating faculty hub",
            )
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM facultyhub")
        faculty_hubs = cursor.fetchall()
        conn.close()
        return render_template("createfacultyhub.html", faculty_hubs=faculty_hubs)


# admin
@app.route("/profile")
def profile():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session["id"],))
    user_data = cursor.fetchone()
    conn.close()

    session["username"] = user_data[3]
    session["role"] = user_data[1]
    session["faculty"] = user_data[2]
    session["email"] = user_data[4]
    session["phone_number"] = user_data[5]

    return render_template(
        "profile.html",
        username=user_data["username"],
        email=user_data["email"],
        faculty=user_data["faculty"],
        phone_number=user_data["phone_number"],
        role=user_data["role"],
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True, port=6969)