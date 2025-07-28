
import streamlit.components.v1 as components
import streamlit as st
import snowflake.snowpark as sp
from snowflake.snowpark import Session
from datetime import datetime, timedelta, time
import re
import uuid
import hashlib
from PIL import Image, ImageOps
import io
import base64
import pandas as pd
##########################################################################################
##########################################################################################
##########################################################################################


##########################################################################################
##########################################################################################

# Initialize Snowflake connection
def get_session():
    return sp.context.get_active_session()

# Role-based access control
ROLE_ACCESS = {
    'admin': ['Home', 'profile', 'customers', 'appointments', 'quotes', 'invoices', 'payments', 'reports', 'analytics', 'admin_tables', 'equipment'],
    'office': ['Home', 'customers', 'appointments', 'equipment'],
    'technician': ['Home', 'profile', 'quotes', 'invoices', 'payments', 'equipment'],
    'driver': ['Home', 'profile', 'driver_tasks']
} ##########################################################################################






##########################################################################################
##########################################################################################
##########################################################################################

# Login page

def login_page():
    st.title("POTOMAC HVAC")
    emp_id = st.text_input("Employee ID")
    password = st.text_input("Password", type='password')
        # Add MFA passcode field if required
    if st.session_state.get('mfa_required', False):
        st.session_state.mfa_passcode = st.text_input("MFA Passcode", type='password')
    
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Login"):
            session = get_session()
            try:
                result = session.sql(f"""
                    SELECT e.*, r.rolename
                    FROM employees e
                    JOIN employee_roles er ON e.employeeid = er.employeeid
                    JOIN roles r ON er.roleid = r.roleid
                    WHERE e.employeeid = '{emp_id}' AND e.password = '{password}'
                """).collect()
                if result:
                    st.session_state.update({
                        'logged_in': True,
                        'user_id': emp_id,
                        'user_name': result[0]['ENAME'],
                        'roles': [row['ROLENAME'] for row in result]
                    })
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            except Exception as e:
                st.error(f"Login error: {str(e)}")
    with col2:
        if st.button("Forgot Password?"):
            st.session_state['show_forgot_password'] = True

    # Show "Forgot Password" section if enabled
    if st.session_state.get('show_forgot_password'):
        forgot_password()

        # Add a "Back to Login" button only in the "Forgot Password" flow
        if st.button("Back to Login"):
            st.session_state['show_forgot_password'] = False
            st.rerun()
##########################################################################################
##########################################################################################
##########################################################################################

# Forgot password functionality
def forgot_password():
    st.subheader("🔒 Forgot Password")
    email = st.text_input("Enter your email address")
    if st.button("Send Reset Link"):
        session = get_session()
        try:
            employee = session.sql(f"""
                SELECT employeeid FROM employees
                WHERE email = '{email}'
            """).collect()
            if employee:
                employee_id = employee[0]['EMPLOYEEID']
                reset_token = str(uuid.uuid4())
                token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
                expires_at = datetime.now() + timedelta(hours=1)
                session.sql(f"""
                    INSERT INTO password_resets
                    (resetid, employeeid, reset_token, expires_at)
                    VALUES (
                        '{str(uuid.uuid4())}',
                        '{employee_id}',
                        '{token_hash}',
                        '{expires_at}'
                    )
                """).collect()
                st.success("Password reset link sent to your email!")
            else:
                st.error("No account found with that email address")
        except Exception as e:
            st.error(f"Error processing request: {str(e)}")
##########################################################################################
##########################################################################################
##########################################################################################

# Reset password functionality
def reset_password(token):
    st.subheader("🔑 Reset Password")
    new_password = st.text_input("New Password", type='password')
    confirm_password = st.text_input("Confirm Password", type='password')
    if st.button("Reset Password"):
        if new_password == confirm_password:
            session = get_session()
            try:
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                reset_record = session.sql(f"""
                    SELECT * FROM password_resets
                    WHERE reset_token = '{token_hash}'
                    AND used = FALSE
                    AND expires_at > CURRENT_TIMESTAMP()
                """).collect()
                if reset_record:
                    employee_id = reset_record[0]['EMPLOYEEID']
                    session.sql(f"""
                        UPDATE employees
                        SET password = '{new_password}'
                        WHERE employeeid = '{employee_id}'
                    """).collect()
                    session.sql(f"""
                        UPDATE password_resets
                        SET used = TRUE
                        WHERE resetid = '{reset_record[0]['RESETID']}'
                    """).collect()
                    st.success("Password reset successfully!")
                    st.session_state.clear()
                    st.rerun()
                else:
                    st.error("Invalid or expired reset token")
            except Exception as e:
                st.error(f"Error resetting password: {str(e)}")
        else:
            st.error("Passwords do not match")
#######################################################################
######################################################################
#############HOME#####################################################

def Home():
    # Establish connection to Snowflake database using existing session
    session = get_session()
    
    # Initialize variables for time tracking with default values
    selected_date = datetime.now().date()  # Set default date to today
    manual_time = False  # Flag for manual time entry mode
    manual_clock_in = None  # Stores manually entered clock-in time
    manual_clock_out = None  # Stores manually entered clock-out time
    manual_break_start = None  # Stores manually entered break start time
    manual_break_end = None  # Stores manually entered break end time
    is_clocked_in = False  # Tracks if employee is currently clocked in
    is_on_break = False  # Tracks if employee is currently on break
    time_entry = []  # Stores time clock entries from database
    break_entry = []  # Stores break entries from database

    # --- UI Layout ---
    # Create main page title
    st.title("Home")
    
    # Create header section with profile information
    col1, col2 = st.columns([4, 1])  # Split layout into two columns (4:1 ratio)
    with col1:  # Left column for user info
        # Display welcome message with user's name
        st.subheader(f"Welcome, {st.session_state.user_name}!")
        # Show user's roles in smaller text
        st.caption(f"Role: {', '.join(st.session_state.roles)}")

    with col2:  # Right column for profile picture
        try:  # Handle potential errors in profile picture loading
            # Query database for most recent profile picture
            pic_data = session.sql(f"""
                SELECT PICTURE_DATA_TEXT FROM EMPLOYEE_PICTURES
                WHERE EMPLOYEEID = '{st.session_state.user_id}'
                ORDER BY UPLOADED_AT DESC LIMIT 1
            """).collect()
            
            if pic_data and pic_data[0]['PICTURE_DATA_TEXT']:
                # Decode base64 image data and display
                img = Image.open(io.BytesIO(base64.b64decode(pic_data[0]['PICTURE_DATA_TEXT'])))
                st.image(img, width=100)  # Show image at 100px width
            else:
                # Display placeholder gray image if no picture exists
                st.image(Image.new('RGB', (100,100), color='gray'), width=100)
        except Exception as e:  # Catch and display any image loading errors
            st.error(f"Couldn't load profile picture: {str(e)}")

    # --- Time Tracking Section ---
    # Create section header for time tracking
    st.subheader("Time Tracking")
    # Add toggle switch for manual time entry mode
    manual_time = st.toggle("Manual Time Entry", help="Enable to enter times manually")
    
    # Generate time options for manual entry dropdowns
    time_options = []  # Store tuples of (display time, time object)
    for hour in range(7, 23):  # Hours from 7 AM to 10 PM (23 in 24h format)
        for minute in [0, 15, 30, 45]:  # 15-minute intervals
            time_obj = time(hour, minute)  # Create time object
            # Format as 12-hour time with AM/PM and add to options
            time_options.append((time_obj.strftime("%I:%M %p"), time_obj))
    
    if manual_time:  # Manual time entry mode
        with st.form("manual_time_form"):  # Create form container
            st.warning("Manual Entry Mode - For correcting missed punches")
            
            # Date selection for manual entry
            selected_date = st.date_input(
                "Entry Date",
                value=datetime.now().date(),  # Default to today
                min_value=datetime.now().date() - timedelta(days=30),  # Allow past 30 days
                max_value=datetime.now().date()  # Don't allow future dates
            )
            
            # Create two columns for clock in/out times
            cols = st.columns(2)
            with cols[0]:  # Clock-in column
                selected_clock_in = st.selectbox(
                    "Clock In Time",
                    options=[t[0] for t in time_options],  # Display times
                    index=0,  # Default to first option
                    key="clock_in_select"
                )
                # Get corresponding time object from selection
                manual_clock_in = next(t[1] for t in time_options if t[0] == selected_clock_in)
            
            with cols[1]:  # Clock-out column
                selected_clock_out = st.selectbox(
                    "Clock Out Time",
                    options=["Not clocked out yet"] + [t[0] for t in time_options],
                    index=0,
                    key="clock_out_select"
                )
                # Handle "not clocked out" selection
                manual_clock_out = next((t[1] for t in time_options if t[0] == selected_clock_out), None)
            
            # Create two columns for break times
            cols = st.columns(2)
            with cols[0]:  # Break start column
                selected_break_start = st.selectbox(
                    "Break Start",
                    options=["No break"] + [t[0] for t in time_options],
                    index=0,
                    key="break_start_select"
                )
                manual_break_start = next((t[1] for t in time_options if t[0] == selected_break_start), None)
            
            with cols[1]:  # Break end column
                selected_break_end = st.selectbox(
                    "Break End",
                    options=["Break not ended"] + [t[0] for t in time_options],
                    index=0,
                    key="break_end_select"
                )
                manual_break_end = next((t[1] for t in time_options if t[0] == selected_break_end), None)
            
            # Form submission handler
            if st.form_submit_button("Save Manual Entry"):
                if not manual_clock_in:  # Validate required field
                    st.error("Clock in time is required")
                else:
                    try:
                        # Convert times to datetime objects with selected date
                        clock_in_dt = datetime.combine(selected_date, manual_clock_in)
                        clock_out_dt = datetime.combine(selected_date, manual_clock_out) if manual_clock_out else None
                        
                        # Check for existing time entry
                        existing = session.sql(f"""
                            SELECT ENTRYID FROM employee_time_entries
                            WHERE EMPLOYEEID = '{st.session_state.user_id}'
                            AND ENTRY_DATE = '{selected_date}'
                            LIMIT 1
                        """).collect()
                        
                        if existing:  # Update existing entry
                            session.sql(f"""
                                UPDATE employee_time_entries
                                SET CLOCK_IN = '{clock_in_dt}',
                                    CLOCK_OUT = {'NULL' if clock_out_dt is None else f"'{clock_out_dt}'"}
                                WHERE ENTRYID = '{existing[0]['ENTRYID']}'
                            """).collect()
                        else:  # Create new entry
                            entry_id = f"ENTRY{datetime.now().timestamp()}"  # Generate unique ID
                            session.sql(f"""
                                INSERT INTO employee_time_entries
                                (ENTRYID, EMPLOYEEID, CLOCK_IN, CLOCK_OUT, ENTRY_DATE)
                                VALUES (
                                    '{entry_id}',
                                    '{st.session_state.user_id}',
                                    '{clock_in_dt}',
                                    {'NULL' if clock_out_dt is None else f"'{clock_out_dt}'"},
                                    '{selected_date}'
                                )
                            """).collect()
                        
                        # Handle break entries if provided
                        if manual_break_start and manual_break_end:
                            # Convert break times to datetime objects
                            break_start_dt = datetime.combine(selected_date, manual_break_start)
                            break_end_dt = datetime.combine(selected_date, manual_break_end)
                            
                            # Check for existing break entry
                            existing_break = session.sql(f"""
                                SELECT BREAKID FROM employee_break_entries
                                WHERE EMPLOYEEID = '{st.session_state.user_id}'
                                AND ENTRY_DATE = '{selected_date}'
                                LIMIT 1
                            """).collect()
                            
                            if existing_break:  # Update existing break
                                session.sql(f"""
                                    UPDATE employee_break_entries
                                    SET BREAK_START = '{break_start_dt}',
                                        BREAK_END = '{break_end_dt}'
                                    WHERE BREAKID = '{existing_break[0]['BREAKID']}'
                                """).collect()
                            else:  # Create new break entry
                                break_id = f"BREAK{datetime.now().timestamp()}"
                                session.sql(f"""
                                    INSERT INTO employee_break_entries
                                    (BREAKID, EMPLOYEEID, BREAK_START, BREAK_END, ENTRY_DATE)
                                    VALUES (
                                        '{break_id}',
                                        '{st.session_state.user_id}',
                                        '{break_start_dt}',
                                        '{break_end_dt}',
                                        '{selected_date}'
                                    )
                                """).collect()
                        
                        st.success("Time entry saved successfully!")
                        st.rerun()  # Refresh page to show changes
                    except Exception as e:  # Handle database errors
                        st.error(f"Error saving time entry: {str(e)}")
    
    else:  # Automatic time tracking mode
        # Set date to today for automatic tracking
        selected_date = datetime.now().date()
        # Get current time entries from database
        time_entry = session.sql(f"""
            SELECT * FROM employee_time_entries
            WHERE EMPLOYEEID = '{st.session_state.user_id}'
            AND ENTRY_DATE = '{selected_date}'
            ORDER BY CLOCK_IN DESC
            LIMIT 1
        """).collect()
        
        # Get current break entries from database
        break_entry = session.sql(f"""
            SELECT * FROM employee_break_entries
            WHERE EMPLOYEEID = '{st.session_state.user_id}'
            AND ENTRY_DATE = '{selected_date}'
            ORDER BY BREAK_START DESC
            LIMIT 1
        """).collect()
        
        # Determine current clock status
        is_clocked_in = len(time_entry) > 0 and time_entry[0]['CLOCK_OUT'] is None
        # Determine current break status
        is_on_break = len(break_entry) > 0 and break_entry[0]['BREAK_END'] is None
        
        # Create time tracking buttons
        cols = st.columns(2)  # Split into two columns
        with cols[0]:  # Clock In button
            if st.button("🟢 Clock In", disabled=is_clocked_in):
                # Insert new time entry with current timestamp
                session.sql(f"""
                    INSERT INTO employee_time_entries
                    (ENTRYID, EMPLOYEEID, CLOCK_IN, ENTRY_DATE)
                    VALUES (
                        'ENTRY{datetime.now().timestamp()}',
                        '{st.session_state.user_id}',
                        CURRENT_TIMESTAMP(),
                        '{selected_date}'
                    )
                """).collect()
                st.rerun()  # Refresh to update status
        
        with cols[1]:  # Clock Out button
            if st.button("🔴 Clock Out", disabled=not is_clocked_in or is_on_break):
                # Update most recent entry with clock-out time
                session.sql(f"""
                    UPDATE employee_time_entries
                    SET CLOCK_OUT = CURRENT_TIMESTAMP()
                    WHERE EMPLOYEEID = '{st.session_state.user_id}'
                    AND ENTRY_DATE = '{selected_date}'
                    AND CLOCK_OUT IS NULL
                """).collect()
                st.rerun()
        
        # Break management buttons
        cols = st.columns(2)
        with cols[0]:  # Start Break button
            if st.button("🟡 Start Break", disabled=not is_clocked_in or is_on_break):
                # Insert new break entry with start time
                session.sql(f"""
                    INSERT INTO employee_break_entries
                    (BREAKID, EMPLOYEEID, BREAK_START, ENTRY_DATE)
                    VALUES (
                        'BREAK{datetime.now().timestamp()}',
                        '{st.session_state.user_id}',
                        CURRENT_TIMESTAMP(),
                        '{selected_date}'
                    )
                """).collect()
                st.rerun()
        
        with cols[1]:  # End Break button
            if st.button("🟢 End Break", disabled=not is_on_break):
                # Update most recent break with end time
                session.sql(f"""
                    UPDATE employee_break_entries
                    SET BREAK_END = CURRENT_TIMESTAMP()
                    WHERE EMPLOYEEID = '{st.session_state.user_id}'
                    AND ENTRY_DATE = '{selected_date}'
                    AND BREAK_END IS NULL
                """).collect()
                st.rerun()

    # Refresh time data after potential updates
    time_entry = session.sql(f"""
        SELECT * FROM employee_time_entries
        WHERE EMPLOYEEID = '{st.session_state.user_id}'
        AND ENTRY_DATE = '{selected_date}'
        ORDER BY CLOCK_IN DESC
        LIMIT 1
    """).collect()
    
    # Refresh break data after potential updates
    break_entry = session.sql(f"""
        SELECT * FROM employee_break_entries
        WHERE EMPLOYEEID = '{st.session_state.user_id}'
        AND ENTRY_DATE = '{selected_date}'
        ORDER BY BREAK_START DESC
        LIMIT 1
    """).collect()
    
    # Create two columns for status displays
    cols = st.columns(2)
    with cols[0]:  # Left status column
        # Clock status display
        if time_entry:
            if time_entry[0]['CLOCK_OUT'] is None:  # Currently clocked in
                st.write(f"**Clocked In:**  {time_entry[0]['CLOCK_IN'].strftime('%I:%M %p')}")
            else:  # Clocked out
                st.info("🔴 Clocked Out")
                st.write(f"**Worked:** {time_entry[0]['CLOCK_IN'].strftime('%I:%M %p')} to {time_entry[0]['CLOCK_OUT'].strftime('%I:%M %p')}")

        # Break status display (only shown if clocked in)
        if time_entry and time_entry[0]['CLOCK_OUT'] is None:
            if break_entry:
                if break_entry[0]['BREAK_END'] is None:  # Currently on break
                    st.error("🟡 Currently On Break")
                    st.write(f"**Since:** {break_entry[0]['BREAK_START'].strftime('%I:%M %p')}")
                else:  # Break completed
                    st.write(f"**Break:** {break_entry[0]['BREAK_START'].strftime('%I:%M %p')} to {break_entry[0]['BREAK_END'].strftime('%I:%M %p')}")
            else:  # No break taken
                st.success("✅ Available for Break")

    # Calculate and display total worked time
    time_entries = session.sql(f"""
        SELECT CLOCK_IN, CLOCK_OUT 
        FROM employee_time_entries
        WHERE EMPLOYEEID = '{st.session_state.user_id}'
        AND ENTRY_DATE = '{selected_date}'
        ORDER BY CLOCK_IN
    """).collect()
    
    # Get all break entries for the day
    break_entries = session.sql(f"""
        SELECT BREAK_START, BREAK_END 
        FROM employee_break_entries
        WHERE EMPLOYEEID = '{st.session_state.user_id}'
        AND ENTRY_DATE = '{selected_date}'
        ORDER BY BREAK_START
    """).collect()

    if time_entries:
        # Calculate total worked seconds
        total_seconds = 0
        for entry in time_entries:
            if entry['CLOCK_OUT']:
                # Add difference between clock out and in times
                total_seconds += (entry['CLOCK_OUT'] - entry['CLOCK_IN']).total_seconds()
            else:
                # Add time since clock in if still clocked in
                total_seconds += (datetime.now() - entry['CLOCK_IN']).total_seconds()
        
        # Calculate total break time in seconds
        break_seconds = 0
        for entry in break_entries:
            if entry['BREAK_END']:
                break_seconds += (entry['BREAK_END'] - entry['BREAK_START']).total_seconds()
        
        # Calculate net worked time
        net_seconds = total_seconds - break_seconds
        # Convert seconds to hours and minutes
        hours = int(net_seconds // 3600)
        minutes = int((net_seconds % 3600) // 60)
        
        # Display time with proper pluralization
        time_str = f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
        st.markdown("---")  # Horizontal line
        st.metric("Total Worked Today", time_str)  # Display metric
        st.markdown("---")

    # --- Upcoming Appointments Section ---
    st.header("📅 Upcoming Appointments")  # Section header

    # Query database for appointments
    appointments = session.sql(f"""
        SELECT 
            a.appointmentid,
            a.service_type,
            a.scheduled_time,
            a.sta_tus,
            c.name AS customer_name,
            c.address,
            c.unit,
            c.city,
            c.state,
            c.zipcode,
            c.lock_box_code,
            c.safety_alarm,
            c.entrance_note,
            c.request,
            c.unit_location,
            c.accessibility_level,
            c.phone,
            c.email
        FROM appointments a
        JOIN customers c ON a.customerid = c.customerid
        WHERE a.technicianid = '{st.session_state.user_id}'
        AND a.scheduled_time BETWEEN CURRENT_TIMESTAMP() 
            AND DATEADD('day', 30, CURRENT_TIMESTAMP())
        ORDER BY a.scheduled_time
    """).collect()

    if not appointments:  # Handle no appointments case
        st.info("No upcoming appointments in the next 7 days")
        return

    # Display each appointment in a row
    for appt in appointments:
        # Create 4-column layout per appointment
        col1, col2, col3, col4 = st.columns([1,1,3,1])
        
        with col1:  # Service type column
            st.markdown(f"**{appt['SERVICE_TYPE'].capitalize()}**")  # Capitalized service name
        
        with col2:  # Time column
            dt = appt['SCHEDULED_TIME']
            # Format date/time in compact form
            st.write(f"{dt.strftime('%B %d, %Y')}\n{dt.strftime('%I:%M %p')}")
        
        with col3:  # Customer info column
            full_address = f"{appt['ADDRESS']}, {appt['CITY']}, {appt['STATE']} {appt['ZIPCODE']}"
            # Create Google Maps link
            maps_url = f"https://www.google.com/maps/search/?api=1&query={full_address.replace(' ', '+')}"
            

            # Expandable section for detailed customer info
                
            with st.expander(f"**{appt['CUSTOMER_NAME']}** - {appt['ADDRESS']}, {appt['CITY']}"):
    # Address with Google Maps link
             full_address = f"{appt['ADDRESS']}, {appt['CITY']}, {appt['STATE']} {appt['ZIPCODE']}"
             maps_url = f"https://www.google.com/maps/search/?api=1&query={full_address.replace(' ', '+')}"
             st.markdown(f"**Complete Address:** [📌 {full_address}]({maps_url})")
    
    # Create lists for property access and special instructions
            property_access = []
            special_instructions = []
    
    # Unit information
            if appt['UNIT'] and appt['UNIT'] != 'N/A':
             property_access.append(f"**Unit #:** {appt['UNIT']}")
    
    # Lock box information
            if appt['LOCK_BOX_CODE'] and appt['LOCK_BOX_CODE'] != 'N/A':
             property_access.append(f"**Lock Box Code:** {appt['LOCK_BOX_CODE']}")
    
    # Safety alarm information
            if appt['SAFETY_ALARM'] and appt['SAFETY_ALARM'] != 'N/A':
             property_access.append(f"**Safety Alarm:** {appt['SAFETY_ALARM']}")
    
    # Entrance notes
            if appt['ENTRANCE_NOTE'] and appt['ENTRANCE_NOTE'] != 'N/A':
             special_instructions.append(f"**Entrance Notes:** {appt['ENTRANCE_NOTE']}")
    
    # General notes
            if appt['REQUEST'] and appt['REQUEST'] != 'N/A':
             special_instructions.append(f"**Request:** {appt['REQUEST']}")
    
    # Unit location
            if appt['UNIT_LOCATION'] and appt['UNIT_LOCATION'] != 'N/A':
             special_instructions.append(f"**Unit Location:** {appt['UNIT_LOCATION']}")
    
    # Accessibility information
            if appt['ACCESSIBILITY_LEVEL'] and appt['ACCESSIBILITY_LEVEL'] != 'N/A':
              special_instructions.append(f"**Accessibility:** {appt['ACCESSIBILITY_LEVEL']}")
    
    # Display property access information if any exists
            if property_access:
           
             st.markdown("\n".join(property_access))
    
    # Display special instructions if any exist
           
    
    # Always show contact information
             st.markdown(f"""
        **Phone:** {appt['PHONE']}  
        **Email:** {appt['EMAIL'] or 'Not provided'}
    """)



            

        with col4:  # Status management column
            current_status = appt['STA_TUS'].lower()  # Get lowercase status
            # Color coding for status badges
            status_colors = {
                'scheduled': '#4a4a4a',  # Dark gray
                'accepted': '#2e7d32',   # Green
                'declined': '#c62828',    # Red
                'arrived': '#1565c0'      # Blue
            }
            
            # Create styled status badge
            st.markdown(f"""
                <div style="
                    background-color: {status_colors.get(current_status, '#4a4a4a')};
                    color: white;
                    padding: 0.5rem;
                    border-radius: 0.5rem;
                    text-align: center;
                    margin: 0.5rem 0;
                    font-size: 0.9rem;
                ">
                    {current_status.capitalize()}
                </div>
            """, unsafe_allow_html=True)
            
            # Status transition buttons
            if current_status == 'scheduled':
                # Accept appointment button
                if st.button("✅ Accept", key=f"accept_{appt['APPOINTMENTID']}"):
                    session.sql(f"""
                        UPDATE appointments
                        SET STA_TUS = 'accepted'
                        WHERE APPOINTMENTID = '{appt['APPOINTMENTID']}'
                    """).collect()
                    st.rerun()
                
                # Decline appointment button
                if st.button("❌ Decline", key=f"decline_{appt['APPOINTMENTID']}"):
                    session.sql(f"""
                        UPDATE appointments
                        SET STA_TUS = 'declined'
                        WHERE APPOINTMENTID = '{appt['APPOINTMENTID']}'
                    """).collect()
                    st.rerun()
            
            elif current_status == 'accepted':
                # Mark as arrived button
                if st.button("📍 I'm Here", key=f"arrived_{appt['APPOINTMENTID']}"):
                    session.sql(f"""
                        UPDATE appointments
                        SET STA_TUS = 'arrived'
                        WHERE APPOINTMENTID = '{appt['APPOINTMENTID']}'
                    """).collect()
                    st.rerun()

        st.markdown("---")  # Divider between appointments
        
        
        
        
#######################################################################
#######################################################################        
#######################################################################
def profile_page():
    # Establish connection to Snowflake database using existing session
    session = get_session()
    
    # --- Profile Header Section ---
    # Create two columns layout (1:4 ratio) for profile picture and info
    col1, col2 = st.columns([1, 4])
    
    with col1:  # Left column for profile picture
        # Query database for most recent profile picture
        pic_data = session.sql(f"""
            SELECT PICTURE_DATA_TEXT FROM EMPLOYEE_PICTURES
            WHERE EMPLOYEEID = '{st.session_state.user_id}'
            ORDER BY UPLOADED_AT DESC LIMIT 1
        """).collect()
        
        # Display profile picture if exists
        if pic_data and pic_data[0]['PICTURE_DATA_TEXT']:
            # Decode base64 image data
            img_data = base64.b64decode(pic_data[0]['PICTURE_DATA_TEXT'])
            # Open image and resize
            img = Image.open(io.BytesIO(img_data))
            img.thumbnail((80, 80), Image.Resampling.LANCZOS)
            # Display resized image
            st.image(img, width=80)
        else:
            # Show placeholder gray image
            st.image(Image.new('RGB', (80, 80), color='lightgray'))
        
        # Create expandable section for picture upload
        with st.expander("🖼"):  # Frame emoji as icon
            # Add hidden tooltip
            st.markdown("<span title='Update profile picture'>", unsafe_allow_html=True)
            # File uploader widget (hidden label)
            uploaded_file = st.file_uploader("", type=["jpg", "jpeg", "png"], key="pic_uploader")
            # Update button with image processing
            if uploaded_file and st.button("Update", key="pic_update"):
                try:
                    # Process uploaded image
                    img = Image.open(uploaded_file)
                    img = ImageOps.fit(img, (500, 500))  # Crop to square
                    # Save to buffer with quality settings
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=90)
                    # Encode image for database storage
                    encoded_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    
                    # Insert new picture record
                    session.sql(f"""
                        INSERT INTO EMPLOYEE_PICTURES 
                        (PICTUREID, EMPLOYEEID, PICTURE_DATA_TEXT)
                        VALUES (
                            'PIC{datetime.now().timestamp()}',  

                            '{st.session_state.user_id}',
                          
                            '{encoded_image}'  
                        )
                    """).collect()
                    st.rerun()  # Refresh to show new picture
                except Exception as e:
                    st.error(f"Error: {str(e)}")
            # Close tooltip span
            st.markdown("</span>", unsafe_allow_html=True)

    with col2:  # Right column for profile info
        # Display user name as title
        st.title(f"{st.session_state.user_name}'s Profile")
        # Show employee ID in caption
        st.caption(f"Employee ID: {st.session_state.user_id}")

    # --- Date Range Selector ---
    # Set default date range to current week
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    end_of_week = start_of_week + timedelta(days=6)  # Sunday
    
    # Create expandable date selector
    with st.expander("📅 Date Range", expanded=True):
        col1, col2 = st.columns(2)  # Split into two columns
        with col1:
            # Start date picker with week start default
            start_date = st.date_input("From", value=start_of_week)
        with col2:
            # End date picker with week end default
            end_date = st.date_input("To", value=end_of_week, min_value=start_date)

    # --- Tab Navigation ---
    # Create four tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Schedule", 
        "⏱ Work History", 
        "💰 Earnings", 
        "📝 Appointments"
    ])

    # Tab 1: 
    # --- Employee Schedule Section ---
    with tab1:
        st.subheader("📅 My Schedule")
    
    # Get current week (Monday to Sunday)
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=30)
    
    # Get employee's schedule for the week
        session = get_session()
        schedules = session.sql(f"""
            SELECT 
                SCHEDULE_DATE,
                TO_CHAR(START_TIME, 'HH24:MI') || ' - ' || TO_CHAR(END_TIME, 'HH24:MI') AS TIME_SLOT,
                NOTES
            FROM EMPLOYEE_SCHEDULES
        WHERE EMPLOYEEID = '{st.session_state.user_id}'
        AND SCHEDULE_DATE BETWEEN '{start_of_week}' AND '{end_of_week}'
        ORDER BY SCHEDULE_DATE
        """).collect()
    
    # Create schedule data
        schedule_data = []
        current_date = start_of_week
        while current_date <= end_of_week:
        # Find schedule for this day
            day_schedule = next((s for s in schedules if s['SCHEDULE_DATE'] == current_date), None)
        
            schedule_data.append({
                "Day": current_date.strftime("%A %m/%d"),
                "Time": day_schedule['TIME_SLOT'] if day_schedule else "Not Scheduled",
                "Notes": day_schedule['NOTES'] if day_schedule else ""
         })
            current_date += timedelta(days=1)
    
    # Display schedule in a clean 2-column table
        st.dataframe(
            pd.DataFrame(schedule_data)[["Day", "Time"]],  # Only show Day and Time columns
            hide_index=True,
            use_container_width=True,
            column_config={
                "Day": st.column_config.Column(width="medium"),
                 "Time": st.column_config.Column(width="small")
             }
            )
    
    # Show notes in expandable sections
        with st.expander("📝 View Schedule Notes"):
            for day in schedule_data:
                if day["Notes"]:
                    st.write(f"**{day['Day']}**: {day['Notes']}")
                else:
                    st.write(f"**{day['Day']}**: No notes")
    
   



        

    # Tab 2: Work History
    with tab2:
        # Query time entries from database
        time_entries = session.sql(f"""
            SELECT 
                ENTRY_DATE,
                CLOCK_IN,
                CLOCK_OUT,
                TIMEDIFF('MINUTE', CLOCK_IN, CLOCK_OUT)/60.0 as hours_worked
            FROM employee_time_entries
            WHERE EMPLOYEEID = '{st.session_state.user_id}'
            AND ENTRY_DATE BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY ENTRY_DATE DESC, CLOCK_IN DESC
        """).collect()
        
        if time_entries:
            # Calculate total hours
            total_hours = sum(entry['HOURS_WORKED'] or 0 for entry in time_entries)
            
            # Create formatted dataframe
            st.dataframe(
                pd.DataFrame([{
                    "Date": e['ENTRY_DATE'].strftime('%Y-%m-%d'),
                    "Clock In": e['CLOCK_IN'].strftime('%I:%M %p') if e['CLOCK_IN'] else "-",
                    "Clock Out": e['CLOCK_OUT'].strftime('%I:%M %p') if e['CLOCK_OUT'] else "-",
                    "Hours": f"{e['HOURS_WORKED']:.2f}" if e['HOURS_WORKED'] else "-"
                } for e in time_entries]),
                hide_index=True,  # Hide pandas index
                use_container_width=True  # Full-width display
            )
            
            # Display total hours metric
            st.metric("Total Hours Worked", f"{total_hours:.2f}")
        else:
            st.info("No work history for selected period")

    # Tab 3: Earnings
    with tab3:
        # Get employee hourly rate
        emp_rate = session.sql(f"""
            SELECT hourlyrate FROM employees
            WHERE employeeid = '{st.session_state.user_id}'
        """).collect()[0]['HOURLYRATE']
        
        # Query earnings data
        earnings = session.sql(f"""
            SELECT 
                ENTRY_DATE,
                SUM(TIMEDIFF('MINUTE', CLOCK_IN, CLOCK_OUT)/60.0) as hours_worked
            FROM employee_time_entries
            WHERE EMPLOYEEID = '{st.session_state.user_id}'
            AND CLOCK_OUT IS NOT NULL  
            AND ENTRY_DATE BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY ENTRY_DATE
            ORDER BY ENTRY_DATE DESC
        """).collect()
        
        if earnings:
            # Calculate total earnings
            total_earnings = sum(e['HOURS_WORKED'] * emp_rate for e in earnings)
            
            # Display earnings dataframe
            st.dataframe(
                pd.DataFrame([{
                    "Date": e['ENTRY_DATE'].strftime('%Y-%m-%d'),
                    "Hours": f"{e['HOURS_WORKED']:.2f}",
                    "Rate": f"${emp_rate:.2f}",
                    "Earnings": f"${e['HOURS_WORKED'] * emp_rate:.2f}"
                } for e in earnings]),
                hide_index=True,
                use_container_width=True
            )
            
            # Show total earnings metric
            st.metric("Total Earnings", f"${total_earnings:.2f}")
        else:
            st.info("No earnings data for selected period")

    # Tab 4: Appointments
    with tab4:
        # Query appointments from database
        appointments = session.sql(f"""
            SELECT 
                c.name as customer,
                a.scheduled_time,
                TO_VARCHAR(a.scheduled_time, 'HH12:MI AM') as time,
                a.sta_tus as status,
                a.notes
            FROM appointments a
            JOIN customers c ON a.customerid = c.customerid
            WHERE a.technicianid = '{st.session_state.user_id}'
            AND DATE(a.scheduled_time) BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY a.scheduled_time
        """).collect()
        
        if appointments:
            # Display each appointment in expandable sections
            for appt in appointments:
                # Create expander with formatted title
                with st.expander(f"{appt['SCHEDULED_TIME'].strftime('%a %m/%d')} - {appt['CUSTOMER']} ({appt['TIME']})"):
                    st.write(f"**Status:** {appt['STATUS'].capitalize()}")
                    if appt['NOTES']:
                        st.write(f"**Notes:** {appt['NOTES']}")
        else:
            st.info("No appointments for selected period") 



######################################################################            
######################################################################            
######################################################################            
#######################################################################            
def customer_management():
    st.subheader("👥 Customer Management")
    session = get_session()

    if 'customer_form_data' not in st.session_state:
        st.session_state.customer_form_data = {
            'name': '',
            'phone': '',
            'email': '',
            'address': '',
            'unit': '',
            'city': '',
            'state': 'MD',
            'zipcode': '',
            'lock_box_code': '',
            'safety_alarm': '',  
            'how_heard': '',
            'referral_name': '',
            'entrance_note': '',
            'request': '',
            'unit_location': '',
            'accessibility_level': ''
        }

    with st.expander("➕ Add New Customer", expanded=False):
        with st.form(key="add_customer_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Full Name*", value=st.session_state.customer_form_data['name'])
                phone = st.text_input("Phone* ###-###-####", value=st.session_state.customer_form_data['phone'], placeholder="301-555-1234")
                email = st.text_input("Email", value=st.session_state.customer_form_data['email'])
                address = st.text_input("Street Address*", value=st.session_state.customer_form_data['address'])
                unit = st.text_input("Unit/Apt", value=st.session_state.customer_form_data['unit'])
                city = st.text_input("City*", value=st.session_state.customer_form_data['city'])
                state = st.selectbox("State*", ["MD", "DC", "VA"], index=["MD", "DC", "VA"].index(st.session_state.customer_form_data['state']))
                zipcode = st.text_input("Zip Code* (5 or 9 digits)", value=st.session_state.customer_form_data['zipcode'])

            with col2:
                entrance_note = st.text_input("Entrance Notes", value=st.session_state.customer_form_data['entrance_note'])

                lock_box_code = st.text_input("Lock Box Code", value=st.session_state.customer_form_data['lock_box_code'])

                safety_alarm = st.text_input("Safety Alarm", value=st.session_state.customer_form_data['safety_alarm'])
                unit_location = st.selectbox(
                    "Unit Location",
                    options=["", "Attic", "Basement", "Garage", "Closet", "Crawlspace", "Other"],
                    index=["","Attic", "Basement", "Garage", "Closet", "Crawlspace", "Other"].index(
                        st.session_state.customer_form_data['unit_location']
                    ) if st.session_state.customer_form_data['unit_location'] in ["Attic", "Basement", "Garage", "Closet", "Crawlspace", "Other"] else 0
                )
                accessibility_level = st.selectbox(
                    "Accessibility Level",
                    options=["","Easy", "Moderate", "Difficult"],
                    index=["","Easy", "Moderate", "Difficult"].index(
                        st.session_state.customer_form_data['accessibility_level']
                    ) if st.session_state.customer_form_data['accessibility_level'] in ["Easy", "Moderate", "Difficult"] else 0
                )
                request = st.text_input("Request", value=st.session_state.customer_form_data['request'])

                how_heard = st.selectbox(
                    "How did you hear about us?",
                    ["", "Google", "Friend", "Facebook", "Yelp", "Other"],
                    index=0
                )
                referral_name = st.text_input("Referral Name:", value=st.session_state.customer_form_data['referral_name'])
                
      
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Add Customer")
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.customer_form_data = {
                        'name': '',
                        'phone': '',
                        'email': '',
                        'address': '',
                        'unit': '',
                        'city': '',
                        'state': 'MD',
                        'zipcode': '',
                        'lock_box_code': '',
                        'safety_alarm': '',
                        'how_heard': '',
                        'referral_name': '',
                        'request': '',
                        'entrance_note': '',
                        'unit_location':'',
                        'accessibility_level':''
                    }
                    st.rerun()
            
            if submitted:
                st.session_state.customer_form_data.update({
                    'name': name,
                    'phone': phone,
                    'email': email,
                    'address': address,
                    'unit': unit,
                    'city': city,
                    'state': state,
                    'zipcode': zipcode,
                    'lock_box_code': lock_box_code,
                    'safety_alarm': safety_alarm,
                    'how_heard': how_heard,
                    'referral_name': referral_name,
                    'request': request,
                    'entrance_note': entrance_note,
                    'unit_location': unit_location,
                    'accessibility_level': accessibility_level
                })

                errors = []
                if not name:
                    errors.append("Full Name is required")
                if not phone:
                    errors.append("Phone is required")
                elif not re.match(r"^\d{3}-\d{3}-\d{4}$", phone):
                    errors.append("Invalid phone format (use ###-###-####)")
                if not address:
                    errors.append("Address is required")
                if not city:
                    errors.append("City is required")
                if not state:
                    errors.append("State is required")
                if not zipcode:
                    errors.append("Zip Code is required")
                elif not re.match(r"^\d{5}(-\d{4})?$", zipcode):
                    errors.append("Invalid zip code format (use 5 or 9 digits)")
                if email and not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                    errors.append("Invalid email format")
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    try:
                        # Generate customer ID
                        last_customer = session.sql("""
                            SELECT MAX(TRY_TO_NUMBER(SUBSTRING(CUSTOMERID, 3))) as max_num 
                            FROM CUSTOMERS 
                            WHERE CUSTOMERID LIKE 'CU%'
                        """).collect()
                        
                        if last_customer and last_customer[0]['MAX_NUM'] is not None:
                            next_num = last_customer[0]['MAX_NUM'] + 1
                        else:
                            next_num = 100
                        
                        customer_id = f"CU{next_num:03d}"
                        
                        # Escape special characters in text fields
                        def escape_text(text):
                            return text.replace("'", "''") if text else None
                            
                        # Insert customer record
                        insert_query = f"""
                            INSERT INTO CUSTOMERS (
                                CUSTOMERID, NAME, PHONE, EMAIL, ADDRESS, UNIT, CITY, STATE, ZIPCODE,
                                LOCK_BOX_CODE, SAFETY_ALARM, HOW_HEARD, REFERRAL_NAME,
                                REQUEST, ENTRANCE_NOTE, UNIT_LOCATION, ACCESSIBILITY_LEVEL
                            ) VALUES (
                                '{customer_id}',
                                '{escape_text(name)}',
                                '{escape_text(phone)}',
                                {f"'{escape_text(email)}'" if email else 'NULL'},
                                '{escape_text(address)}',
                                {f"'{escape_text(unit)}'" if unit else 'NULL'},
                                '{escape_text(city)}',
                                '{state}',
                                '{zipcode}',
                                {f"'{escape_text(lock_box_code)}'" if lock_box_code else 'NULL'},
                                {f"'{escape_text(safety_alarm)}'" if safety_alarm else 'NULL'},
                                {f"'{escape_text(how_heard)}'" if how_heard else 'NULL'},
                                {f"'{escape_text(referral_name)}'" if referral_name else 'NULL'},
                                {f"'{escape_text(request)}'" if request else 'NULL'},
                                {f"'{escape_text(entrance_note)}'" if entrance_note else 'NULL'},
                                {f"'{escape_text(unit_location)}'" if unit_location else 'NULL'},
                                {f"'{escape_text(accessibility_level)}'" if accessibility_level else 'NULL'}
                            )
                        """
                        
                        session.sql(insert_query).collect()
                        st.success(f"✅ Customer added successfully! Customer ID: {customer_id}")
                        
                        # Clear form
                        st.session_state.customer_form_data = {
                            'name': '',
                            'phone': '',
                            'email': '',
                            'address': '',
                            'unit': '',
                            'city': '',
                            'state': 'MD',
                            'zipcode': '',
                            'lock_box_code': '',
                            'safety_alarm': '',
                            'how_heard': '',
                            'referral_name': '',
                            'request': '',
                            'entrance_note': '',
                            'unit_location': '',
                            'accessibility_level': ''
                        }
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding customer: {str(e)}")
                

                 ####################
            
    st.subheader("🔍 Search Customers")
    search_term = st.text_input("", placeholder="Search by name, phone, email, or address", key="unified_search")



    
    if search_term:
        customers = session.sql(f"""
            SELECT c.* FROM CUSTOMERS c
            WHERE c.NAME ILIKE '%{search_term}%' 
               OR c.PHONE ILIKE '%{search_term}%'
               OR c.EMAIL ILIKE '%{search_term}%'
               OR c.ADDRESS ILIKE '%{search_term}%'
            ORDER BY c.NAME
        """).collect()

        if customers:
            for customer in customers:
                try:
                    customer_dict = customer.as_dict() if hasattr(customer, 'as_dict') else dict(zip(customer._fields, customer))
                except:
                    customer_dict = dict(zip(['CUSTOMERID', 'NAME', 'PHONE', 'EMAIL', 'ADDRESS', 'UNIT', 'CITY', 'STATE', 'ZIPCODE',
                                            'LOCK_BOX_CODE', 'SAFETY_ALARM', 'HOW_HEARD','REFERRAL_NAME',
                                            'REQUEST', 'ENTRANCE_NOTE', 'UNIT_LOCATION', 'ACCESSIBILITY_LEVEL'

                                           ], customer))
                
                with st.container():
                    st.subheader(f"{customer_dict['NAME']}  {customer_dict['PHONE']}")
                    
                   
                    st.write(f"**Customer ID:** {customer_dict['CUSTOMERID']}")
                    st.write(f"**Email:** {customer_dict.get('EMAIL', 'Not provided')}")
                        
                    full_address = f"{customer_dict['ADDRESS']}, {customer_dict['CITY']}, {customer_dict['STATE']} {customer_dict['ZIPCODE']}"
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={full_address.replace(' ', '+')}"
                    st.markdown(f"""
                    **Address:** <a href="{maps_url}" target="_blank" style="color: blue; text-decoration: none;">
                    {customer_dict['ADDRESS']}{', ' + customer_dict['UNIT'] if customer_dict.get('UNIT') else ''}<br>
                    {customer_dict['CITY']}, {customer_dict['STATE']} {customer_dict['ZIPCODE']}.
                            </a>
                     """, unsafe_allow_html=True)
                    
                    
                    
                    st.write(f"**Unit #:** {customer_dict.get('unit_number', '')}")
                    st.write(f"**How Heard:** {customer_dict.get('HOW_HEARD', 'Not specified')}")
                    st.write(f"**request:** {customer_dict.get('request', 'None')}")
                    st.write(f"**Entrance Note:** {customer_dict.get('ENTRANCE_NOTE', 'None')}")
                    st.write(f"**Unit Location:** {customer_dict.get('UNIT_LOCATION', 'None')}")

                    ################################################
                   
                    ################################################
                    
                    
                    ########################################
                    ########################################################



               ####### Bottom of the page// Buttons 

    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Edit", key=f"edit_{customer_dict['CUSTOMERID']}"):
                            st.session_state['edit_customer'] = customer_dict['CUSTOMERID']
                            st.session_state['customer_to_edit'] = customer_dict
                            st.rerun()
                    with col2:
                        if st.button("Schedule Appointment", key=f"appt_{customer_dict['CUSTOMERID']}"):
                            st.session_state['appointment_customer_id'] = customer_dict['CUSTOMERID']
                            st.session_state['appointment_customer_name'] = customer_dict['NAME']
                            st.session_state['active_tab'] = 'appointments'
                            st.rerun()
                   

                  
                  




   
    
    

    ##### EDIT CUSTOMER ##########


    # --- Edit Customer Form ---
    if 'edit_customer' in st.session_state and 'customer_to_edit' in st.session_state:
        edit_customer_id = st.session_state['edit_customer']
        customer_to_edit = st.session_state['customer_to_edit']
        
        st.subheader("✏️ Edit Customer")
        with st.form("edit_customer_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Full Name*", value=customer_to_edit['NAME'])
                phone = st.text_input("Phone*", value=customer_to_edit['PHONE'])
                email = st.text_input("Email", value=customer_to_edit.get('EMAIL', ''))
                address = st.text_input("Street Address*", value=customer_to_edit['ADDRESS'])
                unit = st.text_input("Unit/Apt", value=customer_to_edit.get('UNIT', ''))
                city = st.text_input("City*", value=customer_to_edit['CITY'])
                state = st.selectbox("State*", ["MD", "DC", "VA"], 
                index=["MD", "DC", "VA"].index(customer_to_edit['STATE']))
                zipcode = st.text_input("Zip Code*", value=customer_to_edit['ZIPCODE'])
                how_heard = customer_to_edit.get('HOW_HEARD', '')
                
                
                how_heard = st.selectbox(
                    "How did you hear about us?",
                    ["", "Google", "Friend", "Facebook", "Yelp", "Other"],
                    index=["", "Google", "Friend", "Facebook", "Yelp", "Other"].index(how_heard) if how_heard in ["", "Google", "Friend", "Facebook", "Yelp", "Other"] else 0
                )
  
                referral_name = st.text_input("referral_name", value=customer_to_edit.get('referral_name', ''))
                
       
            with col2:

                lock_box_code = st.text_input("Lock Box Code", value=customer_to_edit.get('LOCK_BOX_CODE', ''))
                safety_alarm = st.text_input("Safety Alarm ", value=customer_to_edit.get('SAFETY_ALARM', ''))
                entrance_note = st.text_input("Entrance Notes", value=customer_to_edit.get('entrance_note', ''))
                request = st.text_input("Request", value=customer_to_edit.get('REQUEST', ''))

            # Safer unit location selection
                unit_location_options = ["", "Attic", "Basement", "Garage", "Closet", "Crawlspace", "Other"]
                current_location = customer_to_edit.get('UNIT_LOCATION', '')
                default_index = unit_location_options.index(current_location) if current_location in unit_location_options else 0
                unit_location = st.selectbox(
                "Unit Location",
                options=unit_location_options,
                index=default_index)


                accessibility_level_option = ["", "Easy", "Moderate", "Difficult"]
                current_accessibility_level= customer_to_edit.get('ACCESSIBILITY_LEVEL', '')
                access_index = accessibility_level_option.index(current_accessibility_level) if current_accessibility_level in accessibility_level_option else 0
                accessibility_level = st.selectbox(
                "Accessibility Level",
                options=accessibility_level_option,
                index=access_index)
                


            submitted = st.form_submit_button("💾 Save Changes")
            if submitted:
                # Validate inputs
                    if not all([name, phone, address]):
                        st.error("Please fill in all required fields (*)")
                    elif not re.match(r"^\d{3}-\d{3}-\d{4}$", phone):
                        st.error("Invalid phone number format. Please use ###-###-####")
                
                    else:
                        try:
                                                    
                            email_escaped = email.replace("'", "''") if email else None
                            unit_escaped = unit.replace("'", "''") if unit else None
                            lock_box_code_escaped = lock_box_code.replace("'", "''") if lock_box_code else None
                            safety_alarm_escaped = safety_alarm.replace("'", "''") if safety_alarm else None
                            how_heard_escaped = how_heard.replace("'", "''") if how_heard else None
                            request_escaped = request.replace("'", "''") if request else None
                            entrance_note_escaped = entrance_note.replace("'", "''") if entrance_note else None   
                            referral_name_escaped = referral_name.replace("'", "''") if referral_name else None  
                            accessibility_level_escaped = accessibility_level.replace("'", "''") if accessibility_level else None
                            unit_location_escaped = unit_location.replace("'", "''") if unit_location else None

                                  
                    
                            # Update customer record

                            update_query = f"""
                                UPDATE CUSTOMERS 
                                SET NAME = '{name.replace("'", "''")}',
                                    PHONE = '{phone.replace("'", "''")}',
                                    EMAIL = {f"'{email_escaped}'" if email else 'NULL'},
                                    ADDRESS = '{address.replace("'", "''")}',
                                    UNIT = {f"'{unit_escaped}'" if unit else 'NULL'},
                                    CITY = '{city.replace("'", "''")}',
                                    STATE = '{state}',
                                    ZIPCODE = '{zipcode}',
                                    LOCK_BOX_CODE = {f"'{lock_box_code_escaped}'" if lock_box_code else 'NULL'},
                                    SAFETY_ALARM = {f"'{safety_alarm_escaped}'" if safety_alarm else 'NULL'},
                                    HOW_HEARD = {f"'{how_heard_escaped}'" if how_heard else 'NULL'},
                                    REFERRAL_NAME = {f"'{referral_name_escaped}'" if referral_name else 'NULL'},
                                    REQUEST = {f"'{request_escaped}'" if request else 'NULL'},
                                    ENTRANCE_NOTE = {f"'{entrance_note_escaped}'" if entrance_note else 'NULL'},
                                    UNIT_LOCATION = {f"'{unit_location_escaped} '" if unit_location else 'NULL'},
                                    ACCESSIBILITY_LEVEL = {f"'{accessibility_level_escaped} '" if accessibility_level else 'NULL'}
                                WHERE CUSTOMERID = '{edit_customer_id}'
                                """
                            session.sql(update_query).collect()
                            st.success("Customer updated successfully!")
                            del st.session_state['edit_customer']
                            del st.session_state['customer_to_edit']
                            st.rerun()
                    
                        except Exception as e:
                            st.error(f"Error updating customer: {str(e)}")
            
            # Cancel button
        if st.button("❌ Cancel"):
            del st.session_state['edit_customer']
            del st.session_state['customer_to_edit']
            st.rerun()
########################################################################################################################
########################################################################################################################      
 ########################################################################################################################
def customer_search_component():
    session = get_session()
    
    st.subheader("🔍 Customer Search")
    search_query = st.text_input("Search by Name, Phone, or Address", key="customer_search")
    
    if search_query:
        customers = session.sql(f"""
            SELECT customerid, name, phone, address 
            FROM customers 
            WHERE NAME ILIKE '%{search_query}%' 
               OR PHONE ILIKE '%{search_query}%'
               OR ADDRESS ILIKE '%{search_query}%'
            ORDER BY name
            LIMIT 10
        """).collect()
        
        if customers:
            selected_customer = st.selectbox(
                "Select Customer",
                options=[row['CUSTOMERID'] for row in customers],
                format_func=lambda x: next(f"{row['NAME']} ({row['PHONE']}) - {row['ADDRESS']}" 
                                         for row in customers if row['CUSTOMERID'] == x)
            )
            return selected_customer
        else:
            st.warning("No customers found")
            return None
    return None       

    
############################################################
#######################################################################


   
   
                          


######################################################################

##########

def appointments():
    session = get_session()
    
    # Check if we have a customer pre-selected
    if 'appointment_customer_id' in st.session_state:
        customer_id = st.session_state['appointment_customer_id']
        customer_name = st.session_state['appointment_customer_name']
        
        # Pre-fill the customer search
        st.session_state.customer_search = customer_name
        customer = session.sql(f"""
            SELECT * FROM customers 
            WHERE customerid = '{customer_id}'
        """).collect()[0]
        
        # Remove the stored customer ID so it doesn't persist
        del st.session_state['appointment_customer_id']
        del st.session_state['appointment_customer_name']
    else:
        customer = None



    # --- Step 1: Customer Selection ---
    st.subheader("1. Select Customer")
    search_query = st.text_input("Search by Name, Phone, Email, or Address", key="customer_search")
    
    # Fetch customers
    customers = session.sql(f"""
        SELECT customerid, name, phone FROM customers 
        {'WHERE NAME ILIKE ' + f"'%{search_query}%'" if search_query else ''}
        ORDER BY name
    """).collect()
    
    if not customers:
        st.warning("No customers found")
        return
    
    selected_customer_id = st.selectbox(
        "Select Customer",
        options=[row['CUSTOMERID'] for row in customers],
        format_func=lambda x: next(f"{row['NAME']} ({row['PHONE']})" for row in customers if row['CUSTOMERID'] == x)
    )

    # --- Step 2: Service Request ---
    st.subheader("2. Service Request")
    request_type = st.selectbox(
        "Select Request Type",
        ["Install", "Service", "Estimate"],
        index=0
    )

    # Get qualified technicians
    expertise_map = {"Install": "EX1", "Service": "EX2", "Estimate": "EX3"}
    technicians = session.sql(f"""
        SELECT e.employeeid, e.ename 
        FROM employees e
        JOIN employee_expertise ee ON e.employeeid = ee.employeeid
        WHERE ee.expertiseid = '{expertise_map[request_type]}'
    """).collect()
    
    if not technicians:
        st.error("No technicians available")
        return

    # --- Different Logic for Install vs Other Services ---
    if request_type == "Install":
        # Full-day booking for installations
        st.subheader("3. Select Installation Date")
        
        # Show 4 weeks of available dates
        start_date = datetime.now().date()
        dates = [start_date + timedelta(days=i) for i in range(28)]
        
        # Get already booked installation days
        booked_days = session.sql(f"""
            SELECT DISTINCT DATE(scheduled_time) as day 
            FROM appointments 
            WHERE service_type = 'Install'
            AND DATE(scheduled_time) BETWEEN '{start_date}' AND '{start_date + timedelta(days=28)}'
        """).collect()
        booked_days = [row['DAY'] for row in booked_days]
        
        # Display available dates
        cols = st.columns(7)
        for i, date in enumerate(dates):
            with cols[i % 7]:
                if date in booked_days:
                    st.button(
                        f"{date.strftime('%a %m/%d')}",
                        disabled=True,
                        key=f"install_day_{date}"
                    )
                else:
                    if st.button(
                        f"{date.strftime('%a %m/%d')}",
                        key=f"install_day_{date}"
                    ):
                        st.session_state.selected_install_date = date
        
        # Handle installation booking
        if 'selected_install_date' in st.session_state:
            date = st.session_state.selected_install_date
            st.success(f"Selected installation date: {date.strftime('%A, %B %d')}")
            
            # Select primary technician
            primary_tech = st.selectbox(
                "Primary Technician",
                options=[t['EMPLOYEEID'] for t in technicians],
                format_func=lambda x: next(t['ENAME'] for t in technicians if t['EMPLOYEEID'] == x)
            )
            
            # Select secondary technician (optional)
            secondary_techs = [t for t in technicians if t['EMPLOYEEID'] != primary_tech]
            secondary_tech = st.selectbox(
                "Additional Technician (Optional)",
                options=[""] + [t['EMPLOYEEID'] for t in secondary_techs],
                format_func=lambda x: next(t['ENAME'] for t in technicians if t['EMPLOYEEID'] == x) if x else "None"
            )
            
            notes = st.text_area("Installation Notes")
            
            if st.button("Book Installation"):
                try:
                    # Book primary technician for full day (8AM-5PM)
                    session.sql(f"""
                        INSERT INTO appointments (
                            appointmentid, customerid, technicianid,
                            scheduled_time, service_type, notes, sta_tus
                        ) VALUES (
                            'APT{datetime.now().timestamp()}',
                            '{selected_customer_id}',
                            '{primary_tech}',
                            '{datetime.combine(date, time(8,0))}',
                            'Install',
                            '{notes}',
                            'scheduled'
                        )
                    """).collect()
                    
                    # Book secondary technician if selected
                    if secondary_tech:
                        session.sql(f"""
                            INSERT INTO appointments (
                                appointmentid, customerid, technicianid,
                                scheduled_time, service_type, notes, sta_tus
                            ) VALUES (
                                'APT{datetime.now().timestamp()}',
                                '{selected_customer_id}',
                                '{secondary_tech}',
                                '{datetime.combine(date, time(8,0))}',
                                'Install-Assist',
                                '{notes}',
                                'scheduled'
                            )
                        """).collect()
                    
                    st.success(f"Installation booked for {date.strftime('%A, %B %d')}!")
                    del st.session_state.selected_install_date
                    st.rerun()
                
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    else:
        # Standard 2-hour slots for non-installation services
        st.subheader("3. Select Appointment Time")
        
        # Week navigation
        today = datetime.now().date()
        if 'week_offset' not in st.session_state:
            st.session_state.week_offset = 0
        
        col1, col2, col3 = st.columns([2,1,1])
        with col1:
            st.write(f"Week of {(today + timedelta(weeks=st.session_state.week_offset)).strftime('%B %d')}")
        with col2:
            if st.button("◀ Previous Week"):
                st.session_state.week_offset -= 1
                st.rerun()
        with col3:
            if st.button("Next Week ▶"):
                st.session_state.week_offset += 1
                st.rerun()
        
        start_date = today + timedelta(weeks=st.session_state.week_offset) - timedelta(days=today.weekday())
        days = [start_date + timedelta(days=i) for i in range(7)]
        
        # Get existing appointments
        appointments = session.sql(f"""
            SELECT * FROM appointments
            WHERE DATE(scheduled_time) BETWEEN '{start_date}' AND '{start_date + timedelta(days=6)}'
            AND sta_tus != 'cancelled'
        """).collect()
        
        # Create calendar with 2-hour slots (8AM-6PM)
        time_slots = [time(hour) for hour in range(8, 19, 2)]  # 8AM, 10AM, 12PM, 2PM, 4PM, 6PM
        
        for day in days:
            with st.expander(day.strftime("%A %m/%d"), expanded=True):
                cols = st.columns(len(time_slots))
                
                for i, time_slot in enumerate(time_slots):
                    slot_start = datetime.combine(day, time_slot)
                    slot_end = slot_start + timedelta(hours=2)
                    
                    with cols[i]:
                        # Check technician availability
                        available_techs = []
                        for tech in technicians:
                            tech_id = tech['EMPLOYEEID']
                            
                            # Check for overlapping appointments
                            is_busy = any(
                                a for a in appointments 
                                if a['TECHNICIANID'] == tech_id
                                and datetime.combine(day, a['SCHEDULED_TIME'].time()) < slot_end
                                and (datetime.combine(day, a['SCHEDULED_TIME'].time()) + timedelta(hours=2)) > slot_start
                            )
                            
                            if not is_busy:
                                available_techs.append(tech)
                        
                        # Display time slot (8-10 format)
                        slot_label = f"{time_slot.hour}-{(time_slot.hour+2)%12 or 12}"
                        
                        if available_techs:
                            if st.button(
                                slot_label,
                                key=f"slot_{day}_{time_slot}",
                                help="Available: " + ", ".join([t['ENAME'].split()[0] for t in available_techs])
                            ):
                                st.session_state.selected_slot = {
                                    'datetime': slot_start,
                                    'techs': available_techs
                                }
                        else:
                            st.button(
                                slot_label,
                                disabled=True,
                                key=f"slot_{day}_{time_slot}_disabled"
                            )
        
        # Handle slot selection for non-install services
        if 'selected_slot' in st.session_state:
            slot = st.session_state.selected_slot
            time_range = f"{slot['datetime'].hour}-{slot['datetime'].hour+2}"
            st.success(f"Selected: {slot['datetime'].strftime('%A %m/%d')} {time_range}")
            
            # Primary technician selection
            primary_tech = st.selectbox(
                "Primary Technician",
                options=[t['EMPLOYEEID'] for t in slot['techs']],
                format_func=lambda x: next(t['ENAME'] for t in slot['techs'] if t['EMPLOYEEID'] == x)
            )
            
            # Secondary technician selection (optional)
            secondary_techs = [t for t in slot['techs'] if t['EMPLOYEEID'] != primary_tech]
            secondary_tech = st.selectbox(
                "Additional Technician (Optional)",
                options=[""] + [t['EMPLOYEEID'] for t in secondary_techs],
                format_func=lambda x: next(t['ENAME'] for t in slot['techs'] if t['EMPLOYEEID'] == x) if x else "None"
            )
            
            notes = st.text_area("Service Notes")
            
            if st.button("Book Appointment"):
                try:
                    # Check availability again
                    existing = session.sql(f"""
                        SELECT * FROM appointments
                        WHERE technicianid = '{primary_tech}'
                        AND DATE(scheduled_time) = '{slot['datetime'].date()}'
                        AND HOUR(scheduled_time) = {slot['datetime'].hour}
                        AND sta_tus != 'cancelled'
                    """).collect()
                    
                    if existing:
                        st.error("Time slot no longer available")
                        del st.session_state.selected_slot
                        st.rerun()
                    
                    # Book primary technician
                    session.sql(f"""
                        INSERT INTO appointments (
                            appointmentid, customerid, technicianid, 
                            scheduled_time, service_type, notes, sta_tus
                        ) VALUES (
                            'APT{datetime.now().timestamp()}',
                            '{selected_customer_id}',
                            '{primary_tech}',
                            '{slot['datetime']}',
                            '{request_type}',
                            '{notes}',
                            'scheduled'
                        )
                    """).collect()
                    
                    # Book secondary technician if selected
                    if secondary_tech:
                        session.sql(f"""
                            INSERT INTO appointments (
                                appointmentid, customerid, technicianid, 
                                scheduled_time, service_type, notes, sta_tus
                            ) VALUES (
                                'APT{datetime.now().timestamp()}',
                                '{selected_customer_id}',
                                '{secondary_tech}',
                                '{slot['datetime']}',
                                '{request_type}-Assist',
                                '{notes}',
                                'scheduled'
                            )
                        """).collect()
                    
                    st.success(f"Appointment booked for {time_range}!")
                    del st.session_state.selected_slot
                    st.rerun()
                
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # --- Current Appointments Display ---
    st.subheader("Current Appointments ")
    current_appts = session.sql(f"""
        SELECT 
            a.appointmentid,
            c.name as customer_name,
            e.ename as technician_name,
            a.scheduled_time,
            a.service_type,
            a.sta_tus,
            a.notes
        FROM appointments a
        JOIN customers c ON a.customerid = c.customerid
        JOIN employees e ON a.technicianid = e.employeeid
        WHERE DATE(a.scheduled_time) BETWEEN '{start_date}' AND '{start_date + timedelta(days=120)}'
        ORDER BY a.scheduled_time
    """).collect()
    
    if current_appts:
        appt_data = []
        for appt in current_appts:
            start = appt['SCHEDULED_TIME']
            time_range = f"{start.hour}-{start.hour+2}"
            
            appt_data.append({
                "Date": start.strftime('%a %m/%d'),
                "Time": time_range,
                "Customer": appt['CUSTOMER_NAME'],
                "Technician": appt['TECHNICIAN_NAME'],
                "Service": appt['SERVICE_TYPE'],
                "Status": appt['STA_TUS']
            })
        
        st.dataframe(
            pd.DataFrame(appt_data),
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No appointments scheduled")
# Add Cancel button at the very bottom
        st.markdown("---")  # Visual separator
        if st.button("❌ Cancel Appointment", type="primary", use_container_width=True):
            if 'appointment_customer_id' in st.session_state:
                del st.session_state['appointment_customer_id']
                del st.session_state['appointment_customer_name']
            st.success("Appointment scheduling cancelled")
            st.rerun()
            
        else:
        # Normal appointment scheduling flow
         st.subheader("📅 Schedule New Appointment")

##########################################################################################
def reset_estimate_session_state():
    """Reset all estimate report session state variables to default values"""
    defaults = {
        # Equipment checks
        'HAS_COMMERCIAL': False,
        'HAS_RESIDENTIAL': False,
        'HAS_GAS_FURNACE': False,
        'HAS_COIL': False,
        'HAS_AIR_HANDLER': False,
        'HAS_CONDENSER': False,
        'HAS_HEAT_PUMP': False,
        'HAS_DUAL_FUEL_SYSTEM': False,
        'HAS_MINI_SPLIT_CONDENSER': False,
        'HAS_WATER_SOURCE_HP': False,
        'HAS_GEOTHERMAL': False,
        'HAS_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL': False,
        'HAS_ROOF_TOP_HEAT_PUMP': False,
        'HAS_ELECTRIC_WH': False,
        'HAS_GAS_WH': False,
        'HAS_HYBRID_WH': False,
        'HAS_MINI_SPLIT_WALL': False,
        'HAS_MINI_SPLIT_CEILING': False,
        'HAS_ELECTRIC_BOILER': False,
        'HAS_GAS_BOILER': False,
        'HAS_HUMIDIFIER': False,
        'HAS_UV_LIGHT': False,
        'HAS_THERMOSTAT': False,
        'HAS_EVR': False,
        'HAS_ZONE_CTRL': False,
        'HAS_THRU_THE_WALL_CONDENSER': False,
        'HAS_THRU_THE_WALL_PACKED_HEAT_PUMP': False,
        'HAS_WALK_IN_COOLER': False,
        'HAS_WALK_IN_FREEZER': False,
        'HAS_CONSOLE_HEAT_PUMP': False,
        'HAS_CONSOLE_FAN_COIL': False,
        'HAS_OTHER_EQUIPMENT': False,
        'HAS_CANVAS': False,
        'HAS_VANE': False,
        'HAS_FILTER_RACK': False,
        'HAS_PLENUM_BOX': False,
        'HAS_ELECTRIC_DISCONNECT_BOX': False,
        'HAS_THERMOSTAT_INSTALLATION': False,
        'HAS_NITROGEN_LEAK_TEST': False,
        'HAS_EZ_TRAP': False,
        'HAS_CONDENSATION_PVC': False,
        'HAS_CONDENSATION_PUMP': False,
        'HAS_SECONDARY_DRAIN_PAN': False,
        'HAS_CONDENSER_PAD': False,
        'HAS_CONDENSER_LEG': False,
        'HAS_WHIP': False,
        'HAS_LINE_SETS_FLUSHING': False,
        'HAS_LOCKING_CAP': False,
        'HAS_LS_INSULATION': False,
        'HAS_UV_RESISTANCE': False,
        'HAS_ADDITIONAL_FEATURES_OTHER': False,
        'HAS_LOW_VOLTAGE_WIRE': False,
        'HAS_HIGH_VOLTAGE_WIRE': False,
        'HAS_OBSTACLES': False,
        'NEEDS_CRANE': False,
        'NEEDS_TRAILER': False,
        'NEEDS_LADDER': False,
        'NEEDS_LIFT': False,
        'NEEDS_COUNTY_PERMIT': False,
        'NEEDS_COMMUNITY_PERMIT': False,
        'NEEDS_APARTMENT_PERMIT': False,
        'NEEDS_PARKING_PERMIT': False,
        'NEEDS_ELEVATOR_PERMIT': False,
        'NEEDS_FIRE_MARSHAL': False,
        'NEEDS_HANDLING': False,
        'NEEDS_TRAFFIC_CONTROL': False,
        'NEEDS_UTILITY_OPERATOR': False,
        'NEEDS_SIGN': False,
        'NEEDS_OTHER': False,
        'NEEDS_OTHER': False,
        'WORK_AREA_BASEMENT': False,
        'WORK_AREA_MAIN_FLOOR': False,
        'WORK_AREA_SECOND_FLOOR': False,
        'WORK_AREA_APARTMENT': False,
        'WORK_AREA_ATTIC': False,
        'WORK_AREA_CRAWL_SPACE': False,
        'WORK_AREA_OTHER': False,
        'INDOOR_ACCESS_LEFT': False,
        'INDOOR_ACCESS_RIGHT': False,
        'INDOOR_ACCESS_FRONT': False,
        'INDOOR_ACCESS_REAR': False,
        'INDOOR_ACCESS_DOOR_OPENING': False,
        'INDOOR_ACCESS_STAIRS': False,
        'INDOOR_ACCESS_CLOSET': False,
        'INDOOR_ACCESS_OTHER': False,
        'OUTDOOR_ACCESS_LEFT': False,
        'OUTDOOR_ACCESS_RIGHT': False,
        'OUTDOOR_ACCESS_FRONT': False,
        'OUTDOOR_ACCESS_REAR': False,
        'OUTDOOR_ACCESS_DOOR_OPENING': False,
        'OUTDOOR_ACCESS_STAIRS': False,
        'OUTDOOR_ACCESS_ROOF': False,
        'OUTDOOR_ACCESS_OTHER': False,
        'LINE_SETS_ACCESSIBLE': False,
        
        # Text fields
        'EXISTING_EQUIPMENT_NOTE': "",
        'ADDITIONAL_FEATURES_NOTE': "",
        'OBSTACLE_DESCRIPTION': "",
        'DUCTWORK_SUPPLY_SIZE_LENGTH': "",
        'DUCTWORK_SUPPLY_SIZE_WIDTH': "",
        'DUCTWORK_RETURN_LENGTH': "",
        'DUCTWORK_RETURN_WIDTH': "",
        'SPECIAL_REQUIREMENTS_NOTE': "",
        'WORK_AREA_NOTE': "",
        'INDOOR_ACCESS_WORKING_SPACE': "",
        'INDOOR_ACCESS_NOTE': "",
        'OUTDOOR_ACCESS_WORKING_SPACE': "",
        'OUTDOOR_ACCESS_NOTE': "",
        'LINE_SETS_SIZE': "",
        'LINE_SETS_CONDITION': "",
        'LINE_SETS_LENGTH': "",
        'LINE_SETS_REFRIGERANT_TYPE': "",
        'DESCRIPTION': "",
        'RECOMMENDATIONS': "",
        'CUSTOM_REFRIGERANT': "",
        'equipment_details': {},
        'new_equipment_details': {},
        'equipment_list': []
    }
       # Set all defaults
    for key, value in defaults.items():
        st.session_state[key] = value

########################################################################################## 
##########################################################################################



def estimate_report():
    session = get_session()
 
    # Initialize ALL session state variables with default values

    # Initialize session state if not already done
    if 'estimate_initialized' not in st.session_state:
        reset_estimate_session_state()  # This replaces the old initialization
        st.session_state.estimate_initialized = True
    
    # The rest of your estimate_report function remains the same
    session = get_session()
    st.title("📝 HVAC Estimate Report")
    

    # 1. TECHNICIAN & CUSTOMER INFO
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Technician:** {st.session_state.user_name}")
    with col2:
        st.markdown(f"**Date/Time:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    st.subheader("Customer Information")
    search_term = st.text_input("Search customer by name, phone, or address:", key="customer_search")
    
    customer_id = None
    customer_name = "Not selected"
    if search_term:
        customers = session.sql(f"""
            SELECT customerid, name, phone, address FROM customers
            WHERE name ILIKE '%{search_term}%'
               OR phone ILIKE '%{search_term}%'
               OR address ILIKE '%{search_term}%'
            ORDER BY name
            LIMIT 10
        """).collect()
        
        if customers:
            selected_customer = st.selectbox(
                "Select customer:",
                options=[c['CUSTOMERID'] for c in customers],
                format_func=lambda x: next(f"{c['NAME']} | {c['PHONE']} | {c['ADDRESS']}" 
                                         for c in customers if c['CUSTOMERID'] == x),
                key="customer_select"
            )
            customer_id = selected_customer
            customer_name = next(c['NAME'] for c in customers if c['CUSTOMERID'] == customer_id)
    
    st.markdown(f"**Selected Customer:** {customer_name}")
    

    
    with st.expander("Property Type"):
        cols = st.columns(2)
        property_type = {}
        with cols[0]:
            property_type['HAS_RESIDENTIAL'] = st.checkbox("Residential", key="HAS_RESIDENTIAL")
        with cols[1]:    
            property_type['HAS_COMMERCIAL'] = st.checkbox("Commercial", key="HAS_COMMERCIAL")
        
    
    # ======================
    # 2. EQUIPMENT TYPES
    # ======================
    
  
    with st.expander("Equipment Type"):

    # Organized in categories
        cols = st.columns(3)
        equipment_checks = {}
    
    # Heating/Cooling Systems
        with cols[0]:
            st.write("**Heating/Cooling**")
            equipment_checks['HAS_GAS_FURNACE'] = st.checkbox("Gas Furnace", key="HAS_GAS_FURNACE")
            equipment_checks['HAS_COIL'] = st.checkbox("Coil", key="HAS_COIL")
            equipment_checks['HAS_AIR_HANDLER'] = st.checkbox("Air Handler", key="HAS_AIR_HANDLER")
            equipment_checks['HAS_CONDENSER'] = st.checkbox("Condenser", key="HAS_CONDENSER")
            equipment_checks['HAS_HEAT_PUMP'] = st.checkbox("Heat Pump", key="HAS_HEAT_PUMP")
            equipment_checks['HAS_DUAL_FUEL_SYSTEM'] = st.checkbox("Dual Fuel System", key="HAS_DUAL_FUEL_SYSTEM")
            equipment_checks['HAS_MINI_SPLIT_CONDENSER'] = st.checkbox("Mini_Split Condenser", key="HAS_MINI_SPLIT_CONDENSER")
            equipment_checks['HAS_WATER_SOURCE_HP'] = st.checkbox("Water Source Heat Pump", key="HAS_WATER_SOURCE_HP")
            equipment_checks['HAS_GEOTHERMAL'] = st.checkbox("Geothermal Heat Pump", key="HAS_GEOTHERMAL")
            equipment_checks['HAS_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL'] = st.checkbox("Roof Top Gas Heat Electric Cool", key="HAS_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL")
            equipment_checks['HAS_ROOF_TOP_HEAT_PUMP'] = st.checkbox("Roof Top Heat Pump", key="HAS_ROOF_TOP_HEAT_PUMP")
            
        with cols[1]:
            st.write("**Water Heaters**")
            equipment_checks['HAS_ELECTRIC_WH'] = st.checkbox("Electric Water Heaters", key="HAS_ELECTRIC_WH")
            equipment_checks['HAS_GAS_WH'] = st.checkbox("Gas Water Heaters", key="HAS_GAS_WH")
            equipment_checks['HAS_HYBRID_WH'] = st.checkbox("Hybrid Water Heaters", key="HAS_HYBRID_WH")
        
            st.write("**Mini-Split Indoor**")
            equipment_checks['HAS_MINI_SPLIT_WALL'] = st.checkbox("Wall Mount", key="HAS_MINI_SPLIT_WALL")
            equipment_checks['HAS_MINI_SPLIT_CEILING'] = st.checkbox("Ceiling Mount", key="HAS_MINI_SPLIT_CEILING")
        
            st.write("**Boilers**")
            equipment_checks['HAS_ELECTRIC_BOILER'] = st.checkbox("Electric Boiler", key="HAS_ELECTRIC_BOILER")
            equipment_checks['HAS_GAS_BOILER'] = st.checkbox("Gas Boiler", key="HAS_GAS_BOILER")
            st.write("**Components**")
            equipment_checks['HAS_HUMIDIFIER'] = st.checkbox("Humidifier", key="HAS_HUMIDIFIER")
            equipment_checks['HAS_UV_LIGHT'] = st.checkbox("UV Light", key="HAS_UV_LIGHT")
            equipment_checks['HAS_THERMOSTAT'] = st.checkbox("Thermostat", key="HAS_THERMOSTAT")
        
        with cols[2]:
            st.write("**Controls**")
            equipment_checks['HAS_EVR'] = st.checkbox("EVR", key="HAS_EVR")
            equipment_checks['HAS_ZONE_CTRL'] = st.checkbox("Zone Control", key="HAS_ZONE_CTRL")
        
            st.write("**Other Types**")
            equipment_checks['HAS_THRU_THE_WALL_CONDENSER'] = st.checkbox("Thru-the-Wall Condenser", key='HAS_THRU_THE_WALL_CONDENSER')
            equipment_checks['HAS_THRU_THE_WALL_PACKED_HEAT_PUMP'] = st.checkbox("Thru-the-Wall Packed Heat Pump", key="HAS_THRU_THE_WALL_PACKED_HEAT_PUMP")
            equipment_checks['HAS_WALK_IN_COOLER'] = st.checkbox("Walk-in Cooler", key="HAS_WALK_IN_COOLER")
            equipment_checks['HAS_WALK_IN_FREEZER'] = st.checkbox("Walk-in Freezer", key="HAS_WALK_IN_FREEZER")
            equipment_checks['HAS_CONSOLE_HEAT_PUMP'] = st.checkbox("Console Heat Pump", key="HAS_CONSOLE_HEAT_PUMP")
            equipment_checks['HAS_CONSOLE_FAN_COIL'] = st.checkbox("Console Fan Coil", key="HAS_CONSOLE_FAN_COIL")

            equipment_checks['HAS_OTHER_EQUIPMENT'] = st.checkbox("Other Equipment", key="HAS_OTHER_EQUIPMENT")
            
    
      
        EXISTING_EQUIPMENT_NOTE = st.text_input("Note", key ='EXISTING_EQUIPMENT_NOTE')

    # ======================
    # 3. EXISTING EQUIPMENT (MODIFIED SECTION)
    # ======================
    
    # Initialize equipment details in session state
    if 'equipment_details' not in st.session_state:
        st.session_state.equipment_details = {}
    
    # Mapping of session state keys to human-readable names
    equipment_mapping = {
    'HAS_GAS_FURNACE': 'Gas Furnace',
    'HAS_COIL': 'Coil',
    'HAS_AIR_HANDLER': 'Air Handler',
    'HAS_CONDENSER': 'Condenser',
    'HAS_HEAT_PUMP': 'Heat Pump',
    'HAS_DUAL_FUEL_SYSTEM': 'Dual Fuel System',
    'HAS_MINI_SPLIT_CONDENSER': 'Mini_Split Condenser',
    'HAS_WATER_SOURCE_HP' : 'Water Source Heat Pump',
    'HAS_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL' :' Roof Top Gas Heat Electric Cool', 
    'HAS_ROOF_TOP_HEAT_PUMP' : 'Roof Top Heat Pump',
    'HAS_GEOTHERMAL': 'Geothermal Heat Pump',
    'HAS_ELECTRIC_WH': 'Electric Water Heaters',
    'HAS_GAS_WH': 'Gas Water Heater',
    'HAS_HYBRID_WH': 'Hybrid Water Heater',
    'HAS_MINI_SPLIT_WALL': 'Wall Mount',
    'HAS_MINI_SPLIT_CEILING': 'Ceiling Mount',
    'HAS_ELECTRIC_BOILER': 'Electric Boiler',
    'HAS_GAS_BOILER': "Gas Boiler",
    'HAS_HUMIDIFIER': 'Humidifier',
    'HAS_UV_LIGHT': 'UV Light',
    'HAS_THERMOSTAT': 'Thermostat',
    'HAS_EVR': 'EVR',
    'HAS_ZONE_CTRL': 'Zone Control',
    'HAS_THRU_THE_WALL_CONDENSER':'Thru-the-Wall Condenser ',
    'HAS_THRU_THE_WALL_PACKED_HEAT_PUMP': 'Thru-the-Wall Packed Heat Pump',        
    'HAS_WALK_IN_COOLER': 'Walk-in Cooler',
    'HAS_WALK_IN_FREEZER': 'Walk-in Freezer',
    'HAS_CONSOLE_HEAT_PUMP': 'Console Heat Pump',
    'HAS_CONSOLE_FAN_COIL': 'Console Fan Coil',
    'HAS_OTHER_EQUIPMENT': 'Other Equipment',
    }
    
    
    # Create collapsible sections for each equipment type
    for key, eq_name in equipment_mapping.items():
        if st.session_state.get(key, False):
            with st.expander(f"{eq_name} Details"):
                # Create columns for model/serial and picture
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    # Model and Serial Inputs
                    model = st.text_input(f"{eq_name} Model", 
                                         key=f"{key}_MODEL",
                                         value=st.session_state.equipment_details.get(key, {}).get('model', ''))
                    serial = st.text_input(f"{eq_name} Serial", 
                                          key=f"{key}_SERIAL",
                                          value=st.session_state.equipment_details.get(key, {}).get('serial', ''))
                
                with col2:
                    # Picture Upload
                    uploaded_file = st.file_uploader(f"Upload {eq_name} Picture", 
                                                    type=["jpg", "jpeg", "png"], 
                                                    key=f"{key}_UPLOAD")
                    pic_notes = st.text_input(f"Picture Notes", 
                                             key=f"{key}_PIC_NOTES",
                                             value=st.session_state.equipment_details.get(key, {}).get('pic_notes', ''))
                
                # Store in session state
                st.session_state.equipment_details[key] = {
                    'type': eq_name,
                    'model': model,
                    'serial': serial,
                    'uploaded_file': uploaded_file,
                    'pic_notes': pic_notes
                }
    
  
    
    # ======================
    # 4. INSTALLATION FEATURES
    # ======================
    with st.expander("Installation Features"):
    
        cols = st.columns(5)
        install_features = {}
    
        with cols[0]:
            st.write("**Components**")
            install_features['HAS_THERMOSTAT_INSTALLATION '] = st.checkbox("Thermostat Installation", key="HAS_THERMOSTAT_INSTALLATION")
            install_features['HAS_NITROGEN_LEAK_TEST '] = st.checkbox("Nitrogen Leak Test", key="HAS_NITROGEN_LEAK_TEST")
            install_features['HAS_EZ_TRAP '] = st.checkbox("EZ Trap", key="HAS_EZ_TRAP")
    
        with cols[1]:
            st.write("**Drainage**")
            install_features['HAS_CONDENSATION_PVC '] = st.checkbox("Condensation PVC Pipe", key="HAS_CONDENSATION_PVC")
            install_features['HAS_CONDENSATION_PUMP'] = st.checkbox("Condensation Pump", key="HAS_CONDENSATION_PUMP")
            install_features['HAS_SECONDARY_DRAIN_PAN'] = st.checkbox("Secondary Drain Pan", key="HAS_SECONDARY_DRAIN_PAN")
            install_features['HAS_ELECTRIC_DISCONNECT_BOX'] = st.checkbox("Electric Disconnect Box", key="HAS_ELECTRIC_DISCONNECT_BOX")

    
        with cols[2]:
            st.write("**Condenser**")
            install_features['HAS_CONDENSER_PAD'] = st.checkbox("Condenser Pad", key="HAS_CONDENSER_PAD")
            install_features['HAS_CONDENSER_LEG'] = st.checkbox("Condenser Leg", key="HAS_CONDENSER_LEG")
            install_features['HAS_WHIP'] = st.checkbox("Whip", key="HAS_WHIP")
    
            install_features['HAS_CANVAS'] = st.checkbox("Canvas", key="HAS_CANVAS")
            install_features['HAS_VANE'] = st.checkbox("Vane", key="HAS_VANE")
            install_features['HAS_FILTER_RACK'] = st.checkbox("Filter Rack", key="HAS_FILTER_RACK")
            install_features['HAS_PLENUM_BOX'] = st.checkbox("Plenum Box", key="HAS_PLENUM_BOX")



        with cols[3]:
            st.write("**Line Sets**")
            install_features['HAS_LINE_SETS_FLUSHING'] = st.checkbox("Line Sets Flushing", key="HAS_LINE_SETS_FLUSHING")
            install_features['HAS_LOCKING_CAP'] = st.checkbox("Locking Cap", key="HAS_LOCKING_CAP")
            install_features['HAS_LS_INSULATION'] = st.checkbox("Line Set Insulation", key="HAS_LS_INSULATION")
            install_features['HAS_UV_RESISTANCE'] = st.checkbox("UV Resistance", key="HAS_UV_RESISTANCE")
        with cols[4]:
            
            install_features['HAS_HIGH_VOLTAGE_WIRE'] = st.checkbox("High-Voltage Wire", key="HAS_HIGH_VOLTAGE_WIRE")
            install_features['HAS_LOW_VOLTAGE_WIRE'] = st.checkbox("Low-Voltage Wire", key="HAS_LOW_VOLTAGE_WIRE")
            install_features['HAS_ADDITIONAL_FEATURES_OTHER'] = st.checkbox("Additional Features", key="HAS_ADDITIONAL_FEATURES_OTHER")
   
        additional_features_note = st.text_area("Notes", key="ADDITIONAL_FEATURES_NOTE")

        st.markdown("---")
    
    # ======================
    # 5. SYSTEM DETAILS
    # ======================

    with st.expander("Ductwork"):
    # Supply Duct Section
        col1, col2, col3, col4 = st.columns([0.5, 0.1, 0.5, 0.5])
        with col1:
            ductwork_supply_size_length = st.text_input("Supply Length", 
                                              key="DUCTWORK_SUPPLY_SIZE_LENGTH", 
                                              max_chars=4,
                                             help="Enter length in inches")


            ductwork_return_length = st.text_input("Return Length", 
                                              key="DUCTWORK_RETURN_LENGTH", 
                                              max_chars=4,                                                        
                                             help="Enter length in inches")

            
        with col2:
            st.markdown("<div style='tet-align: center; padding-top: 2rem;'>×</div>", 
                   unsafe_allow_html=True)
            
            st.markdown("<div style='tet-align: center; padding-top: 4rem;'>×</div>", 
                   unsafe_allow_html=True)
            
        with col3:
            ductwork_supply_size_width = st.text_input("Supply Width", 
                                             key="DUCTWORK_SUPPLY_SIZE_WIDTH", 
                                             max_chars=3,
                                             help="Enter width in inches")
            

            ductwork_return_width = st.text_input("Return Width", 
                                             key="DUCTWORK_RETURN_WIDTH", 
                                             max_chars=3,
                                             help="Enter width in inches")
        with col4:
            st.markdown("<div style='text-align: left; padding-top: 2rem;'>inches</div>", 
                   unsafe_allow_html=True)
            st.markdown("<div style='text-align: left; padding-top: 4rem;'>inches</div>", 
                   unsafe_allow_html=True)
    # Display combined size
    if ductwork_supply_size_length or ductwork_supply_size_width:
        st.write(f"**Supply Size:** {ductwork_supply_size_length or '0'} × {ductwork_supply_size_width or '0'} inches")

    # Display combined size
    if ductwork_return_length or ductwork_return_width:
        st.write(f"**Return Size:** {ductwork_return_length or '0'} × {ductwork_return_width or '0'} inches")
    
    

    

    #===============
    with st.expander("Line Sets"):
    # Create two columns for better layout
        col1, col2 = st.columns(2)
    
        with col1:
            LINE_SETS_SIZE = st.text_input("Size", key="LINE_SETS_SIZE")
            line_sets_accessible = st.checkbox("Accessible", key="LINE_SETS_ACCESSIBLE")
            line_sets_condition = st.text_input("Condition", key="LINE_SETS_CONDITION")
    
        with col2:
            line_sets_length = st.text_input("Length", key="LINE_SETS_LENGTH")
        
        # Refrigerant type selection
            refrigerant_options = [
            "", "R-22", "R-410A", "R-32", "R-454B", 
            "R-134a", "R-407C", "R-404A", "R-507", "Other"
            ]
        
        # Get current value from session state
            current_value = st.session_state.get('LINE_SETS_REFRIGERANT_TYPE', "")
        
        # Convert to string if it's not already
            if not isinstance(current_value, str):
                try:
                    current_value = str(current_value)
                except:
                    current_value = ""
        
        # Find the index of the current refrigerant in the options
            try:
                index = refrigerant_options.index(current_value)
            except ValueError:
                index = 0

            selected_refrigerant = st.selectbox(
                "Refrigerant Type",
                options=refrigerant_options,
                index=index,
                key="refrigerant_selectbox"
            )
        
        # Update session state with the selection
            st.session_state['LINE_SETS_REFRIGERANT_TYPE'] = selected_refrigerant
        
        # If "Other" is selected, show text input for custom refrigerant
            if selected_refrigerant == "Other":
                custom_refrigerant = st.text_input("Specify Refrigerant Type", 
                                              value=st.session_state.get('CUSTOM_REFRIGERANT', ""),
                                              key="CUSTOM_REFRIGERANT")
                if custom_refrigerant:
                    st.session_state['LINE_SETS_REFRIGERANT_TYPE'] = custom_refrigerant
         
    # ======================
    # 6. WORKING CONDITIONS
    # ======================
    
    with st.expander("Obstacles"):
        has_obstacles = st.checkbox("Obstacles Present?", key="HAS_OBSTACLES")
        obstacle_description = st.text_area("Obstacle Description", key="OBSTACLE_DESCRIPTION")
    
    with st.expander("Special Requirements"):
        cols = st.columns(3)
        special_reqs = {}
        with cols[0]:
            special_reqs['NEEDS_CRANE'] = st.checkbox("Crane", key="NEEDS_CRANE")
            special_reqs['NEEDS_TRAILER'] = st.checkbox("Trailer", key="NEEDS_TRAILER")
            special_reqs['NEEDS_LADDER'] = st.checkbox("Ladder", key="NEEDS_LADDER")
            special_reqs['NEEDS_LIFT'] = st.checkbox("Lift", key="NEEDS_LIFT")

        with cols[1]:
            
            special_reqs['NEEDS_HANDLING'] = st.checkbox("Handling", key="NEEDS_HANDLING")
            special_reqs['NEEDS_TRAFFIC_CONTROL'] = st.checkbox("Traffic Control", key="NEEDS_TRAFFIC_CONTROL")
        
            special_reqs['NEEDS_UTILITY_OPERATOR'] = st.checkbox("Utility Operator", key="NEEDS_UTILITY_OPERATOR")
            special_reqs['NEEDS_SIGN'] = st.checkbox("Sign", key="NEEDS_SIGN")
        with cols[2]:
            special_reqs['NEEDS_OTHER'] = st.checkbox("Other", key="NEEDS_OTHER")
            SPECIAL_REQUIREMENTS_NOTE = st.text_area("Note", key="SPECIAL_REQUIREMENTS_NOTE")
    
    with st.expander("Working Area"):
        cols = st.columns(3)
        work_areas = {}
        with cols[0]:
            work_areas['WORK_AREA_BASEMENT'] = st.checkbox("Basement", key="WORK_AREA_BASEMENT")
            work_areas['WORK_AREA_MAIN_FLOOR'] = st.checkbox("Main Floor", key="WORK_AREA_MAIN_FLOOR")
        with cols[1]:
            work_areas['WORK_AREA_SECOND_FLOOR '] = st.checkbox("Second Floor", key="WORK_AREA_SECOND_FLOOR")
            work_areas['WORK_AREA_APARTMENT'] = st.checkbox("Apartment", key="WORK_AREA_APARTMENT")
        with cols[2]:
            work_areas['WORK_AREA_ATTIC'] = st.checkbox("Attic", key="WORK_AREA_ATTIC")
            work_areas['WORK_AREA_CRAWL_SPACE'] = st.checkbox("Crawl Space", key="WORK_AREA_CRAWL_SPACE")
            work_areas['WORK_AREA_OTHER'] = st.checkbox("Other", key="WORK_AREA_OTHER")
    
    # ======================
    # 7. ACCESSIBILITY
    # ======================
    
    with st.expander("Indoor Access"):
        cols = st.columns(4)
        indoor_access = {}
        with cols[0]:
            indoor_access['INDOOR_ACCESS_LEFT'] = st.checkbox("Left", key="INDOOR_ACCESS_LEFT")
            indoor_access['INDOOR_ACCESS_FRONT'] = st.checkbox("Front", key="INDOOR_ACCESS_FRONT")
        with cols[1]:
            indoor_access['INDOOR_ACCESS_RIGHT'] = st.checkbox("Right", key="INDOOR_ACCESS_RIGHT")
            indoor_access['INDOOR_ACCESS_REAR'] = st.checkbox("Rear", key="INDOOR_ACCESS_REAR")
        with cols[2]:
            indoor_access['INDOOR_ACCESS_DOOR_OPENING'] = st.checkbox("Door Opening", key="INDOOR_ACCESS_DOOR_OPENING")
            indoor_access['INDOOR_ACCESS_STAIRS'] = st.checkbox("Stairs", key="INDOOR_ACCESS_STAIRS")
        with cols[3]:
            indoor_access['INDOOR_ACCESS_CLOSET'] = st.checkbox("Closet", key="INDOOR_ACCESS_CLOSET")
            indoor_access['INDOOR_ACCESS_OTHER'] = st.checkbox("Other", key="INDOOR_ACCESS_OTHER")
        
        indoor_workspace = st.text_input("Working Space (SF)", key="INDOOR_ACCESS_WORKING_SPACE")
        indoor_notes = st.text_area("Notes", key="INDOOR_ACCESS_NOTE")
    
    with st.expander("Outdoor Access"):
        cols = st.columns(4)
        outdoor_access = {}
        with cols[0]:
            outdoor_access['OUTDOOR_ACCESS_LEFT'] = st.checkbox("Left", key="OUTDOOR_ACCESS_LEFT")
            outdoor_access['OUTDOOR_ACCESS_FRONT'] = st.checkbox("Front", key="OUTDOOR_ACCESS_FRONT")
        with cols[1]:
            outdoor_access['OUTDOOR_ACCESS_RIGHT'] = st.checkbox("Right", key="OUTDOOR_ACCESS_RIGHT")
            outdoor_access['OUTDOOR_ACCESS_REAR'] = st.checkbox("Rear", key="OUTDOOR_ACCESS_REAR")
        with cols[2]:
            outdoor_access['OUTDOOR_ACCESS_DOOR_OPENING'] = st.checkbox("Door Opening", key="OUTDOOR_ACCESS_DOOR_OPENING")
            outdoor_access['OUTDOOR_ACCESS_STAIRS'] = st.checkbox("Stairs", key="OUTDOOR_ACCESS_STAIRS")
        with cols[3]:
            outdoor_access['OUTDOOR_ACCESS_ROOF'] = st.checkbox("Roof Access", key="OUTDOOR_ACCESS_ROOF")
            outdoor_access['OUTDOOR_ACCESS_OTHER'] = st.checkbox("Other", key="OUTDOOR_ACCESS_OTHER")
        
        outdoor_workspace = st.text_input("Working Space (SF)", key="OUTDOOR_ACCESS_WORKING_SPACE")
        outdoor_notes = st.text_area("Notes", key="OUTDOOR_ACCESS_NOTE")
    
    
    # ======================
    # 8. PERMITS REQUIRED
    # ======================
    with st.expander("Permits"):
        cols = st.columns(4)
        permits = {}
    with cols[0]:
        permits['NEEDS_COUNTY_PERMIT'] = st.checkbox("County", key="NEEDS_COUNTY_PERMIT")
        permits['NEEDS_COMMUNITY_PERMIT'] = st.checkbox("Community", key="NEEDS_COMMUNITY_PERMIT")
    with cols[1]:
        permits['NEEDS_APARTMENT_PERMIT'] = st.checkbox("Apartment", key="NEEDS_APARTMENT_PERMIT")
        permits['NEEDS_PARKING_PERMIT'] = st.checkbox("Parking", key="NEEDS_PARKING_PERMIT")
    with cols[2]:
        permits['ELEVATOR'] = st.checkbox("Elevator", key="NEEDS_ELEVATOR_PERMIT")
        permits['FIRE'] = st.checkbox("Fire Marshal", key="NEEDS_FIRE_MARSHAL")

    
    # ======================
    # 9. NOTES & RECOMMENDATIONS
    # ======================
    st.subheader("Notes & Recommendations")
    description = st.text_area("System Description", height=150, key="DESCRIPTION")
    recommendations = st.text_area("Recommendations", height=150, key="RECOMMENDATIONS")
    



    # ======================
# 10. SAVE ESTIMATE (DEBUGGED VERSION)
# ======================
    if st.button("💾 Save Estimate", type="primary", key="save_estimate"):
    # Validate only absolutely required fields
        if not customer_id:
            st.error("❌ Please select a customer first")
            return

 

        try:
        # Generate report ID
            report_id = f"EST-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare equipment data (ensure exactly 4 entries)
            equipment_list = st.session_state.get('equipment_list', [])
            equipment_data = equipment_list.copy()
            while len(equipment_data) < 4:
                equipment_data.append({"model": None, "serial": None})

        # Helper function to handle null/empty values
            def get_value(key, default=None):
                val = st.session_state.get(key, default)
                if val in ["", None]:
                    return None
                return val


            params = [
                report_id,  # REPORT_ID
            st.session_state.user_name,  # TECHNICIAN_NAME
            customer_id,  # CUSTOMER_ID
            customer_name,  # CUSTOMER_NAME
            current_timestamp,  # INSPECTION_DATETIME
            st.session_state.get('HAS_COMMERCIAL', False),
            st.session_state.get('HAS_RESIDENTIAL', False),
            st.session_state.get('HAS_GAS_FURNACE', False),
            st.session_state.get('HAS_COIL', False),
            st.session_state.get('HAS_AIR_HANDLER', False),
            st.session_state.get('HAS_CONDENSER', False),
            st.session_state.get('HAS_HEAT_PUMP', False),
            st.session_state.get('HAS_DUAL_FUEL_SYSTEM', False),
            st.session_state.get('HAS_MINI_SPLIT_CONDENSER', False),
            st.session_state.get('HAS_WATER_SOURCE_HP', False),
            st.session_state.get('HAS_GEOTHERMAL', False),
            st.session_state.get('HAS_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL', False),
            st.session_state.get('HAS_ROOF_TOP_HEAT_PUMP', False),
            st.session_state.get('HAS_ELECTRIC_WH', False),
            st.session_state.get('HAS_GAS_WH', False),
            st.session_state.get('HAS_HYBRID_WH', False),
            st.session_state.get('HAS_MINI_SPLIT_WALL', False),
            st.session_state.get('HAS_MINI_SPLIT_CEILING', False),
            st.session_state.get('HAS_ELECTRIC_BOILER', False),
            st.session_state.get('HAS_GAS_BOILER', False),
            st.session_state.get('HAS_HUMIDIFIER', False),
            st.session_state.get('HAS_UV_LIGHT', False),
            st.session_state.get('HAS_THERMOSTAT', False),
            st.session_state.get('HAS_EVR', False),
            st.session_state.get('HAS_ZONE_CTRL', False),
            st.session_state.get('HAS_THRU_THE_WALL_CONDENSER', False),
            st.session_state.get('HAS_THRU_THE_WALL_PACKED_HEAT_PUMP', False),
            st.session_state.get('HAS_WALK_IN_COOLER', False),
            st.session_state.get('HAS_WALK_IN_FREEZER', False),
            st.session_state.get('HAS_CONSOLE_HEAT_PUMP', False),
            st.session_state.get('HAS_CONSOLE_FAN_COIL', False),
            st.session_state.get('HAS_OTHER_EQUIPMENT', False),
            st.session_state.get('EXISTING_EQUIPMENT_NOTE'),



            
            st.session_state.get('HAS_ELECTRIC_DISCONNECT_BOX', False),
            st.session_state.get('HAS_THERMOSTAT_INSTALLATION', False),
            st.session_state.get('HAS_NITROGEN_LEAK_TEST', False),
            st.session_state.get('HAS_EZ_TRAP', False),
            st.session_state.get('HAS_CONDENSATION_PVC', False),
            st.session_state.get('HAS_CONDENSATION_PUMP', False),
            st.session_state.get('HAS_SECONDARY_DRAIN_PAN', False),
            st.session_state.get('HAS_CONDENSER_PAD', False),
            st.session_state.get('HAS_CANVAS', False),
            st.session_state.get('HAS_VANE', False),
            st.session_state.get('HAS_FILTER_RACK', False),
            st.session_state.get('HAS_PLENUM_BOX', False),

            st.session_state.get('HAS_WHIP', False),
            st.session_state.get('HAS_LINE_SETS_FLUSHING', False),
            st.session_state.get('HAS_LOCKING_CAP', False),
            st.session_state.get('HAS_LS_INSULATION', False),
            st.session_state.get('HAS_UV_RESISTANCE', False),
            st.session_state.get('HAS_ADDITIONAL_FEATURES_OTHER', False),  
            st.session_state.get('ADDITIONAL_FEATURES_NOTE'), 
            st.session_state.get('HAS_LOW_VOLTAGE_WIRE', False),
            st.session_state.get('HAS_HIGH_VOLTAGE_WIRE', False),
            st.session_state.get('HAS_OBSTACLES', False),
            st.session_state.get('OBSTACLE_DESCRIPTION'),  # obstacle_descriptionRIPTION
            st.session_state.get('DUCTWORK_SUPPLY_SIZE_LENGTH'),
            st.session_state.get('DUCTWORK_SUPPLY_SIZE_WIDTH'),
            st.session_state.get('DUCTWORK_RETURN_LENGTH'),
            st.session_state.get('DUCTWORK_RETURN_WIDTH'),
            st.session_state.get('NEEDS_CRANE', False),
            st.session_state.get('NEEDS_TRAILER', False),
            st.session_state.get('NEEDS_LADDER', False),
            st.session_state.get('NEEDS_LIFT', False),
            st.session_state.get('NEEDS_COUNTY_PERMIT', False),
            st.session_state.get('NEEDS_COMMUNITY_PERMIT', False),
            st.session_state.get('NEEDS_APARTMENT_PERMIT', False),
            st.session_state.get('NEEDS_PARKING_PERMIT', False),
            st.session_state.get('NEEDS_ELEVATOR_PERMIT', False),
            st.session_state.get('NEEDS_FIRE_MARSHAL', False),
            st.session_state.get('NEEDS_HANDLING', False),
            st.session_state.get('NEEDS_TRAFFIC_CONTROL', False),
            st.session_state.get('NEEDS_UTILITY_OPERATOR', False),
            st.session_state.get('NEEDS_SIGN', False),
            st.session_state.get('NEEDS_OTHER', False),
            st.session_state.get('SPECIAL_REQUIREMENTS_NOTE'),  # SPECIAL_REQUIREMENTS_NOTE


   

                
            st.session_state.get('WORK_AREA_BASEMENT', False),
            st.session_state.get('WORK_AREA_MAIN_FLOOR', False),
            st.session_state.get('WORK_AREA_SECOND_FLOOR', False),
            st.session_state.get('WORK_AREA_APARTMENT', False),
            st.session_state.get('WORK_AREA_ATTIC', False),
            st.session_state.get('WORK_AREA_CRAWL_SPACE', False),
            st.session_state.get('WORK_AREA_OTHER', False),
            st.session_state.get('WORK_AREA_NOTE'),  # WORK_AREA_NOTE
            st.session_state.get('INDOOR_ACCESS_LEFT', False),
            st.session_state.get('INDOOR_ACCESS_RIGHT', False),
            st.session_state.get('INDOOR_ACCESS_FRONT', False),
            st.session_state.get('INDOOR_ACCESS_REAR', False),
            st.session_state.get('INDOOR_ACCESS_WORKING_SPACE'),  # INDOOR_ACCESS_WORKING_SPACE
            st.session_state.get('INDOOR_ACCESS_DOOR_OPENING', False),
            st.session_state.get('INDOOR_ACCESS_STAIRS', False),
            st.session_state.get('INDOOR_ACCESS_CLOSET', False),
            st.session_state.get('INDOOR_ACCESS_OTHER', False),
            st.session_state.get('INDOOR_ACCESS_NOTE'),  # INDOOR_ACCESS_NOTE

            st.session_state.get('OUTDOOR_ACCESS_LEFT', False),
            st.session_state.get('OUTDOOR_ACCESS_RIGHT', False),
            st.session_state.get('OUTDOOR_ACCESS_FRONT', False),
            st.session_state.get('OUTDOOR_ACCESS_REAR', False),
            st.session_state.get('OUTDOOR_ACCESS_WORKING_SPACE'),  # OUTDOOR_ACCESS_WORKING_SPACE
            st.session_state.get('OUTDOOR_ACCESS_DOOR_OPENING', False),
            st.session_state.get('OUTDOOR_ACCESS_STAIRS', False),
            st.session_state.get('OUTDOOR_ACCESS_ROOF', False),
            st.session_state.get('OUTDOOR_ACCESS_OTHER', False),
            st.session_state.get('OUTDOOR_ACCESS_NOTE'),  # OUTDOOR_ACCESS_NOTE



            st.session_state.get('LINE_SETS_SIZE'),  # LINE_SETS_SIZE
            st.session_state.get('LINE_SETS_CONDITION'),  # LINE_SETS_CONDITION
            st.session_state.get('LINE_SETS_LENGTH'),  # LINE_SETS_LENGTH
            st.session_state.get('LINE_SETS_ACCESSIBLE', False),
            st.session_state.get('LINE_SETS_REFRIGERANT_TYPE'),  # LINE_SETS_REFRIGERANT_TYPE
            st.session_state.get('DESCRIPTION'),  # DESCRIPTION
            st.session_state.get('RECOMMENDATIONS'),  # RECOMMENDATIONS
            current_timestamp  # CREATED_AT
            ]

        # Verify parameter count
            if len(params) != 117:
                st.error(f"CRITICAL: Parameter count mismatch (expected 116, got {len(params)})")
                return
                        # Save equipment pictures
            for key, details in st.session_state.equipment_details.items():
                if details.get('uploaded_file'):
                    try:
                        # Process image
                        img = Image.open(details['uploaded_file'])
                        img = ImageOps.fit(img, (800, 800))
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=85)
                        encoded_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        
                        # Save to database
                        session.sql(f"""
                            INSERT INTO EQUIPMENT_PICTURES (
                                PICTURE_ID, CUSTOMERID, EQUIPMENT_TYPE,
                                MODEL, SERIAL, PICTURE_DATA_TEXT, NOTES
                            ) VALUES (
                                'PIC{datetime.now().timestamp()}',
                                '{customer_id}',
                                '{details['type']}',
                                '{details['model']}',
                                '{details['serial']}',
                                '{encoded_image}',
                                '{details['pic_notes']}'
                            )
                        """).collect()
                    except Exception as e:
                        st.error(f"Error saving {details['type']} picture: {str(e)}")
     


        # Execute with parameter substitution
            session.sql("""
                INSERT INTO ESTIMATE_REPORTS VALUES (
                    /* 1-5 */ ?, ?, ?, ?, ?,
                    /* 6-10 */ ?, ?, ?, ?, ?,
                    /* 11-15 */ ?, ?, ?, ?, ?,
                    /* 16-20 */ ?, ?, ?, ?, ?,
                    /* 21-25 */ ?, ?, ?, ?, ?,
                    /* 26-30 */ ?, ?, ?, ?, ?,
                    /* 31-35 */ ?, ?, ?, ?, ?,
                    /* 36-40 */ ?, ?, ?, ?, ?,
                    /* 41-45 */ ?, ?, ?, ?, ?,
                /* 46-50 */ ?, ?, ?, ?, ?,
                /* 51-55 */ ?, ?, ?, ?, ?,
                /* 56-60 */ ?, ?, ?, ?, ?,
                /* 61-65 */ ?, ?, ?, ?, ?,
                /* 66-70 */ ?, ?, ?, ?, ?,
                /* 71-75 */ ?, ?, ?, ?, ?,
                /* 76-80 */ ?, ?, ?, ?, ?,
                /* 81-85 */ ?, ?, ?, ?, ?,
                /* 86-90 */ ?, ?, ?, ?, ?,
                /* 91-95 */ ?, ?, ?, ?, ?,
                /* 96-100 */ ?, ?, ?, ?, ?,
                /* 101-105 */ ?, ?, ?, ?, ?,
                /* 106-110 */ ?, ?, ?, ?, ?,
                /* 111-115 */ ?, ?, ?,?,?,
                /* 116 */ ?,?
                 )
            """, params=params).collect()
        
            st.success(f"✅ Estimate {report_id} saved successfully!")
            st.balloons()
        
        # Reset form
            if 'equipment_list' in st.session_state:
                del st.session_state['equipment_list']
            st.rerun()
        
        except Exception as e:
            st.error(f"🚨 Error saving estimate: {str(e)}")
########################
##########################################################################################   
##########################################################################################       
def customer_info():
    st.subheader("Customer Information")
    session = get_session()
    
    # Custom CSS with enhanced styling
    st.markdown("""
    <style>
        .search-box {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .customer-card {
            background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            margin-bottom: 25px;
            color: white;
        }
        .estimate-card {
            background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .picture-card {
            background: white;
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            margin-bottom: 15px;
        }
        .clickable {
            color: #0068c9 !important;
            text-decoration: none !important;
            font-weight: bold !important;
        }
        .clickable:hover {
            text-decoration: underline !important;
        }
        .tab-content {
            padding: 15px;
            border-radius: 8px;
            background: rgba(255,255,255,0.9);
            margin-top: 10px;
        }
        .info-item {
            margin-bottom: 8px;
        }
        .section-header {
            color: #6a11cb;
            border-bottom: 2px solid #f0f2f6;
            padding-bottom: 8px;
            margin-top: 25px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Search functionality
    with st.form("customer_search_form"):
        st.markdown('<div class="search-box">', unsafe_allow_html=True)
        search_term = st.text_input("✨ Search by Name, Phone, or Address", 
                                  key="customer_search_info",
                                  placeholder="Type customer details...")
        search_clicked = st.form_submit_button("🔍 Search", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    if search_term and search_clicked:
        try:
            # Search customers
            customers = session.sql(f"""
                SELECT * FROM CUSTOMERS
                WHERE NAME ILIKE '%{search_term}%'
                   OR PHONE ILIKE '%{search_term}%'
                   OR ADDRESS ILIKE '%{search_term}%'
                ORDER BY NAME
                LIMIT 10
            """).collect()
            
            if customers:
                # Convert rows to dictionaries
                customer_dicts = []
                for row in customers:
                    customer_dict = {field: getattr(row, field) for field in row._fields}
                    customer_dicts.append(customer_dict)
                
                # Customer selection
                selected_customer = st.selectbox(
                    "Select Customer",
                    options=[c['CUSTOMERID'] for c in customer_dicts],
                    format_func=lambda x: next(f"🌟 {c['NAME']} | 📞 {c['PHONE']} | 🏠 {c['ADDRESS']}" 
                                            for c in customer_dicts if c['CUSTOMERID'] == x),
                    key="customer_select_info"
                )
                
                customer = next(c for c in customer_dicts if c['CUSTOMERID'] == selected_customer)
                
                # Build complete address with Google Maps link
                address_parts = [
                    customer['ADDRESS'],
                    customer.get('UNIT'),
                    customer.get('CITY'),
                    customer.get('STATE'),
                    customer.get('ZIPCODE')
                ]
                address_parts = [part for part in address_parts if part and str(part).strip() not in ['', 'None', 'N/A']]
                full_address = ', '.join(address_parts)
                maps_url = f"https://www.google.com/maps/search/?api=1&query={full_address.replace(' ', '+')}"
                
                # Customer info card with clickable elements
                st.markdown('<div class="customer-card">', unsafe_allow_html=True)
                st.markdown(f'<h3 style="margin-top: 0;">👤 {customer["NAME"]}</h3>', unsafe_allow_html=True)
                
                # Left column
                col1, col2 = st.columns(2)
                with col1:
                    if customer['PHONE']:
                        phone = customer['PHONE'].replace('-', '')
                        st.markdown(f'<div class="info-item">📱 <strong>Phone:</strong> <a href="tel:{phone}" class="clickable">{customer["PHONE"]}</a></div>', unsafe_allow_html=True)
                    if customer.get('EMAIL'):
                        st.markdown(f'<div class="info-item">📧 <strong>Email:</strong> <a href="mailto:{customer["EMAIL"]}" class="clickable">{customer["EMAIL"]}</a></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="info-item">🏠 <strong>Address:</strong> <a href="{maps_url}" target="_blank" class="clickable">{full_address}</a></div>', unsafe_allow_html=True)
                
                # Right column
                with col2:
                    if customer.get('LOCK_BOX_CODE'):
                        st.markdown(f'<div class="info-item">🔒 <strong>Lock Box:</strong> {customer["LOCK_BOX_CODE"]}</div>', unsafe_allow_html=True)
                    if customer.get('SAFETY_ALARM'):
                        st.markdown(f'<div class="info-item">🚨 <strong>Safety Alarm:</strong> {customer["SAFETY_ALARM"]}</div>', unsafe_allow_html=True)
                    if customer.get('UNIT_LOCATION'):
                        st.markdown(f'<div class="info-item">🏢 <strong>Unit Location:</strong> {customer["UNIT_LOCATION"]}</div>', unsafe_allow_html=True)
                    if customer.get('ACCESSIBILITY_LEVEL'):
                        st.markdown(f'<div class="info-item"><strong>Accessibility:</strong> {customer["ACCESSIBILITY_LEVEL"]}</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
                

                
                # Estimate Reports Section
                st.markdown('<h3 class="section-header">📋 Estimate Reports</h3>', unsafe_allow_html=True)
                
                try:
                    estimates = session.sql(f"""
                        SELECT * FROM ESTIMATE_REPORTS
                        WHERE CUSTOMER_ID = '{selected_customer}'
                        ORDER BY INSPECTION_DATETIME DESC
                    """).collect()
                    
                    if estimates:
                        # Create tabs for each estimate
                        tab_names = [f"Estimate {i+1} {e['INSPECTION_DATETIME'].strftime('%m/%d/%Y')}" 
                                    for i, e in enumerate(estimates)]
                        tabs = st.tabs(tab_names)
                        
                        for i, (tab, estimate) in enumerate(zip(tabs, estimates)):
                            with tab:
                                est_dict = {field: getattr(estimate, field) for field in estimate._fields}
                                
                                st.markdown(f"""
                                    <div class="estimate-card">
                                        <h4>📅 {est_dict['INSPECTION_DATETIME'].strftime('%B %d, %Y')}</h4>
                                        <p><strong>Technician:</strong> {est_dict['TECHNICIAN_NAME']}</p>
                                    </div>
                                """, unsafe_allow_html=True)
                                
                                # Helper function to display only non-empty fields
                                def display_if_exists(label, value, prefix="- "):
                                    if value and str(value).strip() not in ['', 'None', 'N/A']:
                                        st.write(f"{prefix}{label}: {value}")
                                
                                # Equipment Present Section
                                with st.expander("🔧 Equipment Present", expanded=True):
                                    cols = st.columns(2)
                                    equipment_fields = [
                                        ('Gas Furnace', 'HAS_GAS_FURNACE'),
                                        ('Coil', 'HAS_COIL'),
                                        ('Air Handler', 'HAS_AIR_HANDLER'),
                                        ('Condenser', 'HAS_CONDENSER'),
                                        ('Heat Pump', 'HAS_HEAT_PUMP'),
                                        ('Dual Fuel System', 'HAS_DUAL_FUEL_SYSTEM'),
                                        ('Electric Water Heater', 'HAS_ELECTRIC_WH'),
                                        ('Gas Water Heater', 'HAS_GAS_WH'),
                                        ('Humidifier', 'HAS_HUMIDIFIER'),
                                        ('UV Light', 'HAS_UV_LIGHT'),
                                        ('Thermostat', 'HAS_THERMOSTAT')
                                    ]
                                    
                                    half = len(equipment_fields) // 2
                                    with cols[0]:
                                        for label, field in equipment_fields[:half]:
                                            if est_dict[field]:
                                                st.write(f"- {label}")
                                    with cols[1]:
                                        for label, field in equipment_fields[half:]:
                                            if est_dict[field]:
                                                st.write(f"- {label}")
                                
                                # Existing Equipment Details
                                existing_equip = []
                                for j in range(1,5):
                                    model = est_dict.get(f'EXISTING_MODEL_{j}')
                                    if model and str(model).strip() not in ['', 'None', 'N/A']:
                                        existing_equip.append({
                                            "Model": model,
                                            "Serial": est_dict.get(f'EXISTING_SERIAL_{j}', 'N/A')
                                        })
                                
                                if existing_equip:
                                    with st.expander("📝 Existing Equipment Details"):
                                        st.dataframe(pd.DataFrame(existing_equip), hide_index=True)
                                
                                # System Details
                                system_details = [
                                   

                                    ('Supply Length', 'DUCTWORK_SUPPLY_SIZE_LENGTH'),
                                    ('Supply Width', 'DUCTWORK_SUPPLY_SIZE_WIDTH'),
                                    ('Return Length', 'DUCTWORK_RETURN_LENGTH'),
                                    ('Return Width', 'DUCTWORK_RETURN_WIDTH'),
                                    ('Line Sets Size', 'LINE_SETS_SIZE'),
                                    ('Line Sets Condition', 'LINE_SETS_CONDITION'),
                                    ('Line Sets Length', 'LINE_SETS_LENGTH'),
                                    ('Line Sets Refrigerant', 'LINE_SETS_REFRIGERANT_TYPE')
                                ]
                                
                                if any(est_dict[field] for _, field in system_details):
                                    with st.expander("⚙️ System Details"):
                                        cols = st.columns(2)
                                        with cols[0]:
                                            st.write("**Ductwork**")
                                            for label, field in system_details[:3]:
                                                display_if_exists(label, est_dict[field])
                                        
                                        with cols[1]:
                                            st.write("**Line Sets**")
                                            for label, field in system_details[3:]:
                                                display_if_exists(label, est_dict[field])
                                
                                # Installation Features
                                install_features = [
                                    ('Thermostat Installation', 'HAS_THERMOSTAT_INSTALLATION'),
                                    ('Nitrogen Leak Test', 'HAS_NITROGEN_LEAK_TEST'),
                                    ('EZ Trap', 'HAS_EZ_TRAP'),
                                    ('Condensation ¾ PVC', 'HAS_CONDENSATION_PVC'),
                                    ('Condensation Pump', 'HAS_CONDENSATION_PUMP'),
                                    ('Secondary Drain Pan', 'HAS_SECONDARY_DRAIN_PAN')
                                ]
                                
                                if any(est_dict[field] for _, field in install_features):
                                    with st.expander("🛠 Installation Features"):
                                        cols = st.columns(2)
                                        with cols[0]:
                                            for label, field in install_features[:3]:
                                                if est_dict[field]:
                                                    st.write(f"- {label}")
                                        with cols[1]:
                                            for label, field in install_features[3:]:
                                                if est_dict[field]:
                                                    st.write(f"- {label}")
                                
                                # Special Requirements
                                special_reqs = [
                                    ('Crane Needed', 'NEEDS_CRANE'),
                                    ('Trailer Needed', 'NEEDS_TRAILER'),
                                    ('Ladder Needed', 'NEEDS_LADDER'),
                                    ('Lift Needed', 'NEEDS_LIFT'),
                                    ('County Permit', 'NEEDS_COUNTY_PERMIT'),
                                    ('Community Permit', 'NEEDS_COMMUNITY_PERMIT'),
                                    ('Apartment Permit', 'NEEDS_APARTMENT_PERMIT'),
                                    ('Parking Permit', 'NEEDS_PARKING_PERMIT')
                                ]
                                
                                if any(est_dict[field] for _, field in special_reqs):
                                    with st.expander("⚠️ Special Requirements"):
                                        cols = st.columns(2)
                                        with cols[0]:
                                            for label, field in special_reqs[:4]:
                                                if est_dict[field]:
                                                    st.write(f"- {label}")
                                        with cols[1]:
                                            for label, field in special_reqs[4:]:
                                                if est_dict[field]:
                                                    st.write(f"- {label}")
                                        
                                        if est_dict['NEEDS_OTHER']:
                                            st.write("**Other Requirements:**")
                                            st.write(est_dict['NEEDS_OTHER'])
                                
                                # Notes & Recommendations
                                if est_dict['DESCRIPTION'] or est_dict['RECOMMENDATIONS']:
                                    with st.expander("📝 Notes & Recommendations"):
                                        if est_dict['DESCRIPTION']:
                                            st.write("**System Description:**")
                                            st.write(est_dict['DESCRIPTION'])
                                        
                                        if est_dict['RECOMMENDATIONS']:
                                            st.write("**Recommendations:**")
                                            st.write(est_dict['RECOMMENDATIONS'])
                    else:
                        st.info("No estimate reports found for this customer")
                
                except Exception as e:
                    st.error(f"Error loading estimates: {str(e)}")
                
                                # Equipment Pictures Section
                st.markdown('<h3 class="section-header">📸 Equipment Pictures</h3>', unsafe_allow_html=True)
                
                try:
                    pictures = session.sql(f"""
                        SELECT * FROM EQUIPMENT_PICTURES
                        WHERE CUSTOMERID = '{selected_customer}'
                        ORDER BY UPLOADED_AT DESC
                    """).collect()
                    
                    if pictures:
                        cols = st.columns(3)
                        col_idx = 0
                        
                        for pic in pictures:
                            pic_dict = {field: getattr(pic, field) for field in pic._fields}
                            
                            with cols[col_idx]:
                                st.markdown('<div class="picture-card">', unsafe_allow_html=True)
                                if pic_dict['PICTURE_DATA_TEXT']:
                                    try:
                                        img_data = base64.b64decode(pic_dict['PICTURE_DATA_TEXT'])
                                        img = Image.open(io.BytesIO(img_data))
                                        st.image(img, caption=f"{pic_dict['EQUIPMENT_TYPE']} - {pic_dict['NOTES']}")
                                    except Exception as e:
                                        st.error(f"Error displaying image: {str(e)}")
                                else:
                                    st.warning("No image data found")
                                st.markdown('</div>', unsafe_allow_html=True)
                            
                            col_idx += 1
                            if col_idx >= 3:
                                col_idx = 0
                                cols = st.columns(3)
                    else:
                        st.info("No equipment pictures found for this customer")
                
                except Exception as e:
                    st.error(f"Error loading pictures: {str(e)}")
                
                
                
                
                # Service History Section
                st.markdown('<h3 class="section-header">⏳ Service History</h3>', unsafe_allow_html=True)
                
                try:
                    service_history = session.sql(f"""
                        SELECT 
                            a.APPOINTMENTID,
                            a.SERVICE_TYPE,
                            a.SCHEDULED_TIME,
                            a.STA_TUS,
                            a.NOTES,
                            e.ENAME AS TECHNICIAN_NAME
                        FROM APPOINTMENTS a
                        JOIN EMPLOYEES e ON a.TECHNICIANID = e.EMPLOYEEID
                        WHERE a.CUSTOMERID = '{selected_customer}'
                        ORDER BY a.SCHEDULED_TIME DESC
                        LIMIT 10
                    """).collect()
                    
                    if service_history:
                        history_data = []
                        for record in service_history:
                            rec_dict = {field: getattr(record, field) for field in record._fields}
                            history_data.append({
                                "Date": rec_dict['SCHEDULED_TIME'].strftime('%Y-%m-%d'),
                                "Service": rec_dict['SERVICE_TYPE'],
                                "Technician": rec_dict['TECHNICIAN_NAME'],
                                "Status": rec_dict['STA_TUS'],
                                "Notes": rec_dict['NOTES'] or ""
                            })
                        
                        st.dataframe(
                            pd.DataFrame(history_data),
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "Date": st.column_config.Column(width="small"),
                                "Service": st.column_config.Column(width="medium"),
                                "Technician": st.column_config.Column(width="medium"),
                                "Status": st.column_config.Column(width="small")
                            }
                        )
                    else:
                        st.info("No service history found for this customer")
                
                except Exception as e:
                    st.error(f"Error loading service history: {str(e)}")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")
    else:
        st.info("Enter search terms and click Search to find a customer")      
                              

##########################################################################################
###############################################################
##########################################################################################


#######################################################################
#######################################################################                  
from fpdf import FPDF
from datetime import datetime
import base64

def quote():
    st.title("📝 HVAC Quote")
    session = get_session()
    
    # Custom styling
    st.markdown("""
    <style>
        .quote-section {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            background-color: #f9f9f9;
        }
        .quote-header {
            background: linear-gradient(135deg, #4b6cb7 0%, #182848 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .important-note {
            background-color: #fffde7;
            border-left: 4px solid #ffc107;
            padding: 10px;
            margin: 15px 0;
        }
        .equipment-card {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
            background-color: #f5f5f5;
        }
        .pdf-button {
            background-color: #ff4b4b !important;
            color: white !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Quote header section
    st.markdown('<div class="quote-header">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        quote_number = st.text_input("Quote #", value=f"QT-{datetime.now().strftime('%Y%m%d-%H%M')}")
    with col2:
        quote_date = st.date_input("Date", value=datetime.today())
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Customer search section
    st.subheader("👤 Customer Information")
    search_term = st.text_input("Search customer by name, phone, or address", key="quote_customer_search")
    customer_id = None
    customer_info = {}
    
    if search_term:
        customers = session.sql(f"""
            SELECT customerid, name, phone, address, city, state, zipcode 
            FROM customers
            WHERE name ILIKE '%{search_term}%'
               OR phone ILIKE '%{search_term}%'
               OR address ILIKE '%{search_term}%'
            ORDER BY name
            LIMIT 5
        """).collect()
        
        if customers:
            selected_customer = st.selectbox(
                "Select customer",
                options=[c['CUSTOMERID'] for c in customers],
                format_func=lambda x: next(f"{c['NAME']} | {c['PHONE']} | {c['ADDRESS']}" for c in customers if c['CUSTOMERID'] == x)
            )
            customer = next(c for c in customers if c['CUSTOMERID'] == selected_customer)
            customer_id = selected_customer
            customer_info = {
                'name': customer['NAME'],
                'address': f"{customer['ADDRESS']}, {customer['CITY']}, {customer['STATE']} {customer['ZIPCODE']}",
                'phone': customer['PHONE']
            }
            st.success(f"Selected: {customer_info['name']}")
        else:
            st.warning("No customers found")
    
    # Service Requested
    st.subheader("🔧 Service Requested")
    service_type = st.selectbox(
        "Service Type",
        ["Installation", "Repair", "Maintenance", "Replacement", "Other"]
    )
    service_description = st.text_area("Service Description", height=100)
    
    # Initialize session state for equipment management
    if 'equipment_to_add' not in st.session_state:
        st.session_state.equipment_to_add = []
    
    # Equipment Information
    st.subheader("🛠 Equipment Details")
    
    # Existing Equipment Section
    with st.expander("📋 Existing Equipment From Estimate Report", expanded=True):
        if customer_id:
            existing_equipment = session.sql(f"""
                SELECT * FROM EQUIPMENT_PICTURES
                WHERE CUSTOMERID = '{customer_id}'
                ORDER BY UPLOADED_AT DESC
            """).collect()
            
            if existing_equipment:
                st.success(f"Found {len(existing_equipment)} existing equipment records")
                
                # Display each equipment record with edit/delete options
                for i, eq in enumerate(existing_equipment):
                    with st.container():
                        st.markdown(f"### Equipment {i+1}: {eq['EQUIPMENT_TYPE']}")
                        
                        col1, col2 = st.columns([3,1])
                        with col1:
                            st.write(f"**Model:** {eq['MODEL']}")
                            st.write(f"**Serial:** {eq['SERIAL']}")
                            st.write(f"**Notes:** {eq['NOTES']}")
                            
                            # Display image if available
                            if eq['PICTURE_DATA_TEXT']:
                                try:
                                    img_data = base64.b64decode(eq['PICTURE_DATA_TEXT'])
                                    img = Image.open(io.BytesIO(img_data))
                                    st.image(img, caption=f"{eq['EQUIPMENT_TYPE']} photo", width=200)
                                except:
                                    st.warning("Could not display image")
                        
                        with col2:
                            # Edit button - opens a form to edit this equipment
                            if st.button(f"✏️ Edit", key=f"edit_{eq['PICTURE_ID']}"):
                                st.session_state['editing_equipment'] = eq['PICTURE_ID']
                            
                            # Delete button
                            if st.button(f"🗑️ Delete", key=f"del_{eq['PICTURE_ID']}"):
                                session.sql(f"""
                                    DELETE FROM EQUIPMENT_PICTURES
                                    WHERE PICTURE_ID = '{eq['PICTURE_ID']}'
                                """).collect()
                                st.success("Equipment record deleted!")
                                st.rerun()
                        
                        # Edit form (appears when edit button is clicked)
                        if 'editing_equipment' in st.session_state and st.session_state['editing_equipment'] == eq['PICTURE_ID']:
                            with st.form(f"edit_form_{eq['PICTURE_ID']}"):
                                new_type = st.text_input("Equipment Type", value=eq['EQUIPMENT_TYPE'])
                                new_model = st.text_input("Model #", value=eq['MODEL'])
                                new_serial = st.text_input("Serial #", value=eq['SERIAL'])
                                new_notes = st.text_area("Notes", value=eq['NOTES'])
                                new_file = st.file_uploader("Update Picture", type=["jpg", "jpeg", "png"])
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("💾 Save Changes"):
                                        try:
                                            # Process new image if uploaded
                                            img_data = None
                                            if new_file:
                                                img = Image.open(new_file)
                                                img = ImageOps.fit(img, (800, 800))
                                                buffer = io.BytesIO()
                                                img.save(buffer, format="JPEG", quality=85)
                                                img_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                                            
                                            # Update record
                                            update_query = f"""
                                                UPDATE EQUIPMENT_PICTURES
                                                SET EQUIPMENT_TYPE = '{new_type}',
                                                    MODEL = '{new_model}',
                                                    SERIAL = '{new_serial}',
                                                    NOTES = '{new_notes}'
                                            """
                                            if img_data:
                                                update_query += f", PICTURE_DATA_TEXT = '{img_data}'"
                                            
                                            update_query += f" WHERE PICTURE_ID = '{eq['PICTURE_ID']}'"
                                            
                                            session.sql(update_query).collect()
                                            st.success("Equipment updated successfully!")
                                            del st.session_state['editing_equipment']
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error updating equipment: {str(e)}")
                                with col2:
                                    if st.form_submit_button("❌ Cancel"):
                                        del st.session_state['editing_equipment']
                                        st.rerun()
                        
                        st.markdown("---")
            else:
                st.info("No existing equipment records found for this customer")
        else:
            st.info("Please select a customer to view existing equipment")
    ##################################################
    with st.expander("Add Existing Equipment"):
        st.subheader("Equipment Type:")

  

    # Organized in categories
        cols = st.columns(3)
        equipment_checks = {}
    
    # Heating/Cooling Systems
        with cols[0]:
            st.write("**Heating/Cooling**")
            equipment_checks['HAS_GAS_FURNACE'] = st.checkbox("Gas Furnace", key="HAS_GAS_FURNACE")
            equipment_checks['HAS_COIL'] = st.checkbox("Coil", key="HAS_COIL")
            equipment_checks['HAS_AIR_HANDLER'] = st.checkbox("Air Handler", key="HAS_AIR_HANDLER")
            equipment_checks['HAS_CONDENSER'] = st.checkbox("Condenser", key="HAS_CONDENSER")
            equipment_checks['HAS_HEAT_PUMP'] = st.checkbox("Heat Pump", key="HAS_HEAT_PUMP")
            equipment_checks['HAS_DUAL_FUEL_SYSTEM'] = st.checkbox("Dual Fuel System", key="HAS_DUAL_FUEL_SYSTEM")
            equipment_checks['HAS_MINI_SPLIT_CONDENSER'] = st.checkbox("Mini_Split Condenser", key="HAS_MINI_SPLIT_CONDENSER")
            equipment_checks['HAS_WATER_SOURCE_HP'] = st.checkbox("Water Source Heat Pump", key="HAS_WATER_SOURCE_HP")
            equipment_checks['HAS_GEOTHERMAL'] = st.checkbox("Geothermal Heat Pump", key="HAS_GEOTHERMAL")
            equipment_checks['HAS_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL'] = st.checkbox("Roof Top Gas Heat Electric Cool", key="HAS_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL")
            equipment_checks['HAS_ROOF_TOP_HEAT_PUMP'] = st.checkbox("Roof Top Heat Pump", key="HAS_ROOF_TOP_HEAT_PUMP")
            
        with cols[1]:
            st.write("**Water Heaters**")
            equipment_checks['HAS_ELECTRIC_WH'] = st.checkbox("Electric Water Heaters", key="HAS_ELECTRIC_WH")
            equipment_checks['HAS_GAS_WH'] = st.checkbox("Gas Water Heaters", key="HAS_GAS_WH")
            equipment_checks['HAS_HYBRID_WH'] = st.checkbox("Hybrid Water Heaters", key="HAS_HYBRID_WH")
        
            st.write("**Mini-Split Indoor**")
            equipment_checks['HAS_MINI_SPLIT_WALL'] = st.checkbox("Wall Mount", key="HAS_MINI_SPLIT_WALL")
            equipment_checks['HAS_MINI_SPLIT_CEILING'] = st.checkbox("Ceiling Mount", key="HAS_MINI_SPLIT_CEILING")
        
            st.write("**Boilers**")
            equipment_checks['HAS_ELECTRIC_BOILER'] = st.checkbox("Electric Boiler", key="HAS_ELECTRIC_BOILER")
            equipment_checks['HAS_GAS_BOILER'] = st.checkbox("Gas Boiler", key="HAS_GAS_BOILER")
            st.write("**Components**")
            equipment_checks['HAS_HUMIDIFIER'] = st.checkbox("Humidifier", key="HAS_HUMIDIFIER")
            equipment_checks['HAS_UV_LIGHT'] = st.checkbox("UV Light", key="HAS_UV_LIGHT")
            equipment_checks['HAS_THERMOSTAT'] = st.checkbox("Thermostat", key="HAS_THERMOSTAT")
        
        with cols[2]:
            st.write("**Controls**")
            equipment_checks['HAS_EVR'] = st.checkbox("EVR", key="HAS_EVR")
            equipment_checks['HAS_ZONE_CTRL'] = st.checkbox("Zone Control", key="HAS_ZONE_CTRL")
        
            st.write("**Other Types**")
            equipment_checks['HAS_THRU_THE_WALL_CONDENSER'] = st.checkbox("Thru-the-Wall Condenser", key='HAS_THRU_THE_WALL_CONDENSER')
            equipment_checks['HAS_THRU_THE_WALL_PACKED_HEAT_PUMP'] = st.checkbox("Thru-the-Wall Packed Heat Pump", key="HAS_THRU_THE_WALL_PACKED_HEAT_PUMP")
            equipment_checks['HAS_WALK_IN_COOLER'] = st.checkbox("Walk-in Cooler", key="HAS_WALK_IN_COOLER")
            equipment_checks['HAS_WALK_IN_FREEZER'] = st.checkbox("Walk-in Freezer", key="HAS_WALK_IN_FREEZER")
            equipment_checks['HAS_CONSOLE_HEAT_PUMP'] = st.checkbox("Console Heat Pump", key="HAS_CONSOLE_HEAT_PUMP")
            equipment_checks['HAS_CONSOLE_FAN_COIL'] = st.checkbox("Console Fan Coil", key="HAS_CONSOLE_FAN_COIL")

            equipment_checks['HAS_OTHER_EQUIPMENT'] = st.checkbox("Other Equipment", key="HAS_OTHER_EQUIPMENT")
            
    
      

    # ======================
    # 3. EXISTING EQUIPMENT (MODIFIED SECTION)
    # ======================
    
    # Initialize equipment details in session state
    if 'equipment_details' not in st.session_state:
        st.session_state.equipment_details = {}
    
    # Mapping of session state keys to human-readable names
    equipment_mapping = {
    'HAS_GAS_FURNACE': 'Gas Furnace',
    'HAS_COIL': 'Coil',
    'HAS_AIR_HANDLER': 'Air Handler',
    'HAS_CONDENSER': 'Condenser',
    'HAS_HEAT_PUMP': 'Heat Pump',
    'HAS_DUAL_FUEL_SYSTEM': 'Dual Fuel System',
    'HAS_MINI_SPLIT_CONDENSER': 'Mini_Split Condenser',
    'HAS_WATER_SOURCE_HP' : 'Water Source Heat Pump',
    'HAS_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL' :' Roof Top Gas Heat Electric Cool', 
    'HAS_ROOF_TOP_HEAT_PUMP' : 'Roof Top Heat Pump',
    'HAS_GEOTHERMAL': 'Geothermal Heat Pump',
    'HAS_ELECTRIC_WH': 'Electric Water Heaters',
    'HAS_GAS_WH': 'Gas Water Heater',
    'HAS_HYBRID_WH': 'Hybrid Water Heater',
    'HAS_MINI_SPLIT_WALL': 'Wall Mount',
    'HAS_MINI_SPLIT_CEILING': 'Ceiling Mount',
    'HAS_ELECTRIC_BOILER': 'Electric Boiler',
    'HAS_GAS_BOILER': "Gas Boiler",
    'HAS_HUMIDIFIER': 'Humidifier',
    'HAS_UV_LIGHT': 'UV Light',
    'HAS_THERMOSTAT': 'Thermostat',
    'HAS_EVR': 'EVR',
    'HAS_ZONE_CTRL': 'Zone Control',
    'HAS_THRU_THE_WALL_CONDENSER':'Thru-the-Wall Condenser ',
    'HAS_THRU_THE_WALL_PACKED_HEAT_PUMP': 'Thru-the-Wall Packed Heat Pump',        
    'HAS_WALK_IN_COOLER': 'Walk-in Cooler',
    'HAS_WALK_IN_FREEZER': 'Walk-in Freezer',
    'HAS_CONSOLE_HEAT_PUMP': 'Console Heat Pump',
    'HAS_CONSOLE_FAN_COIL': 'Console Fan Coil',
    'HAS_OTHER_EQUIPMENT': 'Other Equipment',
    }
    
    
    # Create collapsible sections for each equipment type
    for key, eqe_name in equipment_mapping.items():
        if st.session_state.get(key, False):
            with st.expander(f"{eqe_name} Details"):
            # Initialize list for this equipment type if not exists
                if key not in st.session_state.equipment_details:
                    st.session_state.equipment_details[key] = []
            
                # Display existing models for this equipment type
                for i, model_data in enumerate(st.session_state.equipment_details[key]):
                    with st.container():
                        st.write(f"#### Model {i+1}")
                        col1, col2 = st.columns([3,1])
                    
                        with col1:
                        # Model and Serial Inputs
                            model = st.text_input(
                                f"{eqe_name} Model #{i+1}", 
                                key=f"{key}_MODEL_{i}",
                                value=model_data.get('model', '')
                            )
                            serial = st.text_input(
                                f"{eqe_name} Serial #{i+1}", 
                                key=f"{key}_SERIAL_{i}",
                                value=model_data.get('serial', '')
                            )
                    
                        with col2:
                        # Picture Upload
                            uploaded_file = st.file_uploader(
                                f"Upload {eqe_name} Picture #{i+1}", 
                                type=["jpg", "jpeg", "png"], 
                                key=f"{key}_UPLOAD_{i}"
                            )
                            pic_notes = st.text_input(
                                f"Picture Notes #{i+1}", 
                                key=f"{key}_PIC_NOTES_{i}",
                                value=model_data.get('pic_notes', '')
                            )
                    
                    # Update model data
                        st.session_state.equipment_details[key][i] = {
                            'type': eqe_name,
                            'model': model,
                            'serial': serial,
                            'uploaded_file': uploaded_file,
                            'pic_notes': pic_notes
                        }
                    
                    # Remove button
                        if st.button(f"Remove Model {i+1}", key=f"remove_{key}_{i}"):
                            st.session_state.equipment_details[key].pop(i)
                            st.rerun()
                    
                        st.markdown("---")
            
            # Add new model button
                if st.button(f"➕ Add Another {eqe_name} Model"):
                    st.session_state.equipment_details[key].append({
                        'type': eqe_name,
                        'model': '',
                        'serial': '',
                        'uploaded_file': None,
                        'pic_notes': ''
                    })
                    st.rerun()
  
######################################    
    with st.expander("Add New Equipment"):
        st.subheader("New Equipment Type:")

  

    # Organized in categories
        cols = st.columns(3)
        equipment_checks = {}
    
    # Heating/Cooling Systems
        with cols[0]:
            st.write("**Heating/Cooling**")
            equipment_checks['HAS_NEW_GAS_FURNACE'] = st.checkbox("Gas Furnace", key="HAS_NEW_GAS_FURNACE")
            equipment_checks['HAS_NEW_COIL'] = st.checkbox("Coil", key="HAS_NEW_COIL")
            equipment_checks['HAS_NEW_AIR_HANDLER'] = st.checkbox("Air Handler", key="HAS_NEW_AIR_HANDLER")
            equipment_checks['HAS_NEW_CONDENSER'] = st.checkbox("Condenser", key="HAS_NEW_CONDENSER")
            equipment_checks['HAS_NEW_HEAT_PUMP'] = st.checkbox("Heat Pump", key="HAS_NEW_HEAT_PUMP")
            equipment_checks['HAS_NEW_DUAL_FUEL_SYSTEM'] = st.checkbox("Dual Fuel System", key="HAS_NEW_DUAL_FUEL_SYSTEM")
            equipment_checks['HAS_NEW_MINI_SPLIT_CONDENSER'] = st.checkbox("Mini_Split Condenser", key="HAS_NEW_MINI_SPLIT_CONDENSER")
            equipment_checks['HAS_NEW_WATER_SOURCE_HP'] = st.checkbox("Water Source Heat Pump", key="HAS_NEW_WATER_SOURCE_HP")
            equipment_checks['HAS_NEW_GEOTHERMAL'] = st.checkbox("Geothermal Heat Pump", key="HAS_NEW_GEOTHERMAL")
            equipment_checks['HAS_NEW_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL'] = st.checkbox("Roof Top Gas Heat Electric Cool", key="HAS_NEW_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL")
            equipment_checks['HAS_NEW_ROOF_TOP_HEAT_PUMP'] = st.checkbox("Roof Top Heat Pump", key="HAS_NEW_ROOF_TOP_HEAT_PUMP")
            
        with cols[1]:
            st.write("**Water Heaters**")
            equipment_checks['HAS_NEW_ELECTRIC_WH'] = st.checkbox("Electric Water Heaters", key="HAS_NEW_ELECTRIC_WH")
            equipment_checks['HAS_NEW_GAS_WH'] = st.checkbox("Gas Water Heaters", key="HAS_NEW_GAS_WH")
            equipment_checks['HAS_NEW_HYBRID_WH'] = st.checkbox("Hybrid Water Heaters", key="HAS_NEW_HYBRID_WH")
        
            st.write("**Mini-Split Indoor**")
            equipment_checks['HAS_NEW_MINI_SPLIT_WALL'] = st.checkbox("Wall Mount", key="HAS_NEW_MINI_SPLIT_WALL")
            equipment_checks['HAS_NEW_MINI_SPLIT_CEILING'] = st.checkbox("Ceiling Mount", key="HAS_NEW_MINI_SPLIT_CEILING")
        
            st.write("**Boilers**")
            equipment_checks['HAS_NEW_ELECTRIC_BOILER'] = st.checkbox("Electric Boiler", key="HAS_NEW_ELECTRIC_BOILER")
            equipment_checks['HAS_NEW_GAS_BOILER'] = st.checkbox("Gas Boiler", key="HAS_NEW_GAS_BOILER")
            st.write("**Components**")
            equipment_checks['HAS_NEW_HUMIDIFIER'] = st.checkbox("Humidifier", key="HAS_NEW_HUMIDIFIER")
            equipment_checks['HAS_NEW_UV_LIGHT'] = st.checkbox("UV Light", key="HAS_NEW_UV_LIGHT")
            equipment_checks['HAS_NEW_THERMOSTAT'] = st.checkbox("Thermostat", key="HAS_NEW_THERMOSTAT")
        
        with cols[2]:
            st.write("**Controls**")
            equipment_checks['HAS_NEW_EVR'] = st.checkbox("EVR", key="HAS_NEW_EVR")
            equipment_checks['HAS_NEW_ZONE_CTRL'] = st.checkbox("Zone Control", key="HAS_NEW_ZONE_CTRL")
        
            st.write("**Other Types**")
            equipment_checks['HAS_NEW_THRU_THE_WALL_CONDENSER'] = st.checkbox("Thru-the-Wall Condenser", key='HAS_NEW_THRU_THE_WALL_CONDENSER')
            equipment_checks['HAS_NEW_THRU_THE_WALL_PACKED_HEAT_PUMP'] = st.checkbox("Thru-the-Wall Packed Heat Pump", key="HAS_NEW_THRU_THE_WALL_PACKED_HEAT_PUMP")
            equipment_checks['HAS_NEW_WALK_IN_COOLER'] = st.checkbox("Walk-in Cooler", key="HAS_NEW_WALK_IN_COOLER")
            equipment_checks['HAS_NEW_WALK_IN_FREEZER'] = st.checkbox("Walk-in Freezer", key="HAS_NEW_WALK_IN_FREEZER")
            equipment_checks['HAS_NEW_CONSOLE_HEAT_PUMP'] = st.checkbox("Console Heat Pump", key="HAS_NEW_CONSOLE_HEAT_PUMP")
            equipment_checks['HAS_NEW_CONSOLE_FAN_COIL'] = st.checkbox("Console Fan Coil", key="HAS_NEW_CONSOLE_FAN_COIL")

            equipment_checks['HAS_NEW_OTHER_EQUIPMENT'] = st.checkbox("Other Equipment", key="HAS_NEW_OTHER_EQUIPMENT")
            
    
      

    # ======================
    # 3. EXISTING EQUIPMENT (MODIFIED SECTION)
    # ======================
   
    
    # Initialize equipment details in session state
    if 'new_equipment_details' not in st.session_state:
        st.session_state.new_equipment_details = {}
    
    # Mapping of session state keys to human-readable names
    new_equipment_mapping = {
    'HAS_NEW_GAS_FURNACE': 'Gas Furnace',
    'HAS_NEW_COIL': 'Coil',
    'HAS_NEW_AIR_HANDLER': 'Air Handler',
    'HAS_NEW_CONDENSER': 'Condenser',
    'HAS_NEW_HEAT_PUMP': 'Heat Pump',
    'HAS_NEW_DUAL_FUEL_SYSTEM': 'Dual Fuel System',
    'HAS_NEW_MINI_SPLIT_CONDENSER': 'Mini_Split Condenser',
    'HAS_NEW_WATER_SOURCE_HP' : 'Water Source Heat Pump',
    'HAS_NEW_ROOF_TOP_GAS_HEAT_ELECTRIC_COOL' :' Roof Top Gas Heat Electric Cool', 
    'HAS_NEW_ROOF_TOP_HEAT_PUMP' : 'Roof Top Heat Pump',
    'HAS_NEW_GEOTHERMAL': 'Geothermal Heat Pump',
    'HAS_NEW_ELECTRIC_WH': 'Electric Water Heaters',
    'HAS_NEW_GAS_WH': 'Gas Water Heater',
    'HAS_NEW_HYBRID_WH': 'Hybrid Water Heater',
    'HAS_NEW_MINI_SPLIT_WALL': 'Wall Mount',
    'HAS_NEW_MINI_SPLIT_CEILING': 'Ceiling Mount',
    'HAS_NEW_ELECTRIC_BOILER': 'Electric Boiler',
    'HAS_NEW_GAS_BOILER': "Gas Boiler",
    'HAS_NEW_HUMIDIFIER': 'Humidifier',
    'HAS_NEW_UV_LIGHT': 'UV Light',
    'HAS_NEW_THERMOSTAT': 'Thermostat',
    'HAS_NEW_EVR': 'EVR',
    'HAS_NEW_ZONE_CTRL': 'Zone Control',
    'HAS_NEW_THRU_THE_WALL_CONDENSER':'Thru-the-Wall Condenser ',
    'HAS_NEW_THRU_THE_WALL_PACKED_HEAT_PUMP': 'Thru-the-Wall Packed Heat Pump',        
    'HAS_NEW_WALK_IN_COOLER': 'Walk-in Cooler',
    'HAS_NEW_WALK_IN_FREEZER': 'Walk-in Freezer',
    'HAS_NEW_CONSOLE_HEAT_PUMP': 'Console Heat Pump',
    'HAS_NEW_CONSOLE_FAN_COIL': 'Console Fan Coil',
    'HAS_NEW_OTHER_EQUIPMENT': 'Other Equipment',
    }
    
    #eqn_name: new equipment name
    for key, eqn_name in new_equipment_mapping.items():
        if st.session_state.get(key, False):
            with st.expander(f"New {eqn_name} Details"):
            # Initialize list for this equipment type if not exists
                if key not in st.session_state.new_equipment_details:
                    st.session_state.new_equipment_details[key] = []
            
                # Display existing models for this equipment type
                for i, model_data in enumerate(st.session_state.new_equipment_details[key]):
                    with st.container():
                        st.write(f"#### Model {i+1}")
                        col1, col2 = st.columns([3,1])
                    
                        with col1:
                        # Model and Serial Inputs
                            model = st.text_input(
                                f"{eqn_name} Model #{i+1}", 
                                key=f"{key}_MODEL_{i}",
                                value=model_data.get('model', '')
                            )
                            
                    
                        
                    
                    # Update model data
                        st.session_state.new_equipment_details[key][i] = {
                            'type': eqn_name,
                            'model': model
                        }
                    
                    # Remove button
                        if st.button(f"Remove Model {i+1}", key=f"remove_{key}_{i}"):
                            st.session_state.new_equipment_details[key].pop(i)
                            st.rerun()
                    
                      
            
            # Add new model button
                if st.button(f"➕ Add Another {eqn_name} Model"):
                    st.session_state.new_equipment_details[key].append({
                        'type': eqn_name,
                        'model': ''
                    })
                    st.rerun()
  
    with st.expander("📅 Timeline"):
        st.subheader("Project Timeline")
        col1, col2 = st.columns(2)
        with col1:
            start_days = st.number_input("Business days to start after deposit", min_value=1, value=5)
        with col2:
            completion_days = st.number_input("Estimated completion days", min_value=1, value=3)
        
       




    
                ###################
    
    # Work Description
    with st.expander("📝 Work Description", expanded=True):
        st.write("**Removing and hauling away existing equipment:**")
        
    with st.expander("Excluding, Payment, Warranty"):
        st.subheader("Excluding:")
        st.write("""
        Excluding: permitting, repairing drywalls, painting, and training.""")
        
        st.subheader("Payment:")
        st.write("""
        To initiate the installation process, we require a deposit of half the total price. The installation
        will commence within five business days of receiving the deposit and will be completed within one
        day. The remaining balance is due within three business days of the installation's completion. We
        accept payment by check, cash, money order, Zelle, Venmo, and credit card (with a 3% fee).""")
        
        st.subheader("Warranty:")
        st.write("""
        We believe in the quality of our work and the products we use. After registration, all units
        come with a 10-year parts warranty from the manufacturer. Please note that labor costs are not included
        in this warranty. However, our installation warranty is for a lifetime, covering any problems related to
        the installation, including refrigerant leaks. We are also responsible for the shortage of refrigerant and
        offer a one-time inspection in the summertime for your peace of mind.""")
        st.write("We truly appreciate your business and the trust you've placed in us.")
        st.write("Potomac HVAC LLC")
        st.write("(301) 825-4447")

    # Company Information
    col1, col2 = st.columns([1, 2])
    with col1:
        # You should replace this with your actual logo image
        # For now using a placeholder
        st.image(Image.new('RGB', (150, 100), color='#4b6cb7'), width=150)
    with col2:
        st.markdown("""
        **Potomac HVAC LLC**  
        **All Heating and Cooling Systems**
        
        ☎ (301) 825-4447  
        ✉ info@potomachvac.com  
        🌐 www.potomachvac.com
        """)
    
    # Action Buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🖨️ Generate Quote PDF", type="primary"):
            # Generate the PDF
            pdf = generate_quote_pdf(
                quote_number=quote_number,
                quote_date=quote_date.strftime('%Y-%m-%d') if quote_date else datetime.today().strftime('%Y-%m-%d'),
                customer_info=customer_info,
                service_type=service_type,
                service_description=service_description,
                proposed_equipment=st.session_state.proposed_equipment,
                remove_fan_coil=remove_fan_coil,
                remove_outdoor_hp=remove_outdoor_hp,
                remove_air_handler=remove_air_handler,
                remove_condenser=remove_condenser,
                start_days=start_days,
                completion_days=completion_days
            )
            
            # Create download link
            st.download_button(
                label="⬇️ Download PDF",
                data=pdf.output(dest='S').encode('latin1'),
                file_name=f"Quote_{quote_number}.pdf",
                mime="application/pdf"
            )
            st.success("Quote generated successfully!")
    
    with col2:
        if st.button("✉️ Email to Customer"):
            st.success("Quote sent to customer!")
    with col3:
        if st.button("💾 Save Draft"):
            st.success("Draft saved successfully!")
if st.button("Generate Quote PDF"):
    pdf_path = generate_quote_pdf()
    with open(pdf_path, "rb") as f:
        st.download_button("Download Quote PDF", f, file_name="HVAC_Quote.pdf", mime="application/pdf")

########################
#######################################################################

from fpdf import FPDF
from datetime import datetime

class QuotePDF(FPDF):
    def header(self):
        self.set_font("Arial", 'B', 14)
        self.cell(0, 10, "POTOMAC HVAC LLC", ln=True, align='C')
        self.set_font("Arial", '', 11)
        self.cell(0, 10, "(301) 825-4447", ln=True, align='C')
        self.ln(5)

    def add_title(self, title):
        self.set_font("Arial", 'B', 12)
        self.set_text_color(0)
        self.cell(0, 10, title, ln=True)
        self.set_font("Arial", '', 11)

    def add_line(self, label, value):
        self.set_font("Arial", 'B', 11)
        self.cell(40, 8, label, ln=False)
        self.set_font("Arial", '', 11)
        self.cell(0, 8, value, ln=True)

    def multi_text(self, text):
        self.set_font("Arial", '', 11)
        self.multi_cell(0, 8, text)
        self.ln(2)

    def add_table(self, header, data):
        self.set_font("Arial", 'B', 11)
        for item in header:
            self.cell(63, 8, item, border=1, align='C')
        self.ln()
        self.set_font("Arial", '', 11)
        for row in data:
            for item in row:
                self.cell(63, 8, str(item), border=1, align='C')
            self.ln()
        self.ln(3)

def generate_quote_pdf():
    pdf = QuotePDF()
    pdf.add_page()

    # Quote header
    quote_number = "062525-5"
    quote_date = datetime.today().strftime('%B %d, %Y')
    pdf.add_line("Quote Number:", quote_number)
    pdf.add_line("Date:", quote_date)
    pdf.ln(5)

    # Customer Info
    pdf.add_title("Customer Information")
    pdf.multi_text("Name: Mrs. Sara Royce\nPhone: (570) 236-5982\nAddress: 722B, Main Street, Gaithersburg, MD. 20878")

    # Service Requested
    pdf.add_title("Service Requested")
    pdf.multi_text("NO COOL")

    # Diagnostic
    pdf.add_title("Diagnostic")
    pdf.multi_text("""Visiting date and time: July 25 - 8:20 pm
Technician: Mahdi Poursiami, Master HVAC (License#: 112743, MD)
The compressor in the outdoor condenser is defective (grounded).""")

    # Existing Equipment Table
    pdf.add_title("Existing Equipment")
    existing_data = [
        ["Outdoor Condenser", "Model#: 113ANW036-H", "Serial#: 2114E22043"],
        ["Indoor Furnace", "Model#: P3URB12N07501E", "Serial#: EAKM027846"],
        ["Evaporator Coil", "Model#: CNPVP3617AL", "Serial#: 1114X37758"]
    ]
    pdf.add_table(["Type", "Model#", "Serial#"], existing_data)

    # Replacement Options
    pdf.add_title("Replacement Options")
    options = [
        ("Option 1", "Bryant 3 Ton Up to 16.5 SEER2 AC + Coil", "$6,130.00"),
        ("Option 2", "Bryant AC + Coil + 92% AFUE Gas Furnace", "$8,750.00"),
        ("Option 3", "Goodman 14.3 SEER2 AC + Coil", "$5,690.00"),
        ("Option 4", "Goodman AC + Coil + 96% Gas Furnace", "$7,860.00"),
    ]
    for label, desc, price in options:
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, label, ln=True)
        pdf.set_font("Arial", '', 11)
        pdf.multi_cell(0, 8, f"{desc}\nTotal Price: {price}")
        pdf.ln(2)

    # Including
    pdf.add_title("Including")
    pdf.multi_text("""- Ductwork to fit new fan coil
- Condenser pad and legs
- UV-resistant insulation
- Lock-cap on service valves
- Gas line connection
- Flushing and nitrogen leak test
- Vacuum line sets to 500 microns
- Press fittings for A2L refrigerant""")

    # Excluding
    pdf.add_title("Excluding")
    pdf.multi_text("Permitting, drywall repair, painting, and training.")

    # Payment
    pdf.add_title("Payment Terms")
    pdf.multi_text("""To initiate installation, a deposit of half the total price is required. Work will begin within 5 business days of deposit (if equipment is available) and completed within 1 day. Balance is due within 3 business days of completion. Accepted: check, cash, Zelle, Venmo, credit card (+3% fee).""")

    # Warranty
    pdf.add_title("Warranty")
    pdf.multi_text("""All units come with a 10-year parts warranty (after registration). Labor not included. Lifetime installation warranty covers refrigerant leaks and includes a one-time summer inspection.""")

    # Footer
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, "We truly appreciate your business and the trust you've placed in us.", ln=True)
    pdf.cell(0, 10, "Potomac HVAC LLC", ln=True)
    pdf.cell(0, 10, "(301) 825-4447", ln=True)

    # Save
    output_path = "quote_output.pdf"
    pdf.output(output_path)
    return output_path


    
#######################################################################
#######################################################################

    


#######################################################################
#######################################################################


        
#######################################################################   
#######################################################################
# Admin Tab: Manage All Tables

def admin_tables():
    st.subheader("🛠 Admin Tables")
    session = get_session()
    
    # List of available tables (all uppercase for Snowflake)
    tables = [
        "EMPLOYEES", "CUSTOMERS", "APPOINTMENTS", 
        "ROLES", "EMPLOYEE_ROLES", "EXPERTISE", "EMPLOYEE_EXPERTISE",
        "EMPLOYEE_SCHEDULES"
    ]
    
    # Select table to manage
    selected_table = st.selectbox("Select Table", tables)
    
    if selected_table == "EMPLOYEE_SCHEDULES":
        st.subheader("📅 Employee Schedule Management")
        
        # Date range selection - default to current week
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=30)
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Week Starting", value=start_of_week)
        with col2:
            end_date = st.date_input("Week Ending", value=end_of_week)
        
        # Get all employees for dropdown
        employees = session.sql("SELECT EMPLOYEEID, ENAME FROM EMPLOYEES ORDER BY ENAME").collect()
        employee_options = {e['EMPLOYEEID']: e['ENAME'] for e in employees}
        
        # Get all schedules for the selected week
        schedules = session.sql(f"""
            SELECT 
                s.SCHEDULEID,
                e.ENAME as EMPLOYEE_NAME,
                s.SCHEDULE_DATE,
                TO_CHAR(s.START_TIME, 'HH24:MI') as START_TIME,
                TO_CHAR(s.END_TIME, 'HH24:MI') as END_TIME,
                s.NOTES
            FROM EMPLOYEE_SCHEDULES s
            JOIN EMPLOYEES e ON s.EMPLOYEEID = e.EMPLOYEEID
            WHERE s.SCHEDULE_DATE BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY s.SCHEDULE_DATE, e.ENAME
        """).collect()
        
        # Display schedules in a clean table format
        if schedules:
            # Create a list of dictionaries for the table display
            display_data = []
            for s in schedules:
                display_data.append({
                    "Employee": s['EMPLOYEE_NAME'],
                    "Date": s['SCHEDULE_DATE'].strftime('%a %m/%d'),
                    "Start Time": s['START_TIME'],
                    "End Time": s['END_TIME'],
                    "Notes": s['NOTES'] or ""
                })
            
            st.dataframe(
                pd.DataFrame(display_data),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Date": st.column_config.Column(width="small"),
                    "Start Time": st.column_config.Column(width="small"),
                    "End Time": st.column_config.Column(width="small"),
                    "Notes": st.column_config.Column(width="medium")
                }
            )
        else:
            st.info("No schedules found for selected week")
            
        # Schedule management form
        with st.expander("✏️ Add/Edit Schedule"):
            with st.form("schedule_form"):
                col1, col2 = st.columns(2)
                with col1:
                    employee = st.selectbox(
                        "Employee",
                        options=list(employee_options.keys()),
                        format_func=lambda x: employee_options[x]
                    )
                    schedule_date = st.date_input(
                        "Date",
                        min_value=start_date,
                        max_value=end_date
                    )
                
                with col2:
                    # Time selection  editable
                    start_time = st.time_input("Start Time", value=time(8, 0), step=1800)
                    end_time = st.time_input("End Time", value=time(17, 0), step=1800)
                
                notes = st.text_input("Notes (optional)")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Save Schedule"):
                        try:
                            # Validate time range
                            if start_time >= end_time:
                                st.error("End time must be after start time!")
                            else:
                                # Check for existing schedule
                                existing = session.sql(f"""
                                    SELECT * FROM EMPLOYEE_SCHEDULES
                                    WHERE EMPLOYEEID = '{employee}'
                                    AND SCHEDULE_DATE = '{schedule_date}'
                                """).collect()
                                
                                if existing:
                                    # Update existing schedule
                                    session.sql(f"""
                                        UPDATE EMPLOYEE_SCHEDULES
                                        SET 
                                            START_TIME = '{start_time}',
                                            END_TIME = '{end_time}',
                                            NOTES = '{notes.replace("'", "''")}'
                                        WHERE SCHEDULEID = '{existing[0]['SCHEDULEID']}'
                                    """).collect()
                                    st.success("Schedule updated successfully!")
                                else:
                                    # Create new schedule
                                    schedule_id = f"SCH{datetime.now().timestamp()}"
                                    session.sql(f"""
                                        INSERT INTO EMPLOYEE_SCHEDULES (
                                            SCHEDULEID, EMPLOYEEID, SCHEDULE_DATE, 
                                            START_TIME, END_TIME, NOTES
                                        ) VALUES (
                                            '{schedule_id}',
                                            '{employee}',
                                            '{schedule_date}',
                                            '{start_time}',
                                            '{end_time}',
                                            '{notes.replace("'", "''")}'
                                        )
                                    """).collect()
                                    st.success("Schedule added successfully!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error saving schedule: {str(e)}")
                
                with col2:
                    if st.form_submit_button("Remove Schedule"):
                        try:
                            session.sql(f"""
                                DELETE FROM EMPLOYEE_SCHEDULES
                                WHERE EMPLOYEEID = '{employee}'
                                AND SCHEDULE_DATE = '{schedule_date}'
                            """).collect()
                            st.success("Schedule removed successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error removing schedule: {str(e)}")


    else:
        # Standard table management for all other tables
        st.subheader(f"Manage {selected_table.capitalize().replace('_', ' ')}")
        
        try:
            # Fetch data from selected table
            table_data = session.table(selected_table).collect()
            
            if table_data:
                # Convert to pandas DataFrame for better display
                df = pd.DataFrame(table_data)
                st.dataframe(df)
               
            else:
                st.info(f"No data found in {selected_table}")
        
        except Exception as e:
            st.error(f"Error accessing table: {str(e)}")
        
        # Add new record
        with st.expander("➕ Add New Record"):
            with st.form(f"add_{selected_table}_form"):
                # Get table columns
                columns = session.table(selected_table).columns
                input_values = {}
                
                for col in columns:
                    if col.upper().endswith("ID") and col.upper() != "EMPLOYEEID":  # Skip auto-generated ID fields
                        continue
                    input_values[col] = st.text_input(f"{col}")
                
                if st.form_submit_button("Add Record"):
                    try:
                        # Generate ID if not provided
                        if "ID" in [c.upper() for c in columns] and not input_values.get(columns[0]):
                            input_values[columns[0]] = f"{selected_table.split('_')[-1]}_{datetime.now().timestamp()}"
                        
                        # Build SQL query
                        columns_str = ", ".join([f'"{col}"' for col in input_values.keys() if input_values[col]])
                        values_str = ", ".join([f"'{input_values[col]}'" for col in input_values.keys() if input_values[col]])
                        
                        session.sql(f"""
                            INSERT INTO {selected_table} 
                            ({columns_str})
                            VALUES ({values_str})
                        """).collect()
                        st.success("Record added successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding record: {str(e)}")
        
        # Edit/Delete record
        if table_data:
            with st.expander("✏️ Edit/Delete Record"):
                columns = session.table(selected_table).columns
                selected_record = st.selectbox(
                    f"Select Record to Edit/Delete",
                    options=[row[columns[0]] for row in table_data],
                    key=f"record_select_{selected_table}"
                )
                
                if selected_record:
                    record_data = [row for row in table_data if row[columns[0]] == selected_record][0]
                    
                    with st.form(f"edit_{selected_table}_form"):
                        # Dynamically create input fields for editing
                        edit_values = {}
                        for col in columns:
                            if col.upper().endswith("ID"):  # Skip ID fields (read-only)
                                st.text_input(f"{col} (Read-Only)", value=record_data[col], disabled=True)
                            else:
                                edit_values[col] = st.text_input(f"{col}", value=record_data[col])
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Update Record"):
                                try:
                                    set_clause = ", ".join([f'"{col}" = \'{edit_values[col]}\'' for col in edit_values.keys()])
                                    session.sql(f"""
                                        UPDATE {selected_table} 
                                        SET {set_clause}
                                        WHERE "{columns[0]}" = '{selected_record}'
                                    """).collect()
                                    st.success("Record updated successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error updating record: {str(e)}")
                        with col2:
                            if st.form_submit_button("Delete Record"):
                                try:
                                    session.sql(f"""
                                        DELETE FROM {selected_table} 
                                        WHERE "{columns[0]}" = '{selected_record}'
                                    """).collect()
                                    st.success("Record deleted successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting record: {str(e)}")
   

#######################################################################
# Main app function

def main_app():
    st.sidebar.title(f"Welcome {st.session_state.user_name}")

    # Available tabs based on roles
    available_tabs = set()
    for role in st.session_state.roles:
        available_tabs.update(ROLE_ACCESS.get(role.lower(), []))

    # Add the "profile" tab for all employees
    available_tabs.add("profile")

    # Define tab order
    tab_order = ['Home', 'profile', 'customers', 'appointments','customer_info', 
                'admin_tables', 'quote', 'estimate_report', 'technician_installation_report',
               'jobs', 'invoices', 'payments', 'service_history']    
    available_tabs = [tab for tab in tab_order if tab in available_tabs]


   # Check if we're being redirected from customer management
    if 'active_tab' in st.session_state:
        selected_tab = st.session_state['active_tab']
    else:
        selected_tab = st.sidebar.selectbox("Navigation", available_tabs)

   

    if selected_tab == 'Home':
        Home()
    elif selected_tab == 'profile':
        profile_page()    
    elif selected_tab == 'customers':
        customer_management()

    elif selected_tab == 'customer_info':
        customer_info()
    
    elif selected_tab == 'appointments':
        appointments()
    elif selected_tab == 'technician_installation_report':
        technician_installation_report()
        
    elif selected_tab == 'estimate_report':
        estimate_report()
    elif selected_tab == 'quote':
        quote()

    elif selected_tab == 'admin_tables':
        admin_tables()  # Now this is defined before being called

    elif selected_tab == 'jobs':
        jobs_management()
    elif selected_tab == 'invoices':
        invoices_management()
    elif selected_tab == 'payShow Column Namesments':
        payments_management()
    elif selected_tab == 'service_history':
        service_history()
# Clear the active tab after use
    if 'active_tab' in st.session_state:
        del st.session_state['active_tab']

    

    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

# Main app flow
if __name__ == '__main__':
    query_params = st.query_params
    if 'reset_token' in query_params:
        reset_password(query_params['reset_token'])
    elif not st.session_state.get('logged_in'):
        login_page()
    else:
        main_app()
        
        
        
