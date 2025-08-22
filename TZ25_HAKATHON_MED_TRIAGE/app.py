from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, send_file
from agents import receive_symptom_message, SYMPTOM_CONVERSATION
from langchain_core.messages import HumanMessage, AIMessage
import os
import datetime
import pickle
import json
import io
from werkzeug.utils import secure_filename
from typing import List
import traceback
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
from markdown import markdown # For converting summary to HTML
from itsdangerous import URLSafeTimedSerializer
from urllib.parse import urljoin
from pdf_generator import generate_pdf

# Try importing Google API client
try:
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("Google API client not available. Calendar integration will be simulated.")

# --- Configuration ---
app = Flask(__name__, static_folder="static")
app.secret_key = "hackwave2025"  # Secret key for session management

# Email configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "likhith.b.polavaram@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "yeqh udvd pvra ptxs")

# Initialize URL safe serializer for tokens
serializer = URLSafeTimedSerializer(app.secret_key)

def generate_appointment_token(appointment_data):
    """Generate a secure token for appointment actions"""
    return serializer.dumps(appointment_data)

def verify_appointment_token(token, max_age=3600):
    """Verify and decode the appointment token"""
    try:
        return serializer.loads(token, max_age=max_age)
    except:
        return None

def get_base_url():
    """Get the base URL for the application"""
    return request.host_url.rstrip('/')

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Create appointments directory for storing responses
APPOINTMENTS_FOLDER = 'appointments'
if not os.path.exists(APPOINTMENTS_FOLDER):
    os.makedirs(APPOINTMENTS_FOLDER)

def save_appointment_data(appointment_data):
    """Save appointment data to prevent duplicate responses"""
    appointment_id = appointment_data.get('id')
    if not appointment_id:
        return False
    
    filename = os.path.join(APPOINTMENTS_FOLDER, f'{appointment_id}.json')
    with open(filename, 'w') as f:
        json.dump(appointment_data, f)
    return True

# --- Sample Data ---
DOCTORS = [
    {
        "id": "1", "name": "Dr. Priya Sharma", "specialization": "Gastroenterologist",
        "experience": 12, "languages": "Hindi, English, Marathi", "consultation_fee": 1500,
        "rating": 4.9, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["09:00 AM", "11:30 AM", "02:00 PM", "04:30 PM"]
    },
    {
        "id": "2", "name": "Dr. Arjun Reddy", "specialization": "Cardiologist",
        "experience": 15, "languages": "Telugu, English, Hindi", "consultation_fee": 1800,
        "rating": 4.8, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["10:00 AM", "01:00 PM", "03:30 PM", "05:00 PM"]
    },
    {
        "id": "3", "name": "Dr. Kavitha Menon", "specialization": "Dermatologist",
        "experience": 10, "languages": "Malayalam, English, Tamil", "consultation_fee": 1200,
        "rating": 4.7, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["09:30 AM", "12:00 PM", "02:30 PM", "04:00 PM"]
    },
    {
        "id": "4", "name": "Dr. Rajesh Kumar", "specialization": "Neurologist",
        "experience": 14, "languages": "Hindi, English, Punjabi", "consultation_fee": 2000,
        "rating": 4.9, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["08:30 AM", "11:00 AM", "01:30 PM", "05:30 PM"]
    },
    {
        "id": "5", "name": "Dr. Anjali Gupta", "specialization": "Psychiatrist",
        "experience": 11, "languages": "Hindi, English, Bengali", "consultation_fee": 1600,
        "rating": 4.6, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["10:30 AM", "12:30 PM", "03:00 PM", "05:30 PM"]
    },
    {
        "id": "6", "name": "Dr. Suresh Iyer", "specialization": "Orthopedic Surgeon",
        "experience": 18, "languages": "Tamil, English, Kannada", "consultation_fee": 2200,
        "rating": 4.8, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["09:00 AM", "11:00 AM", "02:00 PM", "04:00 PM"]
    },
    {
        "id": "7", "name": "Dr. Meera Patel", "specialization": "Pediatrician",
        "experience": 13, "languages": "Gujarati, English, Hindi", "consultation_fee": 1400,
        "rating": 4.9, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["08:00 AM", "10:30 AM", "01:00 PM", "03:30 PM"]
    },
    {
        "id": "8", "name": "Dr. Vikram Singh", "specialization": "Urologist",
        "experience": 16, "languages": "Punjabi, Hindi, English", "consultation_fee": 1900,
        "rating": 4.7, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["09:30 AM", "12:00 PM", "02:30 PM", "05:00 PM"]
    },
    {
        "id": "9", "name": "Dr. Lakshmi Rao", "specialization": "Gynecologist",
        "experience": 14, "languages": "Kannada, English, Telugu", "consultation_fee": 1700,
        "rating": 4.8, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["10:00 AM", "12:30 PM", "03:00 PM", "05:30 PM"]
    },
    {
        "id": "10", "name": "Dr. Amit Joshi", "specialization": "Ophthalmologist",
        "experience": 12, "languages": "Marathi, Hindi, English", "consultation_fee": 1300,
        "rating": 4.6, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["08:30 AM", "11:30 AM", "01:30 PM", "04:30 PM"]
    },
    {
        "id": "11", "name": "Dr. Deepika Nair", "specialization": "Endocrinologist",
        "experience": 10, "languages": "Malayalam, English, Tamil", "consultation_fee": 1800,
        "rating": 4.7, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["09:00 AM", "11:00 AM", "02:00 PM", "04:00 PM"]
    },
    {
        "id": "12", "name": "Dr. Ravi Agarwal", "specialization": "Pulmonologist",
        "experience": 17, "languages": "Hindi, English, Rajasthani", "consultation_fee": 2000,
        "rating": 4.9, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["10:00 AM", "12:00 PM", "03:00 PM", "05:00 PM"]
    },
    {
        "id": "13", "name": "Dr. Sushma Bhatt", "specialization": "Rheumatologist",
        "experience": 11, "languages": "Gujarati, Hindi, English", "consultation_fee": 1600,
        "rating": 4.5, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["09:30 AM", "11:30 AM", "01:30 PM", "04:30 PM"]
    },
    {
        "id": "14", "name": "Dr. Karthik Krishnamurthy", "specialization": "Oncologist",
        "experience": 19, "languages": "Tamil, English, Telugu", "consultation_fee": 2500,
        "rating": 4.9, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["08:00 AM", "10:00 AM", "01:00 PM", "03:00 PM"]
    },
    {
        "id": "15", "name": "Dr. Sunita Mishra", "specialization": "Nephrologist",
        "experience": 13, "languages": "Hindi, English, Odia", "consultation_fee": 1900,
        "rating": 4.8, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["09:00 AM", "11:30 AM", "02:30 PM", "05:00 PM"]
    },
    {
        "id": "16", "name": "Dr. Harish Chandra", "specialization": "ENT Specialist",
        "experience": 15, "languages": "Hindi, English, Punjabi", "consultation_fee": 1500,
        "rating": 4.7, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["08:30 AM", "10:30 AM", "01:00 PM", "04:00 PM"]
    },
    {
        "id": "17", "name": "Dr. Preeti Desai", "specialization": "Hematologist",
        "experience": 12, "languages": "Gujarati, English, Hindi", "consultation_fee": 1800,
        "rating": 4.6, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["10:00 AM", "12:30 PM", "02:00 PM", "04:30 PM"]
    },
    {
        "id": "18", "name": "Dr. Manoj Tripathi", "specialization": "Anesthesiologist",
        "experience": 14, "languages": "Hindi, English, Bengali", "consultation_fee": 1700,
        "rating": 4.8, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["09:30 AM", "11:00 AM", "01:30 PM", "05:30 PM"]
    },
    {
        "id": "19", "name": "Dr. Radha Venkatesh", "specialization": "Radiologist",
        "experience": 16, "languages": "Tamil, English, Kannada", "consultation_fee": 1600,
        "rating": 4.7, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["08:00 AM", "10:00 AM", "02:00 PM", "04:00 PM"]
    },
    {
        "id": "20", "name": "Dr. Ashok Bansal", "specialization": "General Physician",
        "experience": 20, "languages": "Hindi, English, Punjabi", "consultation_fee": 1200,
        "rating": 4.9, "email": "likhith.b.polavaram@gmail.com", # Replace with actual doctor email
        "available_slots": ["08:30 AM", "11:30 AM", "02:30 PM", "05:00 PM"]
    }
]

# --- Helper Functions ---

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_email_with_attachments(sender_email, sender_password, recipient_email,
                              subject, body, attachment_list=None):
    """Sends an email with attachments using SMTP."""
    try:
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'html'))

        if attachment_list:
            for attachment in attachment_list:
                file_path = attachment.get('path')
                if not file_path or not os.path.exists(file_path):
                    print(f"Skipping attachment - file not found: {file_path}")
                    continue
                
                filename = attachment.get('filename') or os.path.basename(file_path)
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type is None:
                    content_type = "application/octet-stream"
                
                main_type, sub_type = content_type.split('/', 1)

                with open(file_path, 'rb') as file:
                    part = MIMEBase(main_type, sub_type)
                    part.set_payload(file.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 'attachment', filename=filename)
                    message.attach(part)
                    print(f"Attached file: {filename}")

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(message)
        server.quit()
        print(f"Email sent successfully to {recipient_email}")
        return {"success": True, "message": f"Email sent to {recipient_email}"}

    except Exception as e:
        print(f"Error sending email: {str(e)}")
        traceback.print_exc()
        return {"success": False, "message": f"Failed to send email: {str(e)}"}

def send_doctor_appointment_request(doctor_email, patient_email, scheduled_time, symptom_summary, 
                                 meet_link, attachments=None, primary_symptoms=None, 
                                 additional_symptoms=None, symptom_duration=None):
    """Send appointment request email to doctor with accept/reject buttons"""
    try:
        # Find doctor information
        doctor_info = next((d for d in DOCTORS if d['email'] == doctor_email), None)
        if not doctor_info:
            return {"success": False, "message": "Doctor not found"}
        
        # Generate unique appointment ID
        import hashlib
        import time
        appointment_id = hashlib.md5(f"{doctor_email}{patient_email}{scheduled_time}{time.time()}".encode()).hexdigest()[:12]
        
        # Generate appointment token
        appointment_data = {
            'id': appointment_id,
            'doctor_email': doctor_email,
            'patient_email': patient_email,
            'appointment_time': scheduled_time,
            'meet_link': meet_link,
            'doctor_name': doctor_info['name'],
            'doctor_specialization': doctor_info['specialization'],
            'symptom_summary': symptom_summary,
            'primary_symptoms': primary_symptoms,
            'additional_symptoms': additional_symptoms,
            'symptom_duration': symptom_duration
        }
        token = generate_appointment_token(appointment_data)
        
        # Generate accept/reject URLs
        base_url = request.host_url.rstrip('/')
        accept_url = f"{base_url}/appointment/response/{token}?action=accept"
        reject_url = f"{base_url}/appointment/response/{token}?action=reject"
        
        # Render email template
        email_body = render_template('email_doctor.html',
            patient_email=patient_email,
            scheduled_time=scheduled_time,
            symptom_summary=symptom_summary,
            primary_symptoms=primary_symptoms or "Not specified",
            additional_symptoms=additional_symptoms,
            symptom_duration=symptom_duration,
            meet_link=meet_link,
            accept_url=accept_url,
            reject_url=reject_url,
            token=token
        )
        
        return send_email_with_attachments(
            EMAIL_SENDER,
            EMAIL_PASSWORD,
            doctor_email,
            "New Patient Appointment Request",
            email_body,
            attachments
        )
    except Exception as e:
        print(f"Error sending doctor appointment request: {str(e)}")
        traceback.print_exc()
        return {"success": False, "message": str(e)}

def send_patient_confirmation_email(patient_email, doctor_name, scheduled_time, meet_link, doctor_specialization=None):
    """Send confirmation email to patient when doctor accepts"""
    try:
        email_body = render_template('email_patient.html',
            doctor_name=doctor_name,
            doctor_specialization=doctor_specialization,
            scheduled_time=scheduled_time,
            meet_link=meet_link,
            status="accepted"
        )
        
        return send_email_with_attachments(
            EMAIL_SENDER,
            EMAIL_PASSWORD,
            patient_email,
            f"Appointment Confirmed with {doctor_name}",
            email_body
        )
    except Exception as e:
        print(f"Error sending patient confirmation: {str(e)}")
        traceback.print_exc()
        return {"success": False, "message": str(e)}

def send_patient_rejection_email(patient_email, doctor_name, scheduled_time, doctor_specialization=None):
    """Send rejection email to patient when doctor declines"""
    try:
        email_body = render_template('email_patient.html',
            doctor_name=doctor_name,
            doctor_specialization=doctor_specialization,
            scheduled_time=scheduled_time,
            status="rejected"
        )
        
        return send_email_with_attachments(
            EMAIL_SENDER,
            EMAIL_PASSWORD,
            patient_email,
            f"Appointment Update from {doctor_name}",
            email_body
        )
    except Exception as e:
        print(f"Error sending patient rejection: {str(e)}")
        traceback.print_exc()
        return {"success": False, "message": str(e)}

def authenticate_google_calendar():
    """Authenticate and return Google Calendar API service instance."""
    if not GOOGLE_API_AVAILABLE:
        return None
    
    creds = None
    token_path = "token.pickle"
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        print("Google Calendar credentials not valid or missing.")
        return None
        
    return build("calendar", "v3", credentials=creds)

def schedule_meet_with_notification(scheduled_time, doctor_email, patient_email, description=None, attachments=None):
    """Schedule a Google Meet and notify both doctor & patient via email."""
    service = authenticate_google_calendar()
    
    calendar_success = True
    meet_link = "https://meet.google.com/abc-defg-hij"  # Default mock link
    
    if service:
        try:
            start_time = datetime.datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M")
            end_time = start_time + datetime.timedelta(minutes=30)
            
            event = {
                "summary": "Doctor Appointment",
                "description": description,
                "start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Kolkata"},
                "end": {"dateTime": end_time.isoformat(), "timeZone": "Asia/Kolkata"},
                "attendees": [{"email": doctor_email}, {"email": patient_email}],
                "conferenceData": {
                    "createRequest": {
                        "requestId": f"meet-{start_time.strftime('%Y%m%d%H%M')}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                }
            }
            
            created_event = service.events().insert(
                calendarId="primary",
                body=event,
                conferenceDataVersion=1,
                sendUpdates="all"
            ).execute()
            
            meet_link = created_event.get("hangoutLink", meet_link)
            print(f"Google Calendar event created successfully. Link: {meet_link}")
        
        except Exception as e:
            print(f"Error creating Google Meet: {str(e)}")
            traceback.print_exc()
            calendar_success = False
    else:
        print("Using mock Google Meet integration (Google API credentials not available).")

    # --- Email Notifications ---
    doctor_info = next((d for d in DOCTORS if d["email"] == doctor_email), 
                       {"name": "Your Doctor", "specialization": "Specialist"})
    
    # Render symptom summary from markdown to HTML for emails
    symptom_summary_html = markdown(description)

    # Send appointment request email to Doctor with accept/reject buttons
    if doctor_email:
        result = send_doctor_appointment_request(
            doctor_email=doctor_email,
            patient_email=patient_email,
            scheduled_time=scheduled_time,
            symptom_summary=symptom_summary_html,
            meet_link=meet_link,
            attachments=attachments,
            primary_symptoms=description,  # You can modify this to pass actual primary symptoms
            additional_symptoms=None,  # You can modify this to pass additional symptoms
            symptom_duration=None  # You can modify this to pass symptom duration
        )
        
        if not result.get('success'):
            print(f"Failed to send doctor appointment request: {result.get('message')}")

    # Note: Patient confirmation email will be sent only after doctor accepts the appointment

    return {
        "success": calendar_success,
        "meet_link": meet_link,
        "message": "Google Meet created successfully" if calendar_success else "Failed to create Google Meet, but notifications sent."
    }

# --- Flask Routes ---

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        name = request.form.get('name', '').strip()
        age = request.form.get('age', '').strip()
        contact = request.form.get('contact', '').strip()
        
        # Basic validation
        if not all([name, age, contact]):
            return jsonify({'success': False, 'message': 'Please fill in all fields'})
        
        try:
            age_int = int(age)
            if age_int < 1 or age_int > 120:
                return jsonify({'success': False, 'message': 'Please enter a valid age between 1 and 120'})
        except ValueError:
            return jsonify({'success': False, 'message': 'Please enter a valid age'})
        
        if len(contact) < 10 or not contact.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            return jsonify({'success': False, 'message': 'Please enter a valid contact number'})
        
        # Store user data in session
        session['user_logged_in'] = True
        session['user_name'] = name
        session['user_age'] = age_int
        session['user_contact'] = contact
        
        return jsonify({'success': True, 'message': 'Login successful!'})
        
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred during login'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/home')
def home_page():
    # Check if user is logged in
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))
    
    user_data = {
        'name': session.get('user_name'),
        'age': session.get('user_age'),
        'contact': session.get('user_contact')
    }
    return render_template('index.html', user=user_data)

@app.route('/sel_sym')
def sym_page():
    # Check if user is logged in
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))
    return render_template('symptoms.html')
    
@app.route('/sel_sym1')
def sym_page1():
    # Check if user is logged in
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))
    return render_template('sex.html')

@app.route('/sel_sym2')
def sym_page2():
    # Check if user is logged in
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))
    return render_template('add_sym.html')

@app.route('/hospitals')
def hospitals():
    # Check if user is logged in
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))
    return render_template('hospitals.html')

@app.route('/symptom_analysis')
def symptom_analysis():
    # Check if user is logged in
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))
        
    global SYMPTOM_CONVERSATION
    SYMPTOM_CONVERSATION.clear()
    
    initial_symptoms = session.get('initial_symptoms', '')
    
    welcome_message = AIMessage(content="👋 Hello! I'm your AI Medical Assistant. I'm here to help analyze your symptoms. Please describe how you're feeling.")
    SYMPTOM_CONVERSATION.append(welcome_message)
    
    if initial_symptoms:
        symptoms_list = [s.strip() for s in initial_symptoms.split(',') if s.strip()]
        if symptoms_list:
            initial_message = f"I have the following symptoms: {', '.join(symptoms_list)}"
            receive_symptom_message(initial_message)
    
    return render_template('symptom_analysis.html', conversation=SYMPTOM_CONVERSATION)

@app.route('/predict_1', methods=['POST'])
def predict_1():
    selected_symptoms = request.form.get('selected_symptoms', '')
    additional_symptoms = request.form.get('selected_symptoms_frommodel', '')
    
    all_symptoms = selected_symptoms
    if additional_symptoms:
        all_symptoms += f", {additional_symptoms}" if all_symptoms else additional_symptoms
        
    session['initial_symptoms'] = all_symptoms
    return redirect(url_for('symptom_analysis'))

@app.route('/api/send_message', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        message = data.get('message')
        
        result = receive_symptom_message(message)
        response = SYMPTOM_CONVERSATION[-1].content
        
        return jsonify({
            'message': response,
            'show_booking': result.get('show_booking', False),
            'symptom_details': result.get('symptom_details', {})
        })
    except Exception as e:
        print(f"API ERROR: {str(e)}")
        return jsonify({
            'message': "I apologize for the technical difficulties. Please try again.",
            'show_booking': False
        })

@app.route('/api/set_gender', methods=['POST'])
def set_gender():
    try:
        data = request.get_json()
        gender = data.get('gender')
        
        if gender in ['Male', 'Female']:
            session['user_gender'] = gender
            return jsonify({'success': True, 'message': 'Gender set successfully'})
        else:
            return jsonify({'success': False, 'message': 'Invalid gender selection'})
    except Exception as e:
        print(f"Error setting gender: {str(e)}")
        return jsonify({'success': False, 'message': 'Error setting gender'})

@app.route('/download_report', methods=['GET'])
def download_report():
    """Generate and stream a PDF report based on user's latest analysis."""
    try:
        # Gather comprehensive user data from session
        user_data = {
            # User login information
            'name': session.get('user_name', 'Not provided'),
            'age': session.get('user_age', 'Not provided'),
            'contact': session.get('user_contact', 'Not provided'),
            
            # Gender from sex.html
            'gender': session.get('user_gender', session.get('gender', 'Not specified')),
            
            # Symptom information
            'symptoms': session.get('initial_symptoms', 'No symptoms recorded'),
            'severity': session.get('severity') or (session.get('symptom_details') or {}).get('severity') or 'Not specified',
            
            # Analysis data
            'predicted_disease': session.get('predicted_disease'),
            'analysis_summary': session.get('symptom_summary', 'No analysis summary available'),
        }

        pdf_bytes, filename = generate_pdf(user_data)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        traceback.print_exc()
        flash('Failed to generate report. Please try again later.', 'error')
        return redirect(url_for('symptom_analysis'))

@app.route('/appointment/response/<token>')
def handle_appointment_response(token):
    """Handle doctor's response to appointment request"""
    action = request.args.get('action')
    if action not in ['accept', 'reject']:
        flash('Invalid action specified', 'error')
        return render_template('appointment_response.html', status='error')
    
    try:
        appointment_data = verify_appointment_token(token)
        if not appointment_data:
            flash('Invalid or expired appointment link', 'error')
            return render_template('appointment_response.html', status='error')
        
        # Check if this appointment has already been responded to
        appointment_id = appointment_data.get('id')
        if appointment_id:
            appointment_file = os.path.join(APPOINTMENTS_FOLDER, f'{appointment_id}.json')
            if os.path.exists(appointment_file):
                with open(appointment_file, 'r') as f:
                    existing_data = json.load(f)
                    if existing_data.get('status'):
                        flash('This appointment has already been responded to', 'warning')
                        return render_template('appointment_response.html', 
                                           status='already_handled',
                                           appointment=existing_data)
            
        # Mark the appointment as handled to prevent duplicate responses
        appointment_data['status'] = action
        appointment_data['response_time'] = datetime.datetime.now().isoformat()
        save_appointment_data(appointment_data)
        
        if action == 'accept':
            # Send confirmation to patient
            result = send_patient_confirmation_email(
                appointment_data['patient_email'],
                appointment_data['doctor_name'],
                appointment_data['appointment_time'],
                appointment_data['meet_link'],
                appointment_data.get('doctor_specialization')
            )
            
            if result.get('success'):
                message = f"Appointment accepted successfully! Patient has been notified via email."
            else:
                message = f"Appointment accepted, but failed to notify patient: {result.get('message')}"
                
        else:  # action == 'reject'
            # Send rejection to patient
            result = send_patient_rejection_email(
                appointment_data['patient_email'],
                appointment_data['doctor_name'],
                appointment_data['appointment_time'],
                appointment_data.get('doctor_specialization')
            )
            
            if result.get('success'):
                message = f"Appointment declined. Patient has been notified via email."
            else:
                message = f"Appointment declined, but failed to notify patient: {result.get('message')}"
        
        return render_template('appointment_response.html',
                           status='accepted' if action == 'accept' else 'rejected',
                           appointment=appointment_data,
                           message=message)
                           
    except Exception as e:
        print(f"Error processing appointment response: {str(e)}")
        traceback.print_exc()
        flash(f'Error processing appointment: {str(e)}', 'error')
        return render_template('appointment_response.html', status='error')

@app.route('/book_appointment')
def book_appointment():
    # Check if user is logged in
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))
        
    summary = ""
    # Find the last AI message, preferably one with a recommendation
    for msg in reversed(SYMPTOM_CONVERSATION):
        if isinstance(msg, AIMessage):
            summary = msg.content
            if any(word in msg.content.lower() for word in ["recommend", "specialist", "doctor"]):
                break
    
    session['symptom_summary'] = summary
    
    recommended_specialist = "General Practitioner"
    specialist_types = [
        "Gastroenterologist", "Cardiologist", "Dermatologist", 
        "Neurologist", "Psychiatrist", "Orthopedic Surgeon", "Pediatrician",
        "Urologist", "Gynecologist", "Ophthalmologist", "Endocrinologist",
        "Pulmonologist", "Rheumatologist", "Oncologist", "Nephrologist",
        "ENT Specialist", "Hematologist", "Anesthesiologist", "Radiologist",
        "General Physician"
    ]
    
    for specialist in specialist_types:
        if specialist.lower() in summary.lower():
            recommended_specialist = specialist
            break
    
    filtered_doctors = [d for d in DOCTORS if recommended_specialist.lower() in d["specialization"].lower()]
    if not filtered_doctors:
        filtered_doctors = DOCTORS
    
    summary_html = markdown(summary) if summary else ""
    
    return render_template('book_appointment.html', 
                           doctors=filtered_doctors, 
                           summary=summary_html,
                           email=session.get('patient_email', ''))

@app.route('/api/book_appointment', methods=['POST'])
def api_book_appointment():
    try:
        doctor_id = request.form.get('doctor_id')
        time_slot = request.form.get('time_slot')
        patient_email = request.form.get('patient_email')
        
        if not all([doctor_id, time_slot, patient_email]):
            return jsonify({'success': False, 'message': 'Missing required information'})
        
        session['patient_email'] = patient_email
        doctor = next((d for d in DOCTORS if d['id'] == doctor_id), None)
        if not doctor:
            return jsonify({'success': False, 'message': 'Doctor not found'})
        
        uploaded_files = []
        for key in request.files:
            file = request.files[key]
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                uploaded_files.append({
                    'filename': filename,
                    'path': file_path,
                    'type': file.content_type
                })
                print(f"Uploaded file: {filename}")
        
        today = datetime.date.today()
        time_obj = datetime.datetime.strptime(time_slot.strip(), "%I:%M %p").time()
        appointment_dt = datetime.datetime.combine(today, time_obj)
        formatted_datetime = appointment_dt.strftime("%Y-%m-%d %H:%M")
        
        symptom_summary = session.get('symptom_summary', 'No symptom analysis available.')
        
        meeting_result = schedule_meet_with_notification(
            formatted_datetime, 
            doctor['email'], 
            patient_email,
            symptom_summary,
            uploaded_files
        )
        
        appointment_data = {
            'doctor_name': doctor['name'],
            'doctor_specialization': doctor['specialization'],
            'appointment_time': appointment_dt.strftime("%Y-%m-%d %I:%M %p"),
            'patient_email': patient_email,
            'meet_link': meeting_result.get('meet_link', ''),
        }
        session['last_appointment'] = appointment_data
        
        return jsonify({'success': True, 'message': 'Appointment booked successfully!', **appointment_data})
        
    except Exception as e:
        print(f"Error booking appointment: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error booking appointment: {str(e)}'})

@app.route('/appointment_confirmation')
def appointment_confirmation():
    appointment = session.get('last_appointment')
    if not appointment:
        flash('No recent appointment found. Please book one first.', 'warning')
        return redirect(url_for('book_appointment'))
    
    return render_template('appointment_confirmation.html', appointment=appointment)

@app.route('/medical_history')
def medical_history():
    """Medical History Dashboard page"""
    if 'user_name' not in session:
        return redirect(url_for('login'))
    
    # Gather current medical status and previous symptoms
    medical_data = {
        # User information
        'user_name': session.get('user_name', 'Not provided'),
        'user_age': session.get('user_age', 'Not provided'),
        'user_contact': session.get('user_contact', 'Not provided'),
        'user_gender': session.get('user_gender', 'Not specified'),
        
        # Current medical status
        'current_symptoms': session.get('initial_symptoms'),
        'predicted_disease': session.get('predicted_disease'),
        'symptom_summary': session.get('symptom_summary'),
        
        # Previous symptoms from session history
        'previous_symptoms': session.get('symptom_history', []),
        
        # Check if user has any medical data
        'has_medical_data': bool(session.get('initial_symptoms') or session.get('predicted_disease')),
        
        # Uploaded reports
        'uploaded_reports': session.get('uploaded_reports', [])
    }
    
    return render_template('medical_history.html', user=session, medical_data=medical_data)

@app.route('/upload_medical_report', methods=['POST'])
def upload_medical_report():
    """Handle medical report file uploads"""
    if 'user_name' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'})
    
    try:
        if 'medical_report' not in request.files:
            return jsonify({'success': False, 'message': 'No file selected'})
        
        file = request.files['medical_report']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        # Check file type
        allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({'success': False, 'message': 'Invalid file type. Please upload PDF, DOC, DOCX, or image files.'})
        
        # Create uploads directory if it doesn't exist
        upload_folder = os.path.join(app.root_path, 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Secure filename and save
        filename = secure_filename(file.filename)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{session['user_name']}_{timestamp}_{filename}"
        file_path = os.path.join(upload_folder, safe_filename)
        
        file.save(file_path)
        
        # Store in session
        if 'uploaded_reports' not in session:
            session['uploaded_reports'] = []
        
        report_info = {
            'filename': filename,
            'safe_filename': safe_filename,
            'upload_date': datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            'file_size': os.path.getsize(file_path)
        }
        
        session['uploaded_reports'].append(report_info)
        session.modified = True
        
        return jsonify({'success': True, 'message': 'Medical report uploaded successfully'})
        
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        return jsonify({'success': False, 'message': 'Error uploading file. Please try again.'})

if __name__ == "__main__":
    app.run(debug=True, port=5000)