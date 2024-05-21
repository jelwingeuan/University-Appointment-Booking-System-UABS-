from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask import session, flash
from flask_login import LoginManager, UserMixin, login_required, current_user
from db_functions import (
    update_user_info,
    create_appointment,
    get_appointments,
    update_appointment,
    delete_appointment,
)
import sqlite3
import bcrypt
import random
import os
import json

app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
app.secret_key = "jelwin"
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


# Function to get database connection
def get_db_connection():
    con = sqlite3.connect("database.db")
    con.row_factory = sqlite3.Row
    return con


@login_manager.user_loader
def load_user(id):
    # Load and return a user from the database based on user_id
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (id,))
    user = cur.fetchone()
    con.close()
    if user:
        return User(user['id'], user['username'])
    
    return None



def load_content():
    with open("content.json", "r") as f:
        content = f.read().strip()
            

    return json.loads(content)


# Save content to JSON file
def save_content(content):
    with open("content.json", "w") as f:
        json.dump(content,f)


content_data = load_content()
home_content = content_data["home_content"]


@app.route("/")
def home():
    return render_template("home.html", home_content=home_content)


@app.route("/about")
def about():
    return render_template("about.html")


# Function for hashed password
def hash_password(password):
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed_password.decode("utf-8")


# Route for "sign up"
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        role = request.form.get("role")
        faculty = request.form.get("faculty")
        username = request.form.get("username")
        email = request.form.get("email")
        phone_number = request.form.get("phone_number")
        password = request.form.get("password")

        if not password:  # Check if password is provided
            return render_template("signup.html", message="Password is required")

        hashed_password = hash_password(password)

        con = get_db_connection()
        cur = con.cursor()

            # Check if email already exists
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()

        if user:
            con.close()
            return render_template(
                "signup.html", message="User with this email already exists"
            )
        else:
            cur.execute(
                "INSERT INTO users (role, faculty, username, email, phone_number, password) VALUES (?, ?, ?, ?, ?, ?)",
                (role, faculty, username, email, phone_number, hashed_password),
            )
            con.commit()
            con.close()
            return redirect("/login")
    else:
        return render_template("signup.html")



# Route for "log in"
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if email == "admin@example.com" and password == "123":
            session["logged_in"] = True
            return redirect("/admin")
        else:
            # If not admin, proceed with regular user login logic
            con = get_db_connection()
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cur.fetchone()

            if user and bcrypt.checkpw(
                password.encode("utf-8"), user["password"].encode("utf-8")
            ):
                # Redirect to the home page upon successful login for regular users
                session["logged_in"] = True
                session["id"] = user[0]
                
                return redirect("/")
            else:
                return render_template(
                    "login.html", message="Invalid email or password"
                )
    else:
        return render_template("login.html")


# Route for updating user information
@app.route("/update_user_info", methods=["POST"])
def update_user():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        phone_number = request.form.get("phone_number")
        update_user_info(session["id"], username, email, phone_number)

        return redirect("/profile")


# Route for changing password
@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Verify if new password and confirm password match
        if new_password != confirm_password:
            return render_template(
                "profile.html", message="New password and confirm password do not match"
            )

        # Verify if the current password is correct
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("SELECT password FROM users WHERE id = ?", (session["id"],))
        user_data = cur.fetchone()

        if not user_data or not bcrypt.checkpw(
            current_password.encode("utf-8"), user_data["password"].encode("utf-8")
        ):
            return render_template("profile.html", message="Incorrect current password")

        # Update the password in the database
        hashed_new_password = hash_password(new_password)
        cur.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_new_password, session["id"]),
        )
        con.commit()
        con.close()

        # Redirect the user to a success page or profile page
        return redirect("/profile")
    else:
        # Render the profile page with the password change form
        return render_template("profile.html")


# # Function to create a new appointment
# @app.route("/make_appointment", methods=["POST"])
# def make_appointment():
#     if request.method == "POST":
#         student = request.form.get("student")
#         lecturer = request.form.get("lecturer")
#         appointment_date = request.form.get("appointment_date")
#         appointment_time = request.form.get("appointment_time")
#         purpose = request.form.get("purpose")

#         # Check if all required fields are provided
#         if student and lecturer and appointment_date and appointment_time and purpose:
#             # Create the appointment
#             create_appointment(
#                 student,
#                 lecturer,
#                 appointment_date,
#                 appointment_time,
#                 purpose,
#                 status="Pending",
#             )

#             # Redirect to the appointment page with a success message
#             return render_template(
#                 "appointment.html", message="Appointment created successfully"
#             )
#         else:
#             # If any required field is missing, show an error message
#             return render_template(
#                 "appointment.html", message="Missing required field(s)"
#             )
#     else:
#         # If the request method is not POST, render the appointment page
#         return render_template("appointment.html")


# # Function to list a student's appointment(s)
# @app.route("/appointments", methods=["GET"])
# def list_appointments():
#     student = request.args.get("student")
#     if student:
#         # Retrieve appointments for the specified student
#         appointments = get_appointments(student)
#         return render_template("appointments.html", appointments=appointments)
#     else:
#         # If no student is specified, show a message
#         return render_template("appointment.html", message="No student specified")


# # Route to update an appointment
# @app.route("/update_appointment", methods=["POST"])
# def update_appointments(appointment_id):
#     if request.method == "POST":
#         # Extract new details from the form
#         new_date = request.form.get("new_date")
#         new_time = request.form.get("new_time")
#         new_purpose = request.form.get("new_purpose")

#         # Update the appointment with the new details
#         update_appointment(appointment_id, new_date, new_time, new_purpose)

#         # Redirect to the list of appointments
#         return redirect(url_for("list_appointments"))


# # Route to delete an appointment
# @app.route("/delete_appointment", methods=["POST"])
# def delete_appointment(appointment_id):
#     if request.method == "POST":
#         # Delete the specified appointment
#         delete_appointment(appointment_id)

#         # Redirect to the list of appointments
#         return redirect(url_for("list_appointments"))


def l_profile():
    return redirect(url_for("l_profile"))


def l_appointment():
    return redirect(url_for("l_appointment"))

def l_approval():
    return redirect(url_for("l_approval"))

 
@app.route("/appointment")
def appointment():
    return render_template("appointment.html")


@app.route("/appointment2")
def appointment2():
    return render_template("appointment2.html")


@app.route("/admin")
def admin_dashboard():
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Execute SQL queries to get the counts based on role
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

    # Close the cursor and connection
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


@app.route("/usercontrol")
def usercontrol():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    user_data = cursor.fetchall()
    conn.close()

    return render_template("usercontrol.html", users=user_data)


def delete_user(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()


@app.route('/adminpageeditor', methods=['GET', 'POST'])
def admin_page_editor():
    if request.method == 'POST':
        
        # Get form data
        home_content = request.form.get('home_content')
        school_name = request.form.get('school_name')
        school_tel = request.form.get('school_tel')
        school_email = request.form.get('school_email')

            # Update content with new data
        content['home_content'] = home_content
        content['school_name'] = school_name
        content['school_tel'] = school_tel
        content['school_email'] = school_email

            # Save updated content to JSON file
        save_content(content)

        return redirect('/adminpageeditor')
    
    # For GET request, load content to display in the form
    content = load_content()
    return render_template('adminpageeditor.html', **content)



@app.route("/update_home_content", methods=["POST"])
def update_home_content():
    global home_content
    home_content = request.form["home_content"]
    content_data["home_content"] = home_content
    save_content(content_data)
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
    # Retrieve faculty information from the database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT faculty_name, faculty_image FROM facultyhub")
    faculty_info = cursor.fetchall()
    conn.close()

    # Render the faculty.html template with the faculty_info variable
    return render_template("faculty.html", faculty_info=faculty_info)


@app.route("/facultyhub/<int:hub_id>", methods=["GET"])
def faculty_hub_page(hub_id=None):
    try:
        if hub_id:
            # Retrieve faculty hub information from the database based on hub_id
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, image_path FROM facultyhub WHERE id = ?", (hub_id,)
            )
            faculty_hub = cursor.fetchone()
            conn.close()

            if faculty_hub:
                # Render the faculty hub page with the relevant information
                return render_template("facultyhub.html", faculty_hub=faculty_hub)
            else:
                # If faculty hub not found, render an error page or redirect to another page
                return render_template("error.html", message="Faculty Hub Not Found")
        else:
            # Handle the case when hub_id is not provided
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
            # Save image to server
            if not os.path.exists(app.config["UPLOAD_FOLDER"]):
                os.makedirs(app.config["UPLOAD_FOLDER"])

            image_path = os.path.join(
                app.config["UPLOAD_FOLDER"], faculty_image.filename
            )
            print("Image Path:", image_path)  # Debugging print statement

            faculty_image.save(image_path)

            # Insert faculty hub info into database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO facultyhub (faculty_name, faculty_image) VALUES (?, ?)",
                (faculty_name, image_path),
            )
            conn.commit()

            conn.close()
            print("Faculty hub created successfully!")  # Debugging print statement
            return redirect(url_for("create_faculty_hub"))
        except Exception as e:
            print("Error occurred:", e)  # Debugging print statement
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


@app.route("/create_booking", methods=["POST"])
def create_booking():

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session["id"],))
    user_data = cursor.fetchone()
    conn.close()

    # After successful login
    session["username"] = user_data["username"]


    if request.method == "POST":
        booking_id = random.randint(100000, 999999)
        student = session["username"]  # Use dictionary access for session data
        lecturer = request.form.get("lecturer")
        purpose = request.form.get("purpose")
        appointment_date = request.form.get("appointment_date")
        appointment_time = request.form.get("appointment_time")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO appointments (student, lecturer, purpose, appointment_date, appointment_time, status) VALUES (?, ?, ?, ?, ?, ? )",
                (student, lecturer, purpose, appointment_date, appointment_time, "Pending"),
            )
            appointment_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        session["appointment_id"] = appointment_id

        flash("Booking created successfully!", "success")
        return redirect("/invoice")




@app.route("/invoice")
def render_template_invoice():
    # Ensure the session has the current user ID
    user_id = session.get("id")

    # Fetch user data from the database using the session user ID
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()

    # Store necessary user data in the session
    session["username"] = user_data["username"]
    session["role"] = user_data["role"]
    session["faculty"] = user_data["faculty"]
    session["email"] = user_data["email"]
    session["phone_number"] = user_data["phone_number"]

    # Fetch the latest appointment data using the appointment ID stored in the session
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
    )


@app.route("/appointmentcontrol", methods=["GET", "POST"])
def appointmentcontrol():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, lecturer, student, appointment_date, purpose, status, appointment_time FROM appointments"
    )
    appointments = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    conn.close()

    return render_template("appointment_control.html", appointments=appointments)


def delete_appointment(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments WHERE id=?", (id,))
    conn.commit()
    conn.close()


@app.route("/delete_booking", methods=["POST"])
def delete_booking():
    id = request.form["id"]
    delete_appointment(id)
    return redirect("/bookinghistory")


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
        else :
            cursor.execute("SELECT * FROM appointments WHERE lecturer = ?", (username,))
            display_role = "student"
            role = 'lecturer'

        appointments = cursor.fetchall()
    finally:
        conn.close()

    return render_template("booking_history.html", appointments=appointments, display_role=display_role, role=role)





@app.route("/cancel_booking", methods=["POST"])
def cancel_booking():

    # Get the booking ID from the form
    booking_id = request.form.get("id")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE appointments SET status = ? WHERE id = ?", ("cancel", booking_id))
        conn.commit()
    finally:
        conn.close()

    return redirect("/bookinghistory")


@app.route("/accept_booking", methods=["POST"])
def accept_booking():
    # Get the booking ID from the form
    booking_id = request.form.get("id")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Update the status to "accept" for the booking with the provided ID
        cursor.execute("UPDATE appointments SET status = ? WHERE id = ?", ("accept", booking_id))
        conn.commit()
    finally:
        conn.close()

    return redirect("/bookinghistory")




if __name__ == "__main__":
    # Run the application
    app.run(debug=True, port=6969)
