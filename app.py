from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.urls import url_parse
from config import Config
from models import db, User, ParkingLot, ParkingSpace, Vehicle, Booking, Payment
import os
import random
import string
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__, instance_relative_config=True)
app.config.from_object(Config)

# Initialize Flask extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

# Create instance folder
os.makedirs(app.instance_path, exist_ok=True)

# Create all database tables
with app.app_context():
    db.create_all()
    
    # Create admin user if it doesn't exist
    admin = User.query.filter_by(email=Config.ADMIN_EMAIL).first()
    if not admin:
        admin = User(
            username='admin',
            email=Config.ADMIN_EMAIL,
            role='admin',
            phone='1234567890',
            address='Admin Address'
        )
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You need admin privileges to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def generate_booking_number():
    letters = string.ascii_uppercase
    digits = string.digits
    return ''.join(random.choice(letters + digits) for i in range(8))

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = User.query.filter_by(email=email).first()
        
        if user is None or not user.check_password(password):
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))
        
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('user_dashboard' if user.role == 'user' else 'admin_dashboard')
        
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Sign In')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email, phone=phone, address=address)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html', title='Register')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Basic routes
@app.route('/')
def index():
    parking_lots = ParkingLot.query.filter_by(is_active=True).limit(5).all()
    return render_template('index.html', parking_lots=parking_lots)

@app.route('/about')
def about():
    return render_template('about.html', title='About Us')

@app.route('/contact')
def contact():
    return render_template('contact.html', title='Contact Us')

# User routes
@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    active_bookings = Booking.query.filter_by(
        user_id=current_user.id, 
        status='active'
    ).order_by(Booking.start_time.desc()).limit(5).all()
    
    recent_bookings = Booking.query.filter_by(
        user_id=current_user.id
    ).order_by(Booking.created_at.desc()).limit(10).all()
    
    vehicles = Vehicle.query.filter_by(user_id=current_user.id).all()
    
    return render_template('user/dashboard.html', 
                           title='Dashboard',
                           active_bookings=active_bookings,
                           recent_bookings=recent_bookings,
                           vehicles=vehicles)

@app.route('/user/profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('user_profile'))
    
    return render_template('user/profile.html', title='My Profile')

@app.route('/user/vehicles')
@login_required
def user_vehicles():
    vehicles = Vehicle.query.filter_by(user_id=current_user.id).all()
    return render_template('user/vehicles.html', title='My Vehicles', vehicles=vehicles)

@app.route('/user/vehicles/add', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    if request.method == 'POST':
        vehicle_number = request.form.get('vehicle_number')
        vehicle_type = request.form.get('vehicle_type')
        model = request.form.get('model')
        
        # Check if vehicle already exists
        if Vehicle.query.filter_by(vehicle_number=vehicle_number).first():
            flash('Vehicle with this number already exists', 'danger')
            return redirect(url_for('add_vehicle'))
        
        vehicle = Vehicle(
            user_id=current_user.id,
            vehicle_number=vehicle_number,
            vehicle_type=vehicle_type,
            model=model
        )
        
        db.session.add(vehicle)
        db.session.commit()
        
        flash('Vehicle added successfully', 'success')
        return redirect(url_for('user_vehicles'))
    
    return render_template('user/add_vehicle.html', title='Add Vehicle')

@app.route('/user/vehicles/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_vehicle(id):
    vehicle = Vehicle.query.get_or_404(id)
    
    if vehicle.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        vehicle.vehicle_number = request.form.get('vehicle_number')
        vehicle.vehicle_type = request.form.get('vehicle_type')
        vehicle.model = request.form.get('model')
        
        db.session.commit()
        flash('Vehicle updated successfully', 'success')
        return redirect(url_for('user_vehicles'))
    
    return render_template('user/edit_vehicle.html', title='Edit Vehicle', vehicle=vehicle)

@app.route('/user/vehicles/<int:id>/delete', methods=['POST'])
@login_required
def delete_vehicle(id):
    vehicle = Vehicle.query.get_or_404(id)
    
    if vehicle.user_id != current_user.id:
        abort(403)
    
    # Check if vehicle has active bookings
    active_bookings = Booking.query.filter_by(
        vehicle_id=vehicle.id,
        status='active'
    ).first()
    
    if active_bookings:
        flash('Cannot delete vehicle with active bookings', 'danger')
        return redirect(url_for('user_vehicles'))
    
    db.session.delete(vehicle)
    db.session.commit()
    
    flash('Vehicle deleted successfully', 'success')
    return redirect(url_for('user_vehicles'))

@app.route('/user/bookings')
@login_required
def user_bookings():
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = app.config['RESULTS_PER_PAGE']
    
    query = Booking.query.filter_by(user_id=current_user.id)
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    bookings = query.order_by(Booking.created_at.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('user/bookings.html', 
                           title='My Bookings', 
                           bookings=bookings,
                           status=status)

@app.route('/user/bookings/<int:id>')
@login_required
def view_booking(id):
    booking = Booking.query.get_or_404(id)
    
    if booking.user_id != current_user.id:
        abort(403)
    
    return render_template('user/view_booking.html', title='Booking Details', booking=booking)

@app.route('/user/book-parking')
@login_required
def book_parking():
    parking_lots = ParkingLot.query.filter_by(is_active=True).all()
    vehicles = Vehicle.query.filter_by(user_id=current_user.id).all()
    
    return render_template('user/book_parking.html', 
                           title='Book Parking',
                           parking_lots=parking_lots,
                           vehicles=vehicles)

@app.route('/api/parking-spaces')
@login_required
def get_parking_spaces():
    lot_id = request.args.get('lot_id', type=int)
    vehicle_type = request.args.get('vehicle_type')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    
    if not all([lot_id, vehicle_type, start_time, end_time]):
        return {'error': 'Missing parameters'}, 400
    
    try:
        start_datetime = datetime.strptime(start_time, '%Y-%m-%dT%H:%M')
        end_datetime = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
    except ValueError:
        return {'error': 'Invalid date format'}, 400
    
    # Get all spaces in the lot that match the vehicle type
    spaces = ParkingSpace.query.filter_by(
        parking_lot_id=lot_id,
        vehicle_type=vehicle_type
    ).all()
    
    # Check which spaces are available during the requested time
    available_spaces = []
    for space in spaces:
        # Check for overlapping bookings
        overlapping_bookings = Booking.query.filter_by(
            parking_space_id=space.id,
            status='active'
        ).filter(
            ((Booking.start_time <= start_datetime) & (Booking.end_time >= start_datetime)) |
            ((Booking.start_time <= end_datetime) & (Booking.end_time >= end_datetime)) |
            ((Booking.start_time >= start_datetime) & (Booking.end_time <= end_datetime))
        ).first()
        
        if not overlapping_bookings:
            available_spaces.append({
                'id': space.id,
                'space_number': space.space_number
            })
    
    return {'spaces': available_spaces}

@app.route('/user/book-parking/confirm', methods=['POST'])
@login_required
def confirm_booking():
    lot_id = request.form.get('parking_lot_id', type=int)
    space_id = request.form.get('parking_space_id', type=int)
    vehicle_id = request.form.get('vehicle_id', type=int)
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    
    if not all([lot_id, space_id, vehicle_id, start_time, end_time]):
        flash('All fields are required', 'danger')
        return redirect(url_for('book_parking'))
    
    try:
        start_datetime = datetime.strptime(start_time, '%Y-%m-%dT%H:%M')
        end_datetime = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(url_for('book_parking'))
    
    # Validate that start time is before end time
    if start_datetime >= end_datetime:
        flash('End time must be after start time', 'danger')
        return redirect(url_for('book_parking'))
    
    # Validate that start time is not in the past
    if start_datetime < datetime.now():
        flash('Start time cannot be in the past', 'danger')
        return redirect(url_for('book_parking'))
    
    # Get the parking lot and space
    parking_lot = ParkingLot.query.get_or_404(lot_id)
    parking_space = ParkingSpace.query.get_or_404(space_id)
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    
    # Verify the vehicle belongs to the user
    if vehicle.user_id != current_user.id:
        abort(403)
    
    # Calculate total amount
    duration_hours = (end_datetime - start_datetime).total_seconds() / 3600
    total_amount = parking_lot.hourly_rate * duration_hours
    
    # Create booking
    booking = Booking(
        user_id=current_user.id,
        vehicle_id=vehicle_id,
        parking_space_id=space_id,
        booking_number=generate_booking_number(),
        start_time=start_datetime,
        end_time=end_datetime,
        total_amount=total_amount,
        status='active',
        payment_status='paid'  # In a real scenario, you'd handle payment first
    )
    
    # Create payment record
    payment = Payment(
        booking=booking,
        payment_method='credit_card',  # Placeholder
        amount=total_amount,
        transaction_id=f"TRANS-{generate_booking_number()}",
        status='completed'  # In a real scenario, this would be set after payment confirmation
    )
    
    db.session.add(booking)
    db.session.add(payment)
    db.session.commit()
    
    flash('Booking confirmed successfully', 'success')
    return redirect(url_for('view_booking', id=booking.id))

# Admin routes
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Get summary statistics
    total_parking_lots = ParkingLot.query.count()
    total_spaces = ParkingSpace.query.count()
    occupied_spaces = ParkingSpace.query.filter_by(is_occupied=True).count()
    active_bookings = Booking.query.filter_by(status='active').count()
    total_users = User.query.filter_by(role='user').count()
    
    # Get recent bookings
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                           title='Admin Dashboard',
                           total_parking_lots=total_parking_lots,
                           total_spaces=total_spaces,
                           occupied_spaces=occupied_spaces,
                           active_bookings=active_bookings,
                           total_users=total_users,
                           recent_bookings=recent_bookings)

@app.route('/admin/parking-lots')
@login_required
@admin_required
def admin_parking_lots():
    parking_lots = ParkingLot.query.all()
    return render_template('admin/parking_lots.html', title='Manage Parking Lots', parking_lots=parking_lots)

@app.route('/admin/parking-lots/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_parking_lot():
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        pin_code = request.form.get('pin_code')
        total_spaces = request.form.get('total_spaces', type=int)
        hourly_rate = request.form.get('hourly_rate', type=float)
        contact_number = request.form.get('contact_number')
        description = request.form.get('description')
        
        parking_lot = ParkingLot(
            name=name,
            address=address,
            pin_code=pin_code,
            total_spaces=total_spaces,
            hourly_rate=hourly_rate,
            contact_number=contact_number,
            description=description
        )
        
        db.session.add(parking_lot)
        db.session.commit()
        
        # Create parking spaces
        for i in range(1, total_spaces + 1):
            space = ParkingSpace(
                space_number=f"A-{i:03d}",
                parking_lot_id=parking_lot.id,
                vehicle_type='car' if i <= total_spaces * 0.8 else 'bike'  # 80% cars, 20% bikes
            )
            db.session.add(space)
        
        db.session.commit()
        
        flash('Parking lot added successfully', 'success')
        return redirect(url_for('admin_parking_lots'))
    
    return render_template('admin/add_parking_lot.html', title='Add Parking Lot')

@app.route('/admin/parking-lots/<int:id>')
@login_required
@admin_required
def view_parking_lot(id):
    parking_lot = ParkingLot.query.get_or_404(id)
    spaces = ParkingSpace.query.filter_by(parking_lot_id=id).all()
    
    # Count occupied spaces
    occupied_spaces = sum(1 for space in spaces if space.is_occupied)
    
    # Get active bookings for this parking lot
    active_bookings = Booking.query.join(ParkingSpace).filter(
        ParkingSpace.parking_lot_id == id,
        Booking.status == 'active'
    ).all()
    
    return render_template('admin/view_parking_lot.html',
                           title=f'Parking Lot: {parking_lot.name}',
                           parking_lot=parking_lot,
                           spaces=spaces,
                           occupied_spaces=occupied_spaces,
                           active_bookings=active_bookings)

@app.route('/admin/parking-lots/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_parking_lot(id):
    parking_lot = ParkingLot.query.get_or_404(id)
    
    if request.method == 'POST':
        parking_lot.name = request.form.get('name')
        parking_lot.address = request.form.get('address')
        parking_lot.pin_code = request.form.get('pin_code')
        parking_lot.hourly_rate = request.form.get('hourly_rate', type=float)
        parking_lot.contact_number = request.form.get('contact_number')
        parking_lot.description = request.form.get('description')
        parking_lot.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash('Parking lot updated successfully', 'success')
        return redirect(url_for('admin_parking_lots'))
    
    return render_template('admin/edit_parking_lot.html', title='Edit Parking Lot', parking_lot=parking_lot)

@app.route('/admin/bookings')
@login_required
@admin_required
def admin_bookings():
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = app.config['RESULTS_PER_PAGE']
    
    query = Booking.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    bookings = query.order_by(Booking.created_at.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('admin/bookings.html', 
                           title='All Bookings', 
                           bookings=bookings,
                           status=status)

@app.route('/admin/bookings/<int:id>')
@login_required
@admin_required
def admin_view_booking(id):
    booking = Booking.query.get_or_404(id)
    return render_template('admin/view_booking.html', title='Booking Details', booking=booking)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.filter_by(role='user').all()
    return render_template('admin/users.html', title='Manage Users', users=users)

@app.route('/admin/reports/occupancy')
@login_required
@admin_required
def occupancy_report():
    parking_lots = ParkingLot.query.all()
    
    # Prepare data for the chart
    data = []
    for lot in parking_lots:
        total = ParkingSpace.query.filter_by(parking_lot_id=lot.id).count()
        occupied = ParkingSpace.query.filter_by(parking_lot_id=lot.id, is_occupied=True).count()
        data.append({
            'name': lot.name,
            'total': total,
            'occupied': occupied,
            'available': total - occupied,
            'occupancy_rate': round(occupied / total * 100, 2) if total > 0 else 0
        })
    
    return render_template('admin/reports/occupancy.html', 
                           title='Occupancy Report', 
                           parking_lots=data)

@app.route('/admin/reports/revenue')
@login_required
@admin_required
def revenue_report():
    # Get date range for the report
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days by default
    
    # Query for completed bookings in the date range
    bookings = Booking.query.filter(
        Booking.status.in_(['completed', 'active']),
        Booking.payment_status == 'paid',
        Booking.created_at.between(start_date, end_date)
    ).all()
    
    # Calculate total revenue
    total_revenue = sum(booking.total_amount for booking in bookings)
    
    # Group by parking lot
    revenue_by_lot = {}
    for booking in bookings:
        lot_id = booking.space.parking_lot_id
        lot_name = booking.space.parking_lot.name
        if lot_id not in revenue_by_lot:
            revenue_by_lot[lot_id] = {'name': lot_name, 'revenue': 0, 'bookings': 0}
        
        revenue_by_lot[lot_id]['revenue'] += booking.total_amount
        revenue_by_lot[lot_id]['bookings'] += 1
    
    return render_template('admin/reports/revenue.html',
                           title='Revenue Report',
                           total_revenue=total_revenue,
                           revenue_by_lot=revenue_by_lot.values(),
                           start_date=start_date,
                           end_date=end_date)

# Additional utility routes
@app.route('/api/parking-lot/<int:id>/details')
def get_parking_lot_details(id):
    parking_lot = ParkingLot.query.get_or_404(id)
    return {
        'id': parking_lot.id,
        'name': parking_lot.name,
        'address': parking_lot.address,
        'hourly_rate': parking_lot.hourly_rate,
        'total_spaces': parking_lot.total_spaces,
        'available_spaces': parking_lot.available_spaces_count()
    }

@app.route('/search-parking')
def search_parking():
    query = request.args.get('query', '')
    pin_code = request.args.get('pin_code', '')
    
    parking_lots = ParkingLot.query.filter_by(is_active=True)
    
    if query:
        parking_lots = parking_lots.filter(ParkingLot.name.ilike(f'%{query}%') | 
                                          ParkingLot.address.ilike(f'%{query}%'))
    
    if pin_code:
        parking_lots = parking_lots.filter(ParkingLot.pin_code == pin_code)
    
    parking_lots = parking_lots.all()
    
    return render_template('search_results.html', 
                           title='Search Results',
                           parking_lots=parking_lots,
                           query=query, 
                           pin_code=pin_code)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)
