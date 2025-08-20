from flask import Flask, redirect, url_for, flash, render_template
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta

def init_appointment_status(app):
    # Create a serializer for generating secure tokens
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    def generate_appointment_token(appointment_data):
        """Generate a secure token for appointment actions"""
        return serializer.dumps(appointment_data)

    def verify_appointment_token(token, max_age=3600):
        """Verify and decode the appointment token"""
        try:
            appointment_data = serializer.loads(token, max_age=max_age)
            return appointment_data
        except:
            return None

    @app.route('/appointment/accept/<token>')
    def accept_appointment(token):
        appointment_data = verify_appointment_token(token)
        if not appointment_data:
            flash('Invalid or expired appointment link.', 'error')
            return render_template('appointment_response.html', status='error')
        
        try:
            # Send confirmation email to patient
            send_patient_confirmation_email(
                appointment_data['patient_email'],
                appointment_data['doctor_name'],
                appointment_data['appointment_time'],
                appointment_data['meet_link']
            )
            
            return render_template('appointment_response.html', 
                                status='accepted',
                                appointment=appointment_data)
        except Exception as e:
            flash(f'Error processing appointment: {str(e)}', 'error')
            return render_template('appointment_response.html', status='error')

    @app.route('/appointment/reject/<token>')
    def reject_appointment(token):
        appointment_data = verify_appointment_token(token)
        if not appointment_data:
            flash('Invalid or expired appointment link.', 'error')
            return render_template('appointment_response.html', status='error')
        
        try:
            # Send rejection email to patient
            send_patient_rejection_email(
                appointment_data['patient_email'],
                appointment_data['doctor_name'],
                appointment_data['appointment_time']
            )
            
            return render_template('appointment_response.html', 
                                status='rejected',
                                appointment=appointment_data)
        except Exception as e:
            flash(f'Error processing appointment: {str(e)}', 'error')
            return render_template('appointment_response.html', status='error')

    return generate_appointment_token
