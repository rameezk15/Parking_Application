from flask import render_template, request, flash, redirect, url_for, session
from models.models import *
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from sqlalchemy import func, case
from datetime import datetime
from math import ceil
from collections import defaultdict
from sqlalchemy import extract, or_, cast, String
from sqlalchemy.orm import joinedload

def init_routes(app):
    # <------------------------Landing Page----------------------->
    @app.route('/')
    def base():
        return render_template('landing_page.html')
    
    # <-----------------Authentication Decorator------------------>
    def login_auth(func):
        @wraps(func)
        def approve_auth(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to continue')
                return redirect(url_for('login'))
            return func(*args, **kwargs)
        return approve_auth
    
    # <--------------------------------------------------------------------------------CRUD Operations-------------------------------------------------------------------------------->
    
    # <----------------------------------------------------------Create---------------------------------------------------------->

    # <-------------------Register The New User------------------->
    @app.route('/register')
    def register():
        return render_template('register.html')

    @app.route('/register', methods = ['POST'])
    def register_post():
        # Get the user details filled in the Form
        name = request.form.get('name').title()
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        city = request.form.get('city').title()
        pincode = request.form.get('pincode')
        # Check all details is given
        if not name or not username or not password or not confirm_password or not city or not pincode:
            flash('Please fill out all fields')
            return redirect(url_for('register'))
        # Check password and confirm_password is same
        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))
        # Check if given username is already present to maintain the uniqueness of username
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        # Save password in hash form in database for security
        passhash = generate_password_hash(password)
        new_user = User(username=username, passhash=passhash, name=name, city=city, pincode=pincode)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successfully completed')
        flash('Please log in to continue!')
        return redirect(url_for('login'))

    # <------------------Create New Parking Lot------------------->
    @app.route('/create_lot', methods=['POST'])
    @login_auth
    def create_lot():
        # Get detials fill in From
        parking_name = request.form.get('parking_name').title()
        address = request.form.get('address').title()
        city = request.form.get('city').title()
        pincode = request.form.get('pincode')
        price = request.form.get('price')
        number_of_spots = request.form.get('number_of_spots')
        if not parking_name or not address or not city or not pincode or not price or not number_of_spots:
            flash('Please fill out all fields')
            return redirect(url_for('home'))
        try:
            # Create ParkingLot
            new_lot = ParkingLot(
                parking_name=parking_name,
                address=address,
                city=city,
                pincode=pincode,
                price=float(price),
                number_of_spots= int(number_of_spots)
            )
            db.session.add(new_lot)
            db.session.flush()  # Flush to ensure the new lot is added in ParkingLot table before adding the spots in ParkingSpot table 
            # Create ParkingSpot
            new_spots = [ParkingSpot(lot_id = new_lot.id, spot_number ='P{:03d}'.format(i+1), occupied = False) for i in range(int(number_of_spots))]
            db.session.add_all(new_spots)
            db.session.commit()
            flash(f"Parking lot '{parking_name}' added successfully")
            return redirect(url_for('home'))
        # Rollback the changes if process failed in middle
        except Exception as e:
            db.session.rollback()
            flash(f"The parking lot name '{parking_name}' is already in use. Please choose a different name.")
            return redirect(url_for('home'))
    
    # <-----------------Genrate New Active Booking---------------->
    @app.route('/active_booking_post/<int:lot_id>', methods=['POST'])
    @login_auth
    def active_booking_post(lot_id):
        try:
            # Get the user booking details from pre-filled Form in booking_detail page
            user_id = session['user_id']
            spot_number = request.form.get('spot_number')
            in_time_str = request.form.get('in_time')  # Gets string from form
            in_time = datetime.strptime(in_time_str, '%Y-%m-%d %H:%M:%S') # Convert in_time string into datetime
            vehicle_number = request.form.get('vehicle_number')
            spot = ParkingSpot.query.filter_by(lot_id=lot_id, spot_number=spot_number).first()
            spot_id = spot.id
            # Change occupied status to true
            spot.occupied = True
            db.session.flush()  # Flush to ensure the spot occupied status is updated before updating the reservation table 
            # Updating the ReserveParkingLot Table
            new_reservation = ReserveParkingLot(user_id=user_id, spot_id=spot_id, in_time= in_time, vehicle_number=vehicle_number)
            db.session.add(new_reservation)
            db.session.commit()
            flash('Spot reserve successfully')
            return redirect(url_for('active_booking'))
        # Rollback the changes if process failed in middle
        except Exception as e:
            db.session.rollback()
            flash(f"Error reserving a parking spot: {spot_number}")
            return redirect(url_for('active_booking'))
    
    # <-----------------------------------------------------------Read----------------------------------------------------------->
    
    # <-----------Home Page To See Parking Lots Details----------->
    @app.route('/home')
    @login_auth
    def home():
        # Get the Search Query
        search_query = request.args.get("q", "").strip()
        # Fetch all parking lots form database (exclude soft deleted lots)
        lots_query = ParkingLot.query.filter_by(deleted_lot=False)
        # If search is perform
        if search_query:
            lots_query = lots_query.filter(
                or_(
                    ParkingLot.parking_name.ilike(f"%{search_query}%"),
                    ParkingLot.city.ilike(f"%{search_query}%"),
                    ParkingLot.address.ilike(f"%{search_query}%"),
                    cast(ParkingLot.pincode, String).ilike(f"%{search_query}%")
                )
            )
        # Fetch all the lots
        lots = lots_query.all()
        # If Search Result Not Found
        if search_query and not(lots):
            flash(f'No result found for {search_query}!')
        # Group occupied & available spot lot wise (exclude soft deleted spots)
        spot_status = db.session.query(
            ParkingSpot.lot_id,
            func.sum(
                case(
                    (((ParkingSpot.occupied == True) & (ParkingSpot.deleted_spot == False)), 1),
                    else_=0
                )
            ).label('occupied_count'),
            func.sum(
                case(
                    (((ParkingSpot.occupied == False) & (ParkingSpot.deleted_spot == False)), 1),
                    else_=0
                )
            ).label('available_count')
        ).group_by(ParkingSpot.lot_id).all()
        # Convert to dict for easy lookup
        spot_status_dict = {
            lot_id: {
                'number_of_spots': occupied+available_count,
                'occupied': occupied,
                'available_count': available_count
            } for lot_id, occupied, available_count in spot_status
        }
        return render_template('index.html', lots=lots, spot_status=spot_status_dict, search_action=url_for('home'))
    
    # <----------------Login Authentication---------------->
    @app.route('/login')
    def login():
        return render_template('login.html')
    
    @app.route('/login', methods = ['POST'])
    def login_post():
        username = request.form.get('username')
        password = request.form.get('password')
        # Check for username & password given
        if not username or not password:
            flash('Please fill out all fields')
            return redirect(url_for('login'))
        # Get the user detail
        user = User.query.filter_by(username=username).first()
        # Check this username & password combination avilable in database
        if not user or not check_password_hash(user.passhash, password):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        # Check if user is soft deleted from database.
        if user.deleted_user:
            flash('User has been deleted. Contact Admin')
            return redirect(url_for('login'))
        # Above condition satisfied then login the user and save the user_id in session for authentication 
        flash('Login successfully')
        flash('Welcome back, {}!'.format(user.name))
        session['user_id'] = user.id
        session['isadmin'] = user.isadmin
        return redirect(url_for('home'))
    
    @app.route('/logout')
    def logout():
        # Remove the user_id from the seesion to logout
        session.pop('user_id', None)
        flash('Logged out successfully')
        flash('See you next time!')
        return redirect(url_for('login'))
    
    # <-------------------------Profile--------------------------->
    @app.route('/profile')
    @login_auth
    def profile():
        # Fetch the user detail from database
        user = User.query.get(session['user_id'])
        return render_template('profile.html', user=user)
    
    # <------------------------Show Spots------------------------->
    @app.route('/show_spot/<int:lot_id>')
    @login_auth
    def show_spot(lot_id):
        # Fetch parking lot detail from database
        lot = ParkingLot.query.get(lot_id)
        lot_price = f'{lot.price:.2f}'
        lot_name = lot.parking_name
        # Fetch all the realated to parking lot spots from database (exclude soft deleted spots)
        spots = ParkingSpot.query.filter_by(lot_id=lot_id, deleted_spot=False).all()
        # Calculate the number of occupied_count and available_count
        occupied_count = sum(1 for spot in spots if spot.occupied)
        available_count = len(spots) - occupied_count
        # Convert to dict for easy lookup
        spot_info ={
            'lot_id' : lot_id,
            'lot_name' : lot_name,
            'lot_price' :lot_price,
            'spots' : spots,
            'occupied_count' : occupied_count,
            'available_count' : available_count
        }
        return render_template('show_spot.html', **spot_info)
    
    # <-------------------Show Booking Details-------------------->
    @app.route('/booking_detail/<int:id>/<string:is_booking>')
    @login_auth
    def booking_detail(id,is_booking):
        # Check booking stage is_booking true when booking the spot & is_booking false when relasing a spot
        is_booking = is_booking.lower() == 'true'
        # Fetch username details form database
        user = User.query.filter_by(id = session['user_id']).first()
        username = user.name
        # Fetch the booking details form database
        if is_booking:
            # Fetch spot detail when booking the spot & Calculate the in_time. Here `id` use as `lot_id`
            spot = ParkingSpot.query.filter_by(lot_id=id, occupied=False, deleted_spot = False).order_by(ParkingSpot.spot_number.asc()).first()
            in_time = datetime.now().replace(microsecond=0) 
        else:
            # Fetch spot detail when releasing it. Here's `id` use as `booking_id`
            booking = ReserveParkingLot.query.filter_by(id=id).first()
            spot = booking.parking_spot
            vehicle_number = booking.vehicle_number
            in_time = booking.in_time
            out_time = datetime.now().replace(microsecond=0)
            price = spot.parking_lot.price
            in_time = booking.in_time
            time_diff = out_time - in_time
            hours = ceil(time_diff.total_seconds() / 3600)  # Convert to hours and round up
            total_cost = price * hours
        spot_number = spot.spot_number
        parking_name = spot.parking_lot.parking_name
        address = f"{spot.parking_lot.address}, {spot.parking_lot.city}, Pin Code = {spot.parking_lot.pincode}"
        price = f"{spot.parking_lot.price:.2f}"
        # Convert to dict for easy lookup
        booking_info = {
            'id' : id,
            'username': username,
            'parking_name': parking_name,
            'address' : address,
            'spot_number': spot_number,
            'in_time': in_time,
            'price': price,
            'is_booking': is_booking,
            'hours': hours if not is_booking else None,
            'vehicle_number': vehicle_number if not is_booking else None,
            'total_cost': total_cost if not is_booking else None,
            'out_time' : out_time if not is_booking else None
        }
        return render_template('booking_detail.html', **booking_info)

    # <--------------------Show Active Booking-------------------->
    @app.route('/active_booking')
    @login_auth
    def active_booking():
        empty = False
        active_bookings = ReserveParkingLot.query \
            .join(User) \
            .join(ParkingSpot) \
            .join(ParkingLot, ParkingSpot.lot_id == ParkingLot.id) \
            .options(
                joinedload(ReserveParkingLot.user),
                joinedload(ReserveParkingLot.parking_spot).joinedload(ParkingSpot.parking_lot)
            ) \
            .filter(ReserveParkingLot.is_release == False)
        # Filter by logged-in user if not admin
        if not session['isadmin']:
            active_bookings = active_bookings.filter(ReserveParkingLot.user_id == session['user_id'])
        # Get the Search Query
        search_query = request.args.get("q", "").strip()
        # If search is perform
        if search_query:
            active_bookings = active_bookings.filter(
                or_(
                    ReserveParkingLot.vehicle_number.ilike(f"{search_query}%"),
                    User.username.ilike(f"%{search_query}%"),
                    ParkingLot.parking_name.ilike(f"%{search_query}%"),
                    ParkingLot.city.ilike(f"%{search_query}%"),
                    ParkingLot.address.ilike(f"%{search_query}%"),
                    cast(ParkingSpot.spot_number, String).ilike(f"%{search_query}%"),
                    cast(ParkingLot.pincode, String).ilike(f"%{search_query}%")
                )
            )
        # Fetch all the lots
        active_bookings = active_bookings.all()
        # If Search Result Not Found
        if search_query and not(active_bookings):
            flash(f'No result found for {search_query}!')
        # Use this to handel the situation when query result is None
        if not active_bookings:
            active_bookings = [{'is_release': False}]
            empty = True
        return render_template('bookings.html', bookings=active_bookings, empty = empty, search_action=url_for('active_booking'))
    
    # <--------------------Show Booking History------------------->
    @app.route('/booking_history')
    @login_auth
    def booking_history():
        empty = False
        # Fetch all booking history
        bookings_query = ReserveParkingLot.query \
            .join(User) \
            .join(ParkingSpot) \
            .join(ParkingLot, ParkingSpot.lot_id == ParkingLot.id) \
            .options(
                joinedload(ReserveParkingLot.user),
                joinedload(ReserveParkingLot.parking_spot).joinedload(ParkingSpot.parking_lot)
            ) \
            .filter(ReserveParkingLot.is_release == True)
        # Filter by logged-in user if not admin
        if not session['isadmin']:
            bookings_query = bookings_query.filter(ReserveParkingLot.user_id == session['user_id'])
        # Get the Search Query
        search_query = request.args.get("q", "").strip()
        # If search is perform
        if search_query:
            bookings_query = bookings_query.filter(
                or_(
                    ReserveParkingLot.vehicle_number.ilike(f"{search_query}%"),
                    User.username.ilike(f"%{search_query}%"),
                    ParkingLot.parking_name.ilike(f"%{search_query}%"),
                    ParkingLot.city.ilike(f"%{search_query}%"),
                    ParkingLot.address.ilike(f"%{search_query}%"),
                    cast(ParkingSpot.spot_number, String).ilike(f"%{search_query}%"),
                    cast(ParkingLot.pincode, String).ilike(f"%{search_query}%")
                )
            )
        # Fetch all the lots
        bookings = bookings_query.all()
        # If Search Result Not Found
        if search_query and not(bookings):
            flash(f'No result found for {search_query}!')
        # Use this to handel the situation when query result is None
        if not bookings:
            bookings = [{'is_release': True}]
            empty = True
        return render_template('bookings.html', bookings=bookings, empty=empty, search_action=url_for('booking_history'))
    
    # <-------------Show User List on Admin Dashboard------------->
    @app.route('/users_list')
    @login_auth
    def users_list():
        # Get the Search Query
        search_query = request.args.get("q", "").strip()
        # Fetch user details from database (exclude soft deleted users)
        users_query = User.query.filter_by(isadmin = not(session['isadmin']), deleted_user = False)
        # If search is perform
        if search_query:
            users_query = users_query.filter(
                or_(
                    User.username.ilike(f"%{search_query}%"),
                    User.name.ilike(f"%{search_query}%"),
                    User.city.ilike(f"%{search_query}%"),
                    cast(User.pincode, String).ilike(f"%{search_query}%")
                )
            )
        # Fetch all the users
        users = users_query.all()
        # If Search Result Not Found
        if search_query and not(users):
            flash(f'No result found for {search_query}!')
        # Map user with its booking status
        booking_stats = {user.id: {
            'active': ReserveParkingLot.query.filter_by(user_id=user.id, is_release=False).count(),
            'complete': ReserveParkingLot.query.filter_by(user_id=user.id, is_release=True).count()
            } for user in users
        }
        return render_template('users_list.html', users= users, booking_stats=booking_stats, search_action=url_for('users_list'))
    
    # <-------------Show Dashboard Charts------------->
    @app.route('/dashboard')
    def dashboard():
        if session['isadmin']:
            # Group total complete_booking & active_booking lot wise
            booking_status_lot_wise = db.session.query(
                ParkingLot.parking_name,
                func.sum(case((ReserveParkingLot.is_release == True, 1), else_=0)).label('complete_booking'),
                func.sum(case((ReserveParkingLot.is_release == False, 1), else_=0)).label('active_booking')
            ).join(ParkingSpot, ParkingSpot.id == ReserveParkingLot.spot_id)\
            .join(ParkingLot, ParkingLot.id == ParkingSpot.lot_id)\
            .group_by(ParkingLot.parking_name).all()
            # Group total monthly earning lot wise
            lot_monthly_collection = db.session.query(
                ParkingLot.parking_name,
                extract('month', ReserveParkingLot.out_time).label('month'),
                func.sum(ReserveParkingLot.total_cost).label('monthly_earning')
            ).join(ParkingSpot, ParkingSpot.id == ReserveParkingLot.spot_id)\
            .join(ParkingLot, ParkingLot.id == ParkingSpot.lot_id)\
            .filter(ReserveParkingLot.is_release == True)\
            .group_by(ParkingLot.parking_name, 'month')\
            .order_by('month').all()
            # Group total complete_booking & active_booking user wise
            booking_status_user_wise = db.session.query(
                User.username,
                func.sum(case((ReserveParkingLot.is_release == True, 1), else_=0)).label('complete_booking'),
                func.sum(case((ReserveParkingLot.is_release == False, 1), else_=0)).label('active_booking')
            ).join(User, User.id == ReserveParkingLot.user_id)\
            .group_by(User.username).all()
            # Group total monthly spends user wise
            user_monthly_spends = db.session.query(
                User.username,
                extract('month', ReserveParkingLot.in_time).label('month'),
                func.sum(ReserveParkingLot.total_cost).label('monthly_earning')
            ).join(User, User.id == ReserveParkingLot.user_id)\
            .filter(ReserveParkingLot.is_release == True)\
            .group_by(User.username, 'month')\
            .order_by('month').all()
        else:
            # Total complete_booking & active_booking lot wise for specific user
            booking_status_lot_wise = db.session.query(
                ParkingLot.parking_name,
                func.sum(case((ReserveParkingLot.is_release == True, 1), else_=0)).label('complete_booking'),
                func.sum(case((ReserveParkingLot.is_release == False, 1), else_=0)).label('active_booking')
            ).join(ParkingSpot, ParkingSpot.id == ReserveParkingLot.spot_id)\
            .join(ParkingLot, ParkingLot.id == ParkingSpot.lot_id)\
            .join(User, User.id == ReserveParkingLot.user_id)\
            .filter(ReserveParkingLot.user_id == session['user_id'])\
            .group_by(ParkingLot.parking_name).all()
            # Total monthly spends lot wise for specific user
            lot_monthly_collection = db.session.query(
                ParkingLot.parking_name,
                extract('month', ReserveParkingLot.out_time).label('month'),
                func.sum(ReserveParkingLot.total_cost).label('monthly_earning')
            ).join(ParkingSpot, ParkingSpot.id == ReserveParkingLot.spot_id)\
            .join(ParkingLot, ParkingLot.id == ParkingSpot.lot_id)\
            .filter(ReserveParkingLot.is_release == True, ReserveParkingLot.user_id == session['user_id'])\
            .group_by(ParkingLot.parking_name, 'month')\
            .order_by('month').all()
            # Total complete_booking & active_booking for specific user
            booking_status_user_wise = db.session.query(
                User.username,
                func.sum(case((ReserveParkingLot.is_release == True, 1), else_=0)).label('complete_booking'),
                func.sum(case((ReserveParkingLot.is_release == False, 1), else_=0)).label('active_booking')
            ).join(User, User.id == ReserveParkingLot.user_id)\
            .filter(ReserveParkingLot.user_id == session['user_id'])
            # Total monthly spends for specific user
            user_monthly_spends = db.session.query(
                User.username,
                extract('month', ReserveParkingLot.in_time).label('month'),
                func.sum(ReserveParkingLot.total_cost).label('monthly_earning')
            ).join(User, User.id == ReserveParkingLot.user_id)\
            .filter(ReserveParkingLot.is_release == True, ReserveParkingLot.user_id == session['user_id'])\
            .order_by('month').all()

        # Lot-wise data
        lot_booking_dict = defaultdict(lambda: {'complete': 0, 'active': 0})
        for lot, complete, active in booking_status_lot_wise:
            lot_booking_dict[lot]['complete'] = complete
            lot_booking_dict[lot]['active'] = active

        lot_monthly_dict = defaultdict(lambda: [0]*12)
        for lot, month, earning in lot_monthly_collection:
            if month:
                lot_monthly_dict[lot][int(month)-1] = earning
        
        # User-wise data
        user_booking_dict = defaultdict(lambda: {'complete': 0, 'active': 0})
        for user, complete, active in booking_status_user_wise:
            user_booking_dict[user]['complete'] = complete
            user_booking_dict[user]['active'] = active

        user_monthly_dict = defaultdict(lambda: [0]*12)
        for user, month, earning in user_monthly_spends:
            if month:
                user_monthly_dict[user][int(month)-1] = earning

        # Pass all to template
        return render_template("dashboard.html",
            lot_booking_dict=lot_booking_dict,
            lot_monthly_dict=lot_monthly_dict,
            user_booking_dict=user_booking_dict,
            user_monthly_dict=user_monthly_dict
        )

    # <----------------------------------------------------------Update---------------------------------------------------------->
    
    # <-----------------------Profile Update---------------------->
    @app.route('/profile', methods = ['POST'])
    @login_auth
    def profile_update():
        # Get the user details filled in the Form
        username = request.form.get('username')
        name = request.form.get('name').title()
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        city = request.form.get('city').title()
        pincode = request.form.get('pincode')
        user = User.query.get(session['user_id'])
        # Check update happened
        if username == user.username and name == user.name and not new_password and city == user.city and pincode == user.pincode:
            flash('No changes made')
            return redirect(url_for('profile'))
        # Check for user password change, if yes then update
        if old_password and new_password:
            if not check_password_hash(user.passhash, old_password):
                flash('Invalid old password')
                return redirect(url_for('profile'))
            if len(new_password) < 5 or old_password == new_password:
                flash('New password must be at least 5 characters long and different from old password')
                return redirect(url_for('profile'))
            passhash = generate_password_hash(new_password)
            user.passhash = passhash
        # Check for username change, if yes then update
        if username != user.username:
            if User.query.filter_by(username=username).first():
                flash('Username already exists')
                return redirect(url_for('profile'))
            user.username = username
        # Check for name change, if yes then update
        if name != user.name:
            user.name = name
        # Check for city change, if yes then update
        if city != user.city:
            user.city = city
        # Check for pincode change, if yes then update
        if pincode != user.pincode:
            user.pincode = pincode
        db.session.commit()
        flash('Profile updated successfully')
        return redirect(url_for('profile'))
    
    # <-------------------------Lot Update------------------------>
    @app.route('/update_lot/<int:lot_id>', methods=['POST'])
    @login_auth
    def update_lot(lot_id):
        try:
            # Fetch lot details form database
            occupied_spot_count = ParkingSpot.query.filter_by(lot_id=lot_id, occupied=True).count()
            lot = ParkingLot.query.get(lot_id)
            current_spots_count = lot.number_of_spots
            # Get lot details filled in the Form and update it into the database
            lot.parking_name = request.form.get('parking_name').title()
            lot.address = request.form.get('address').title()
            lot.city = request.form.get('city').title()
            lot.pincode = request.form.get('pincode')
            lot.price = float(request.form.get('price'))
            new_spot_count = int(request.form.get('number_of_spots'))
            # Check that new_spot_count should always greater then occupied_spot_count
            if occupied_spot_count > new_spot_count:
                db.session.rollback()
                flash(f"New spot quantity is less then occupied spot in {lot.parking_name}")
                return redirect(url_for('home'))
            # if above condition satisfied then update the number_of_spots in database otherwise not
            lot.number_of_spots = new_spot_count
            db.session.flush() # Flush to ensure the lot is updated in ParkingLot table before updating the spots in ParkingSpot table 
            # Calculate the difference of new & old spot to decide to dec or inc the spot quantity
            spot_diff = new_spot_count - current_spots_count
            # Check if diff in +ve need to inc the spots
            if spot_diff > 0:
                # First try to reactivate soft-deleted spots
                deactivated_spots = ParkingSpot.query.filter_by(lot_id=lot_id, deleted_spot=True).limit(spot_diff).all()
                for spot in deactivated_spots:
                    spot.deleted_spot = False
                spot_diff -= len(deactivated_spots)
                # If more spots are still needed, create new ones
                if spot_diff > 0:
                    last_spot_number = ParkingSpot.query.filter_by(lot_id=lot_id).count()
                    new_spots = [
                        ParkingSpot(
                            lot_id=lot_id,
                            spot_number='P{:03d}'.format(last_spot_number + i + 1),
                            occupied=False
                        ) for i in range(spot_diff)
                    ]
                    db.session.add_all(new_spots)
            # Check if diff in -ve need to dec the spots
            elif spot_diff < 0:
                # Soft-delete excess unoccupied spots (highest spot numbers first)
                spots_to_remove = ParkingSpot.query.filter_by(lot_id=lot_id, occupied=False, deleted_spot=False).order_by(ParkingSpot.spot_number.desc()).limit(abs(spot_diff)).all()
                for spot in spots_to_remove:
                    spot.deleted_spot = True
            # Commit the changes if all run successfully
            db.session.commit()
            flash('Parking lot updated successfully')
            return redirect(url_for('home'))
        # Rollback the changes if process failed in middle
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating parking lot: {lot.parking_name}")
            return redirect(url_for('home'))
        
    # <-------------------------Release Lot----------------------->
    @app.route('/release_spot/<int:booking_id>', methods=['POST'])
    @login_auth
    def release_spot(booking_id):
        # Get the user booking details from pre-filled Form in booking_detail page
        out_time_str = request.form.get('out_time')
        out_time = datetime.strptime(out_time_str, "%Y-%m-%d %H:%M:%S")
        hours = int(request.form.get('hours'))
        total_cost = float(request.form.get('total_cost'))
        # Update the value in ReserveParkingLot table
        booking = ReserveParkingLot.query.filter_by(id=booking_id).first()
        booking.is_release = True
        booking.parking_spot.occupied = False
        booking.out_time = out_time
        booking.hours = hours
        booking.total_cost = total_cost
        db.session.commit()
        return redirect(url_for('booking_history'))
    
    # <----------------------------------------------------------Delete---------------------------------------------------------->
    
    # <-------------------------Delete Lot------------------------>
    @app.route('/delete_lot/<int:lot_id>', methods=['POST'])
    @login_auth
    def delete_lot(lot_id):
        lot = ParkingLot.query.get(lot_id)
        try:
            # Soft detlete the lot
            lot.deleted_lot = True
            # Soft detlete the each slot in a lot
            for spot in lot.parking_spot:
                if spot.occupied:
                    raise Exception
                spot.deleted_spot = True
            # Commit the changes
            db.session.commit()
            flash(f"Parking lot '{lot.parking_name}' deleted successfully")
        # Rollback the changes if process failed in middle
        except Exception as e:
            db.session.rollback()
            flash(f"Parking lot '{lot.parking_name}' spot is occupied not able to deleted.")
        return redirect(url_for('home'))
    
    # <-------------------------Delete Spot----------------------->
    @app.route('/delete_spot/<int:spot_id>', methods=['POST'])
    @login_auth
    def delete_spot(spot_id):
        try:
            # Fetch spot detail from database
            spot = ParkingSpot.query.get(spot_id)
            spot_number = spot.spot_number
            lot_id = spot.lot_id
            # Soft delete by update deleted_spot to true
            spot.deleted_spot = True
            # Dec the number_of_spots by 1
            spot.parking_lot.number_of_spots -= 1
            db.session.commit()
            flash(f'{spot_number} spot successfully deleted')
            return redirect(url_for('show_spot', lot_id=lot_id))
        # Rollback the changes if process failed in middle
        except Exception as e:
            db.session.rollback()
            flash(f'Error to delete spot: {e}')
            return redirect(url_for('show_spot', lot_id=lot_id))
        
    # <--------------Delete User on Admin Dashboard--------------->
    @app.route('/delete_user/<int:user_id>', methods=['POST'])
    @login_auth
    def delete_user(user_id):
        # Fetch the user from database
        user = User.query.get(user_id)
        try:
            # Check if any reservation is not released
            active_reservations = [r for r in user.reserve_parking_lot if not r.is_release]
            if not active_reservations:
                user.deleted_user = True
                db.session.commit()
                flash(f"User '{user.username}' deleted successfully")
            else:
                flash(f"User '{user.username}' could not be deleted because active reservations exist.")
                return redirect(url_for('users_list'))
        # Rollback the changes if process failed in middle
        except Exception as e:
            db.session.rollback()
            flash(f"Error deleting user {user.username}: {str(e)}")
        return redirect(url_for('users_list'))