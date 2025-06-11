from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify, Response
import os
import logging
import hashlib
import secrets
import datetime
import re
import uuid
import json
import pytz
import time
from functools import wraps
from sqlalchemy import func
from werkzeug.utils import secure_filename
from models import db, Voter, Vote, Admin, ElectionStatus, Party, PartyMember, SiteSettings, MusicSettings

# Set Nairobi timezone
NAIROBI_TZ = pytz.timezone('Africa/Nairobi')

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", secrets.token_hex(16))

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///election.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

# Ensure static folder exists
if not os.path.exists('static'):
    os.makedirs('static')

# Global parties dictionary - will be populated from database
global_parties = {}

# Create a password hash instead of storing in plain text
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# Admin login required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# Get current election status
def get_election_status():
    status = ElectionStatus.query.first()
    if not status:
        status = ElectionStatus(is_open=True)
        db.session.add(status)
        db.session.commit()
    return status

# Get site settings
def get_site_settings():
    settings = SiteSettings.query.first()
    if not settings:
        settings = SiteSettings()
        db.session.add(settings)
        db.session.commit()
    return settings

# Get music settings
def get_music_settings():
    settings = MusicSettings.query.first()
    if not settings:
        settings = MusicSettings(enabled=False)
        db.session.add(settings)
        db.session.commit()
    return settings


@app.route("/", methods=["GET", "POST"])
def index():
    message = ""
    message_class = ""

    # Get election status and site settings
    status = get_election_status()
    site_settings = get_site_settings()

    # Always reload parties from database on index page to ensure we have the latest
    global global_parties
    db_parties = Party.query.all()
    if db_parties:
        # Update global_parties with latest from database
        global_parties = {}
        for party in db_parties:
            global_parties[party.name] = {
                "image": party.image,
                "votes": 0  # Will be updated with vote counts
            }

    # If voting is closed
    if not status.is_open:
        message = "Voting is currently closed."
        message_class = "error"
    else:
        if request.method == "POST":
            voter_id = request.form["voter_id"].strip()
            voter_name = request.form.get("voter_name", "").strip()
            selected_party = request.form["vote"]

            # Input validation - ensuring ID is exactly 8 or 9 digits using regex
            if not re.match(r'^\d{8,9}$', voter_id):
                message = "ID must be exactly 8 or 9 digits."
                message_class = "error"
            elif not voter_name:
                message = "Please enter your name."
                message_class = "error"
            else:
                # Check if the voter has already voted
                existing_voter = Voter.query.filter_by(
                    voter_id=voter_id).first()

                if existing_voter:
                    message = "You have already voted."
                    message_class = "error"
                else:
                    try:
                        # Create a new voter record
                        new_voter = Voter(voter_id=voter_id,
                                          party=selected_party,
                                          name=voter_name)
                        db.session.add(new_voter)

                        # Record the vote
                        new_vote = Vote(party=selected_party)
                        db.session.add(new_vote)

                        # Commit changes to the database
                        db.session.commit()

                        # Store success message in session
                        session['vote_message'] = f"Thank you for voting, {voter_name}!"
                        session['message_class'] = "success"

                        # Redirect to prevent form resubmission
                        return redirect(url_for('index'))
                    except Exception as e:
                        db.session.rollback()
                        message = "Error recording vote. Please try again."
                        message_class = "error"

    # Get current vote counts more efficiently with a single query
    vote_counts = {}
    party_counts = db.session.query(Vote.party, func.count(Vote.id)).group_by(
        Vote.party).all()
    for party, count in party_counts:
        vote_counts[party] = count

    # Prepare data for the template
    display_data = {}
    for party in global_parties:
        display_data[party] = {
            "image": global_parties[party]["image"],
            "count": vote_counts.get(party, 0)
        }

    # Calculate countdown end time if it exists
    countdown_html = ""
    if status.countdown_end and status.countdown_end > datetime.datetime.now():
        countdown_date = status.countdown_end.strftime("%B %d, %Y %H:%M:%S")
        countdown_html = f"""
        <div id="countdown" class="countdown">
            <p>Voting closes in <span id="countdown-timer"></span></p>
        </div>
        <script>
            const countdownDate = new Date("{countdown_date}").getTime();

            const countdownTimer = setInterval(function() {{
                const now = new Date().getTime();
                const distance = countdownDate - now;

                const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((distance % (1000 * 60)) / 1000);

                document.getElementById("countdown-timer").innerHTML = minutes + "m " + seconds + "s";

                if (distance < 0) {{
                    clearInterval(countdownTimer);
                    document.getElementById("countdown").innerHTML = "<p>Voting is now closed. Refresh the page.</p>";
                    setTimeout(function() {{
                        window.location.reload();
                    }}, 3000);
                }}
            }}, 1000);
        </script>
        """

    # Get flash message from session
    message = session.pop('vote_message', None)
    message_class = session.pop('message_class', None)

    return render_template("vote.html",
                           votes=display_data,
                           message=message,
                           message_class=message_class,
                           admin_message=status.message,
                           countdown_html=countdown_html,
                           election_open=status.is_open,
                           site_title=site_settings.site_title,
                           site_subtitle=site_settings.site_subtitle,
                           logo_path=site_settings.logo_path,
                           settings=site_settings)


@app.route("/live-results")
def live_results():
    """Display live election results"""
    status = get_election_status()
    site_settings = get_site_settings()
    
    # If a winner is declared, redirect to the winner celebration page
    if status.winner:
        return redirect("/winner-view")
    
    # Add timestamp for cache busting
    now = int(time.time())
    
    # Normal live results page (only shown when no winner)
    return render_template("live_results.html",
                         election_open=status.is_open,
                         winner=None,
                         site_title=site_settings.site_title,
                         site_subtitle=site_settings.site_subtitle,
                         logo_path=site_settings.logo_path,
                         settings=site_settings,
                         now=now)

@app.route("/winner-view")
def winner_view():
    """Display winner celebration view"""
    status = get_election_status()
    site_settings = get_site_settings()
    
    # If no winner, redirect back to live results
    if not status.winner:
        return redirect("/live-results")
    
    # Get winner party data
    winner_party_data = {}
    party_members = {}
    
    # Get data for all parties to find winner
    for party_name in global_parties:
        winner_party_data[party_name] = {
            "image": global_parties[party_name]["image"]
        }
        
        # Get party members
        members = PartyMember.query.filter_by(party_name=party_name).all()
        party_members[party_name] = members
    
    # Add timestamp for cache busting
    now = int(time.time())
    
    return render_template("live_results.html",
                         election_open=status.is_open,
                         winner=status.winner,
                         winner_party_data=winner_party_data,
                         party_members=party_members,
                         site_title=site_settings.site_title,
                         site_subtitle=site_settings.site_subtitle,
                         logo_path=site_settings.logo_path,
                         settings=site_settings,
                         now=now)

@app.route("/admin", methods=["GET"])
def admin_redirect():
    return redirect(url_for('admin_login'))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    site_settings = get_site_settings()
    
    if request.method == "POST":
        password = request.form.get("password")

        # Fixed admin password as requested
        if password == "10032010":
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid password"

    return render_template("admin.html", 
                          error=error, 
                          login_page=True,
                          settings=site_settings)


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    # Get vote counts for active parties only
    vote_counts = {}
    party_counts = db.session.query(Vote.party, func.count(Vote.id)).group_by(
        Vote.party).all()

    # Only count votes for parties that still exist
    total_valid_votes = 0
    for party, count in party_counts:
        if party in global_parties:
            vote_counts[party] = count
            total_valid_votes += count

    # Get total number of voters
    total_voters = db.session.query(func.count(Voter.id)).scalar()

    # Use valid votes total instead of all votes
    total_votes = total_valid_votes
    vote_data = {}
    
    for party in global_parties:
        vote_count = vote_counts.get(party, 0)
        percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
        vote_data[party] = {
            "count": vote_count,
            "percentage": round(percentage, 1)
        }

    # Get all voters and their votes for the database view
    all_voters = Voter.query.order_by(Voter.voted_at.desc()).all()

    # Convert all timestamps to Nairobi timezone
    for voter in all_voters:
        if voter.voted_at:
            # Convert UTC time to Nairobi time
            voter.voted_at = voter.voted_at.replace(tzinfo=pytz.UTC).astimezone(NAIROBI_TZ)

    # Get current election status and site settings
    status = get_election_status()
    site_settings = get_site_settings()

    # Calculate the countdown status
    countdown_active = False
    time_remaining = None

    if status.countdown_end and status.countdown_end > datetime.datetime.now():
        countdown_active = True
        time_remaining = status.countdown_end - datetime.datetime.now()
        time_remaining = time_remaining.total_seconds() // 60  # Convert to minutes

    # Get party members for the party information section
    parties_with_members = {}
    for party_name in global_parties:
        members = PartyMember.query.filter_by(party_name=party_name).all()
        parties_with_members[party_name] = members

    return render_template("admin.html",
                         vote_data=vote_data,
                         total_votes=total_votes,
                         total_voters=total_voters,
                         all_voters=all_voters,
                         status=status,
                         countdown_active=countdown_active,
                         time_remaining=time_remaining,
                         parties_with_members=parties_with_members,
                         settings=site_settings)


@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route("/admin/toggle-election", methods=["POST"])
@admin_required
def toggle_election():
    status = get_election_status()
    status.is_open = not status.is_open
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/set-message", methods=["POST"])
@admin_required
def set_admin_message():
    status = get_election_status()
    status.message = request.form.get("message", "")
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/set-countdown", methods=["POST"])
@admin_required
def set_countdown():
    status = get_election_status()
    minutes = request.form.get("minutes", type=int)
    
    if minutes and minutes > 0:
        status.countdown_end = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    else:
        status.countdown_end = None
    
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/declare-winner", methods=["POST"])
@admin_required
def declare_winner():
    status = get_election_status()
    winner = request.form.get("winner")
    
    if winner:
        status.winner = winner
        status.is_open = False  # Close voting when winner is declared
        db.session.commit()
        
        # Log winner declaration
        with open("winner_declared.txt", "w") as f:
            f.write(f"Winner declared at {datetime.datetime.now()}")
    
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/cancel-winner", methods=["POST"])
@admin_required
def cancel_winner():
    status = get_election_status()
    status.winner = None
    db.session.commit()
    
    # Log winner cancellation
    with open("winner_cancelled.txt", "w") as f:
        f.write(f"Winner declaration cancelled at {datetime.datetime.now()}")
    
    return redirect(url_for('admin_dashboard'))


# API endpoints for live data
@app.route("/api/live-results")
def api_live_results():
    """API endpoint for live election results"""
    # Get current vote counts
    vote_counts = {}
    party_counts = db.session.query(Vote.party, func.count(Vote.id)).group_by(
        Vote.party).all()
    
    total_votes = 0
    for party, count in party_counts:
        if party in global_parties:
            vote_counts[party] = count
            total_votes += count

    # Prepare response data
    results = {}
    for party in global_parties:
        vote_count = vote_counts.get(party, 0)
        percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
        results[party] = {
            "votes": vote_count,
            "percentage": round(percentage, 1),
            "image": global_parties[party]["image"]
        }

    status = get_election_status()
    
    return jsonify({
        "results": results,
        "total_votes": total_votes,
        "election_open": status.is_open,
        "winner": status.winner,
        "timestamp": int(time.time())
    })


@app.route("/admin/dashboard-data")
@admin_required
def admin_dashboard_data():
    """API endpoint for admin dashboard data"""
    # Get vote counts for active parties only
    vote_counts = {}
    party_counts = db.session.query(Vote.party, func.count(Vote.id)).group_by(
        Vote.party).all()

    # Only count votes for parties that still exist
    total_valid_votes = 0
    for party, count in party_counts:
        if party in global_parties:
            vote_counts[party] = count
            total_valid_votes += count

    # Get total number of voters
    total_voters = db.session.query(func.count(Voter.id)).scalar()

    vote_data = {}
    for party in global_parties:
        vote_count = vote_counts.get(party, 0)
        percentage = (vote_count / total_valid_votes * 100) if total_valid_votes > 0 else 0
        vote_data[party] = {
            "count": vote_count,
            "percentage": round(percentage, 1)
        }

    return jsonify({
        "vote_data": vote_data,
        "total_votes": total_valid_votes,
        "total_voters": total_voters,
        "timestamp": int(time.time())
    })


# Party management routes
@app.route("/admin/add-party", methods=["POST"])
@admin_required
def add_party():
    party_name = request.form.get("party_name", "").strip()
    party_image = request.form.get("party_image", "").strip()
    
    if party_name and party_image:
        # Check if party already exists
        existing_party = Party.query.filter_by(name=party_name).first()
        if not existing_party:
            new_party = Party(name=party_name, image=party_image)
            db.session.add(new_party)
            db.session.commit()
            
            # Update global_parties
            global_parties[party_name] = {
                "image": party_image,
                "votes": 0
            }
    
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/delete-party", methods=["POST"])
@admin_required  
def delete_party():
    party_name = request.form.get("party_name")
    
    if party_name:
        # Delete from database
        party = Party.query.filter_by(name=party_name).first()
        if party:
            db.session.delete(party)
            db.session.commit()
            
            # Remove from global_parties
            if party_name in global_parties:
                del global_parties[party_name]
    
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/add-party-member", methods=["POST"])
@admin_required
def add_party_member():
    party_name = request.form.get("party_name", "").strip()
    member_name = request.form.get("member_name", "").strip()
    member_position = request.form.get("member_position", "").strip()
    
    if party_name and member_name and member_position:
        new_member = PartyMember(
            party_name=party_name,
            name=member_name,
            position=member_position
        )
        db.session.add(new_member)
        db.session.commit()
    
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/delete-party-member", methods=["POST"])
@admin_required
def delete_party_member():
    member_id = request.form.get("member_id", type=int)
    
    if member_id:
        member = PartyMember.query.get(member_id)
        if member:
            db.session.delete(member)
            db.session.commit()
    
    return redirect(url_for('admin_dashboard'))


# Site settings routes
@app.route("/admin/update-site-settings", methods=["POST"])
@admin_required
def update_site_settings():
    settings = get_site_settings()
    
    settings.site_title = request.form.get("site_title", "").strip() or settings.site_title
    settings.site_subtitle = request.form.get("site_subtitle", "").strip() or settings.site_subtitle
    settings.logo_path = request.form.get("logo_path", "").strip() or settings.logo_path
    settings.theme_color = request.form.get("theme_color", "").strip() or settings.theme_color
    
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


# Initialize database tables
with app.app_context():
    db.create_all()
    
    # Initialize default parties if none exist
    if not Party.query.first():
        default_parties = [
            {"name": "Party A", "image": "https://via.placeholder.com/150x150/FF6B6B/FFFFFF?text=A"},
            {"name": "Party B", "image": "https://via.placeholder.com/150x150/4ECDC4/FFFFFF?text=B"},
            {"name": "Party C", "image": "https://via.placeholder.com/150x150/45B7D1/FFFFFF?text=C"}
        ]
        
        for party_data in default_parties:
            party = Party(name=party_data["name"], image=party_data["image"])
            db.session.add(party)
        
        db.session.commit()
    
    # Load parties into global_parties
    db_parties = Party.query.all()
    for party in db_parties:
        global_parties[party.name] = {
            "image": party.image,
            "votes": 0
        }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
