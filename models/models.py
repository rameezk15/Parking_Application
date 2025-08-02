from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(32), unique = True, nullable = False)
    passhash = db.Column(db.String(64), nullable = False)
    name = db.Column(db.String(64), nullable = True)
    city = db.Column(db.String(50), nullable = False)
    pincode = db.Column(db.String(6), nullable = False)
    isadmin = db.Column(db.Boolean, nullable = False, default = False)
    deleted_user = db.Column(db.Boolean, nullable = False, default = False)
    reserve_parking_lot = db.relationship('ReserveParkingLot', backref = 'user', lazy = True)

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    parking_name = db.Column(db.String(64), unique = True, nullable = False)
    address =  db.Column(db.String(70), nullable = False)
    city = db.Column(db.String(50), nullable = False)
    pincode = db.Column(db.String(6), nullable = False)
    price = db.Column(db.Float, nullable = False)
    number_of_spots = db.Column(db.Integer, nullable = False)
    deleted_lot = db.Column(db.Boolean, nullable = False, default = False)
    parking_spot = db.relationship('ParkingSpot', backref= 'parking_lot', lazy = True, cascade='all, delete')

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    lot_id = db.Column(db.Integer, db.ForeignKey(ParkingLot.id), nullable = False)
    spot_number = db.Column(db.String(6), nullable = False)
    occupied = db.Column(db.Boolean, nullable = False, default = False)
    deleted_spot = db.Column(db.Boolean, nullable = False, default = False)
    reserve_parking_lot = db.relationship('ReserveParkingLot', backref= 'parking_spot', lazy = True)

     # Method to get the current user occupying the spot
    def spot_detail(self,input):
        # Find the most recent reservation where the spot is still occupied
        latest_reservation = ReserveParkingLot.query.filter_by(spot_id=self.id, is_release=False).order_by(ReserveParkingLot.in_time.desc()).first()
        if input == 'user_name':
            return latest_reservation.user.name
        if input == 'vehicle_number':
            return latest_reservation.vehicle_number
        if input == 'in_time':
            return latest_reservation.in_time
        return None

class ReserveParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable = False)
    spot_id = db.Column(db.Integer, db.ForeignKey(ParkingSpot.id), nullable = False)
    in_time = db.Column(db.DateTime , nullable = False)
    out_time = db.Column(db.DateTime , nullable = True)
    hours = db.Column(db.Integer , nullable = True)
    total_cost = db.Column(db.Float, nullable = True)
    vehicle_number = db.Column(db.String(32), nullable = False)
    is_release = db.Column(db.Boolean, nullable = False, default = False)