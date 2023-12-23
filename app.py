import os
import json
from flask import Flask, flash, render_template, request, session, redirect
from sqlalchemy import Enum
from sqlalchemy import or_
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_session import Session
from flask_migrate import Migrate
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required
import secrets

app = Flask(__name__)
app.debug = True
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///schedules.db"
app.config["UPLOAD_EXTENSIONS"] = [".jpg", ".png", ".gif", "pdf"]
app.config["SESSION_PERMANENT"] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)
app.secret_key = secrets.token_hex(32)
app.static_folder = "static"  # Set the static folder to 'static'
app.static_url_path = "/static"


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


class Course(db.Model):
    code = db.Column(db.String(20), primary_key=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    credit_hours = db.Column(db.Integer, nullable=False)
    unassigned_credit_hour = db.Column(db.Integer, nullable=False, default=lambda: Course.credit_hours)
    has_lab = db.Column(db.Boolean, default=False)
    section_course = db.Table('section_course',
                              db.Column('section_id', db.Integer, db.ForeignKey('section.id'), primary_key=True),
                              db.Column('course_id', db.Integer, db.ForeignKey('course.code'), primary_key=True)
                              )


class Instructor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    course_assigned = db.Column(db.Integer, db.ForeignKey(Course.code), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.utcnow)

    course = db.relationship('Course', backref='instructor')


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(1), nullable=False)
    courses = db.relationship('Course', secondary='section_course', backref='sections', lazy=True)


class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(20), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    class_type = db.Column(db.String(10))
    availability = db.relationship("Availability", backref="classroom", cascade="all, delete-orphan")


class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'))
    weekday = db.Column(db.Integer)
    period = db.Column(db.Integer)
    is_available = db.Column(db.Boolean, default=True)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Integer, nullable=False)
    start_period = db.Column(db.Integer, nullable=False)
    end_period = db.Column(db.Integer, nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('instructor.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.code'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=False)
    type = db.Column(Enum('lab', 'lecture', name='schedule_type'), nullable=False)

    classroom = db.relationship('Classroom', backref='schedules')
    instructor = db.relationship('Instructor', backref='schedules')
    course = db.relationship('Course', backref='schedules')
    section = db.relationship('Section', backref='schedules')


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/admin_dash", methods=["GET"])
def admin_dash():
    # view all schedules 
    return render_template("admin_dash.html")


@app.route("/assign_class", methods=["GET", "POST"])
def assign_class():
    if request.method == "POST":
        pass
    else:
        # pass sections here
        sections = Section.query.all()
        return render_template("assign_class.html", sections=sections)


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure email was submitted
        email = request.form.get("email")
        password = request.form.get("password")

        # Ensure both email and password were submitted
        if not email or not password:
            error_message = "Both email and password are required."
            return render_template("admin_login.html", error=error_message)

        # Query database for username (You may replace this with actual database queries)

        # Check if the username and password are correct
        if email == "admin@aau.edu.et" and password == "pass":
            # Remember which user has logged in
            session["admin_email"] = email
            # Redirect user to the admin dashboard
            return render_template("schedule.html")
        else:
            error_message = "Invalid email or password. Please try again."
            return render_template("admin_login.html", error=error_message)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("admin_login.html")


@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure email was submitted
        if not request.form.get("email"):
            error_message = "Please enter your email."
            return render_template("student_login.html", error=error_message)

        # Ensure password was submitted
        # elif not request.form.get("password_hash"):
        #     error_message = "Please enter your password."
        #     return render_template("student_login.html", error=error_message)

        # Query database for username
        user = Student.query.filter_by(email=request.form.get("email")).first()

        # Ensure username exists and password is correct
        # if not user or not check_password_hash(user.password_hash, request.form.get("password")):
        #     error_message = "Invalid email or password. Please try again."
        #     return render_template("student_login.html", error=error_message)

        # Remember which user has logged in
        # session["user_id"] = user.id

        # Redirect user to home page
        return render_template("student_home.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("student_login.html")


@app.route("/instructor_login", methods=["GET", "POST"])
def instructor_login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure email and password were submitted
        email = request.form.get("email")
        password = request.form.get("password")

        if not email:
            error_message = "Please enter your email."
            return render_template("instructor_login.html", error=error_message)

        if not password:
            error_message = "Please enter your password."
            return render_template("instructor_login.html", error=error_message)

        # Query database for the instructor using email
        user = Instructor.query.filter_by(email=email).first()

        # Ensure the instructor exists and the password is correct
        if not user or user.password != password:
            error_message = "Invalid email or password. Please try again."
            return render_template("instructor_login.html", error=error_message)

        # Remember which user has logged in
        session["user_id"] = user.id

        # Redirect user to home page
        return render_template("instructor_home.html", user=user)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("instructor_login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route('/section/<int:section_id>')
def view_section(section_id):
    section = Section.query.get(section_id)

    if section:
        courses = section.courses
        return render_template('section.html', section=section, courses=courses)

    return "Section not found"


# make this based on id


@app.route('/assign_course', methods=['GET', 'POST'])
# instructors if course code similar to course assigned 
# classroom only available
def assign_course():
    # Retrieve instructors with course_assigned attribute equal to the course code
    course_code = request.args.get('course_code', '')
    course = Course.query.filter_by(code=course_code).first()
    instructors = Instructor.query.filter(
        or_(Instructor.course_assigned == course_code, Instructor.course_assigned.is_(None))).all()
    # Retrieve classrooms with available attribute set to 1
    classrooms = Classroom.query.all()

    unassigned_credit_hour = course.unassigned_credit_hour if course else 0
    if request.method == 'GET':
        return render_template('schedule_form.html', course_code=course_code, instructors=instructors,
                               classrooms=classrooms, credit=unassigned_credit_hour)

    elif request.method == 'POST':
        course_code = request.form.get('course_code', '')
        section_id = int(request.form.get('section_id', 0))
        # Retrieve other form fields as needed
        day = request.form.get('day', '')
        start_period = int(request.form.get('start_period', ''))
        end_period = int(request.form.get('end_period', ''))
        classroom_id = int(request.form.get('classroom_id', ''))
        instructor_id = int(request.form.get('instructor_id', ''))
        schedule_type = request.form.get('schedule_type', '')

        duration = end_period - start_period + 1
        course_code = request.form.get('course_code', '')
        course = Course.query.filter_by(code=course_code).first()

        if course and course.unassigned_credit_hour - duration < 0:
            error_message = "Error. You have exceeded the credit hours for this course. Please fix it to continue."
            return render_template("schedule_form.html", error=error_message, section_id=section_id,
                                   course_code=course_code, instructors=instructors, classrooms=classrooms)

        # Check if the same combination of classroom ID, period, and day already exists in availability
        existing_availability = Availability.query.filter_by(classroom_id=classroom_id, weekday=day,
                                                             period=start_period).first()
        if existing_availability:
            error_message = "Error. The classroom is not available for the selected period."
            return render_template("schedule_form.html", error=error_message, section_id=section_id,
                                   course_code=course_code, instructors=instructors, classrooms=classrooms)

        # Create a new Schedule object
        new_schedule = Schedule(
            day=day,
            start_period=start_period,
            end_period=end_period,
            classroom_id=classroom_id,
            instructor_id=instructor_id,
            course_id=course_code,
            section_id=section_id,
            type=schedule_type
        )
        # Add the new schedule to the database
        db.session.add(new_schedule)
        db.session.commit()

        for i in range(duration):
            day_num = int(day)
            period_num = start_period + i
            availability = Availability(
                classroom_id=classroom_id,
                weekday=day_num,
                period=period_num,
                is_available=False
            )
            db.session.add(availability)

        db.session.commit()
        success_message = "You have successfully assigned the schedule."
        return render_template("schedule_form.html", success=success_message, section_id=section_id,
                               course_code=course_code, instructors=instructors, classrooms=classrooms)


@app.route('/view_availability')
def view_availability():
    classrooms = Classroom.query.all()
    availabilities = Availability.query.all()

    # Create a dictionary to store the availability data for each classroom
    availability_data = {}

    # Iterate over each classroom and populate the availability_data dictionary
    for classroom in classrooms:
        classroom_id = classroom.id

        # Filter the availabilities for the current classroom
        classroom_availabilities = [availability for availability in availabilities if
                                    availability.classroom_id == classroom_id]

        # Create a dictionary to store the availability data for each day and period
        classroom_availability_data = {}

        # Iterate over each availability and populate the classroom_availability_data dictionary
        for availability in classroom_availabilities:
            day = availability.weekday
            period = availability.period
            is_available = availability.is_available

            # Check if the classroom_availability_data dictionary has the key for the day
            if day not in classroom_availability_data:
                classroom_availability_data[day] = {}

            # Store the availability status in the classroom_availability_data dictionary
            classroom_availability_data[day][period] = is_available

        # Store the availability data for the classroom in the availability_data dictionary
        availability_data[classroom_id] = classroom_availability_data

    return render_template('classrooms.html', availability_data=availability_data, classrooms=classrooms)


@app.route('/schedule')
def view_schedule():
    # Retrieve the sections data from the database
    sections = Section.query.all()
    schedules_by_section = {}

    for section in sections:
        schedules = Schedule.query.filter_by(section_id=section.id).all()
        schedules_by_section[section] = schedules

    days_mapping = {
        1: 'Monday',
        2: 'Tuesday',
        3: 'Wednesday',
        4: 'Thursday',
        5: 'Friday'
    }

    # Pass the schedules and sections to the template for rendering
    return render_template('schedule.html', schedules_by_section=schedules_by_section, days_mapping=days_mapping)


@app.route("/view_my_schedule", methods=["POST", "GET"])
def view_my_schedule():
    if request.method == "POST":
        section = request.form.get("section")

        # Fetch the schedule from the database based on the section and year
        schedule = Schedule.query.filter_by(section_id=section).all()

        return render_template("student_home.html", section=section, schedule=schedule)

    # Fetch all sections from the database
    sections = Section.query.all()

    return render_template("student_home.html", sections=sections)
