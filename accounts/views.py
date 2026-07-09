from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib import messages
from django.db.models import Count, Sum
import random
import re
import json
import requests
from datetime import datetime

# CORE IMPORTS
from .models import Patient, HospitalOwner, Hospital, Doctor, Booking

# In-memory storage for OTPs (Use database model for production)
otp_storage = {}

# ----------------------------------------------------------------------
# --- PATIENT FLOW VIEWS (OTP-based) ---
# ----------------------------------------------------------------------
def landing(request):
    return render(request, 'accounts/landing.html')

def send_otp_page(request):
    return render(request, 'accounts/send_otp.html')

def doctors_loginpage_view(request):
    return render(request, 'accounts/doctors_loginpage.html')

def verify_otp_page(request):
    return render(request, 'accounts/verify_otp.html')

def hospital_owner_login_page(request):
    return render(request, 'accounts/hospital_loginpage.html')

def doctor_booking_page(request):
    return render(request, 'accounts/doctor_booking.html')

def pharmacy_login(request):
    return render(request, 'accounts/pharmacy_loginpage.html')

def pharmacy_dashboard(request):
    return render(request, 'accounts/pharmacy_dashboard.html')

def lab_login(request):
    return render(request, 'accounts/lab_loginpage.html')

def lab_dashboard(request):
    return render(request, 'accounts/lab_dashboard.html')

def medical_records(request):
    return render(request, 'accounts/Medicine.html')

def labs(request):
    return render(request, 'accounts/Labs.html')

def records(request):
    return render(request, 'accounts/records.html')

def emi_payment(request):
    return render(request, 'accounts/emi.html')

def ai_bill_analyzer(request):
    gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
    gemini_model = getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-flash')
    return render(request, 'accounts/aibill.html', {
        'gemini_api_key': gemini_key,
        'gemini_model': gemini_model
    })

def payment(request):
    return render(request, 'accounts/payment.html')

def doctor_dashboard(request):
    doctor_id = request.session.get("doctor_id")

    if not doctor_id:
        return redirect("doctor_login")  # protection if session empty

    doctor = Doctor.objects.get(id=doctor_id)

    return render(request, "accounts/doctors_dashboard.html", {
        "doctor_name": doctor.name,
    })


def dashboard(request):
    """Patient Dashboard - Requires phone session key."""

    # 1. Check if the user is logged in
    if 'phone' not in request.session:
        return redirect('/')

    phone_number = request.session.get('phone')

    # 2. Retrieve the Patient object from the database
    try:
        current_patient = Patient.objects.get(phone=phone_number)
    except Patient.DoesNotExist:
        # Handle case: User is logged in but patient record is missing
        return redirect('/')

    # 3. Pass the Patient object to the template context
    return render(request, 'accounts/dashboard.html', {
        'patient': current_patient,
    })

@require_http_methods(["POST"])
@csrf_exempt
def check_patient_exists(request):
    """Checks if a patient exists or auto-creates them to bypass registration/OTP."""
    try:
        data = json.loads(request.body)
        phone = data.get("phone", "").strip()

        if not phone or not re.match(r"^\d{10}$", phone):
            return JsonResponse({'exists': False, 'message': 'Invalid phone number'}, status=400)

        # Bypass/Testing: Ensure the patient exists in the database
        Patient.objects.get_or_create(
            phone=phone,
            defaults={
                'abha_id': random.randint(10000000000000, 99999999999999),
                'name': f'Patient {phone}',
                'blood_grp': 'O+',
                'age': 30
            }
        )

        return JsonResponse({'exists': True})

    except Exception as e:
        return JsonResponse({'exists': False, 'message': f'Internal Server Error: {str(e)}'}, status=500)

@require_http_methods(["POST"])
@csrf_exempt
def send_otp(request):
    try:
        data = json.loads(request.body)
        phone = data.get("phone", "").strip()

        if not phone or not re.match(r"^\d{10}$", phone):
            return JsonResponse({"status": "error", "message": "Invalid phone number"})

        # Ensure patient exists
        Patient.objects.get_or_create(
            phone=phone,
            defaults={
                'abha_id': random.randint(10000000000000, 99999999999999),
                'name': f'Patient {phone}',
                'blood_grp': 'O+',
                'age': 30
            }
        )

        # Bypass: do not send actual SMS/WhatsApp OTP, just return success
        return JsonResponse({"status": "success", "message": "OTP sending bypassed"})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})

@require_http_methods(["POST"])
@csrf_exempt
def verify_otp(request):
    try:
        data = json.loads(request.body)
        phone = data.get("phone", "").strip()
        
        # Bypass OTP check: immediately log the user in by setting session phone
        request.session["phone"] = phone
        return JsonResponse({"status": "success", "message": "OTP verified (Bypassed)"})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})

# ----------------------------------------------------------------------
# --- HOSPITAL OWNER FLOW VIEWS (Password-based, Filtered by ID) ---
# ----------------------------------------------------------------------

def render_hospital_login(request):
    """Renders the main hospital login page."""
    return render(request, 'accounts/hospital_loginpage.html')


@csrf_exempt
def hospital_owner_login_api(request):
    if request.method != 'POST':
        return JsonResponse({'message': 'Only POST requests are allowed.'}, status=405)

    try:
        data = json.loads(request.body)
        owner_username = data.get('nin')  # Using 'nin' from frontend as the username/login_id
        password = data.get('password')
    except json.JSONDecodeError:
        return JsonResponse({'message': 'Invalid JSON format'}, status=400)

    # --- AUTHENTICATION: HOSPITAL OWNER LOGIN ---
    try:
        # 1. Look up the HospitalOwner record by username
        owner_instance = HospitalOwner.objects.get(username=owner_username)

        if owner_instance.password == password:
            # Hospital Owner Login SUCCESS
            hospital_id = owner_instance.hospital.id

            # 2. Log in the associated specific User account for session tracking
            try:
                system_user = User.objects.get(username=owner_username)
                login(request, system_user)  # Establish Django session
            except User.DoesNotExist:
                return JsonResponse({'message': 'Owner account found, but session user is missing (User model).'}, status=500)

            # 3. Redirect the owner to the specialized admin dashboard
            redirect_url = f'/accounts/dashboard/admin/{hospital_id}/'

            return JsonResponse({
                'message': f'Facility Access Granted: {owner_instance.hospital.name}',
                'redirectUrl': redirect_url
            }, status=200)

        else:
             # Password mismatch
             raise HospitalOwner.DoesNotExist

    except HospitalOwner.DoesNotExist:
        pass

    # --- FINAL FAILURE ---
    return JsonResponse({'message': 'Invalid ID or Password.'}, status=401)


# --- DASHBOARD VIEW (Authorization Enforced) ---
@login_required
def hospital_owner_dashboard(request, hospital_id):
    """Checks for both authentication (@login_required) and authorization (ID/Role)."""

    # 1. Get the Hospital instance
    hospital = get_object_or_404(Hospital, id=hospital_id)

    # 2. Authorization Check: Ensure the logged-in user is the actual owner of this hospital
    try:
        owner_instance = HospitalOwner.objects.get(hospital=hospital)

        if request.user.username != owner_instance.username:
            return HttpResponseForbidden("Access Denied: Not the authorized Hospital Owner.")

    except HospitalOwner.DoesNotExist:
        return HttpResponseForbidden("Configuration Error: Hospital Owner not defined.")

    # Authorization Passed
    return render(request, 'accounts/hospitaldashboard.html', {
        'hospital_id': hospital_id,
        'hospital_name': hospital.name,
        'owner_username': request.user.username
    })


# ----------------------------------------------------------------------
# --- DASHBOARD API VIEW (WITH FILTERING) ---
# ----------------------------------------------------------------------

@require_http_methods(["GET"])
def get_dashboard_data(request, hospital_id):
    """Fetches dashboard data filtered by the provided hospital_id."""
    try:
        # 1. Get the target Hospital
        hospital = Hospital.objects.get(id=hospital_id)

        # 2. Appointments Count
        appointments_count = Booking.objects.filter(doctor__hospitals=hospital).count()

        # 3. Doctors Data (Filtered)
        doctors_data = []
        doctors_qs = hospital.doctors.all()[:4]

        for doc in doctors_qs:
            next_slot_time = "—"
            status_text = "Off"
            status_class = "off"

            if doc.available:
                status_class = "online"
                status_text = "Online"

                next_booking = doc.bookings.filter(time__gt=datetime.now().time()).order_by('time').first()
                if next_booking:
                    next_slot_time = f"Today, {next_booking.time.strftime('%I:%M %p')}"
                    status_class = "busy"
                    status_text = "Busy"

            doctors_data.append({
                'name': doc.name,
                'spec': doc.specification,
                'slot': next_slot_time,
                'status': status_class,
                'status_text': status_text,
            })

        # 4. Upcoming Appointments (Filtered by Hospital)
        upcoming_bookings = Booking.objects.select_related('patient', 'doctor') \
            .filter(doctor__hospitals=hospital, availability=True, time__gt=datetime.now().time()) \
            .order_by('time')[:2]

        upcoming_data = []
        for booking in upcoming_bookings:
            upcoming_data.append({
                'patient': booking.patient.name,
                'doc': booking.doctor.name,
                'time': booking.time.strftime('%A, %I:%M %p'),
                'status': 'Confirmed',
            })

        # --- Combine all data ---
        dashboard_data = {
            'kpis': {
                'revenue_today': f"₹ {hospital.revenue:,.0f}",
                'appointments_count': appointments_count,
            },
            'doctors': doctors_data,
            'upcoming': upcoming_data,
            'charts': {
                'appointments_7d': {
                    'labels': ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
                    'booked': [34,28,36,30,40,22,20],
                    'walkin': [12,8,10,6,14,8,4]
                },
            }
        }

        return JsonResponse(dashboard_data)

    except Hospital.DoesNotExist:
        return JsonResponse({'error': 'Hospital not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Internal Server Error: {str(e)}'}, status=500)


# ----------------------------------------------------------------------
# --- DOCTOR FLOW VIEWS ---
# ----------------------------------------------------------------------

def doctor_dashboard_view(request, hospital_id):
    """Renders the Doctor's Command Center."""
    hospital = get_object_or_404(Hospital, id=hospital_id)

    return render(request, 'accounts/doctors_dashboard.html', {
        'hospital_id': hospital_id,
        'hospital_name': hospital.name
    })


@csrf_exempt
def doctor_login(request):
    if request.method == "POST":
        data = json.loads(request.body)
        doc_id = data.get("doc_id")
        pin = data.get("pin")

        doctor = Doctor.objects.filter(id=doc_id, pin=pin).first()

        if doctor:
            request.session["doctor_id"] = doctor.id
            request.session["doctor_name"] = doctor.name

            return JsonResponse({
                "status": "success",
                "doctor_name": doctor.name,
                "redirect_url": "/doctor/dashboard/"
            })

        return JsonResponse({"status": "error", "message": "Invalid ID or PIN"})

    # Handle GET request — return method not allowed
    return JsonResponse({"status": "error", "message": "Only POST requests are allowed."}, status=405)


@csrf_exempt
@require_http_methods(["POST"])
def update_doctor_availability(request):
    """Updates the 'available' status of the logged-in doctor (session-based)."""
    try:
        doctor_id = request.session.get("doctor_id")
        if not doctor_id:
            return JsonResponse({"status": "error", "message": "Not logged in"}, status=401)

        data = json.loads(request.body)
        status = data.get("is_available")

        doctor = Doctor.objects.get(id=doctor_id)
        doctor.available = status
        doctor.save()

        return JsonResponse({"status": "success", "is_available": doctor.available})

    except Doctor.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Doctor not found"}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
