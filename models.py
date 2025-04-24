from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), default='user')  # 'user' or 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bookings = db.relationship('Booking', backref='user', lazy=True)
    vehicles = db.relationship('Vehicle', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    total_spaces = db.Column(db.Integer, nullable=False)
    hourly_rate = db.Column(db.Float, nullable=False)
    contact_number = db.Column(db.String(20), nullable=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    spaces = db.relationship('ParkingSpace', backref='parking_lot', lazy=True)
    
    def available_spaces_count(self):
        return ParkingSpace.query.filter_by(parking_lot_id=self.id, is_occupied=False).count()

class ParkingSpace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    space_number = db.Column(db.String(10), nullable=False)
    parking_lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    is_occupied = db.Column(db.Boolean, default=False)
    is_reserved = db.Column(db.Boolean, default=False)
    vehicle_type = db.Column(db.String(20), default='car')  # car, bike, etc.
    bookings = db.relationship('Booking', backref='space', lazy=True)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=False, unique=True)
    vehicle_type = db.Column(db.String(20), nullable=False)  # car, bike, etc.
    model = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bookings = db.relationship('Booking', backref='vehicle', lazy=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    parking_space_id = db.Column(db.Integer, db.ForeignKey('parking_space.id'), nullable=False)
    booking_number = db.Column(db.String(20), nullable=False, unique=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, active, completed, cancelled
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, refunded
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def duration_hours(self):
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 3600
    
    @property
    def is_active(self):
        now = datetime.utcnow()
        return self.start_time <= now <= self.end_time and self.status == 'active'

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_id = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    booking = db.relationship('Booking', backref='payment_info', uselist=False)
