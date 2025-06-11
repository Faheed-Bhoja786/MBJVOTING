from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify
import os
import logging
import hashlib
import secrets
import datetime
import re
from functools import wraps
from sqlalchemy import func
from models import db, Voter, Vote, Admin, ElectionStatus

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", secrets.token_hex(16))

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///election.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

# Ensure static folder exists
if not os.path.exists('static'):
    os.makedirs('static')

# Party details
parties = {
    "Team Sayani": {
        "image": "teamsayani.jpeg",
        "votes": 0
    },
    "Team Opposition": {
        "image": "teamopposition.jpeg",
        "votes": 0
    }
}

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

@app.route("/", methods=["GET", "POST"])
def index():
    message = ""
    message_class = ""

    # Get election status
    status = get_election_status()

    # Redirect to winner page if winner is declared
    if status.winner:
        return redirect(url_for('winner', party=status.winner))

    # If voting is closed
    if not status.is_open:
        message = "Voting is currently closed."
        message_class = "error"
    else:
        if request.method == "POST":
            voter_id = request.form["voter_id"].strip()
            selected_party = request.form["vote"]

            # Input validation
            if len(voter_id) < 8 or len(voter_id) > 9 or not voter_id.isdigit():
                message = "ID must be 8 or 9 digits."
                message_class = "error"
            else:
                # Check if the voter has already voted
                existing_voter = Voter.query.filter_by(voter_id=voter_id).first()

                if existing_voter:
                    message = "You have already voted."
                    message_class = "error"
                else:
                    try:
                        # Create a new voter record
                        new_voter = Voter(voter_id=voter_id, party=selected_party)
                        db.session.add(new_voter)

                        # Record the vote
                        new_vote = Vote(party=selected_party)
                        db.session.add(new_vote)

                        # Commit changes to the database
                        db.session.commit()

                        message = "Thank you for voting!"
                        message_class = "success"
                    except Exception as e:
                        db.session.rollback()
                        message = "Error recording vote. Please try again."
                        message_class = "error"

    # Get current vote counts more efficiently with a single query
    vote_counts = {}
    party_counts = db.session.query(Vote.party, func.count(Vote.id)).group_by(Vote.party).all()
    for party, count in party_counts:
        vote_counts[party] = count

    # Prepare data for the template
    display_data = {}
    for party in parties:
        display_data[party] = {
            "image": parties[party]["image"],
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

    return render_template(
        "vote.html", 
        votes=display_data, 
        message=message, 
        message_class=message_class,
        admin_message=status.message,
        countdown_html=countdown_html,
        election_open=status.is_open
    )

@app.route("/admin", methods=["GET"])
def admin_redirect():
    return redirect(url_for('admin_login'))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        password = request.form.get("password")

        # Fixed admin password as requested
        if password == "10032010":
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid password"

    return render_template("admin.html", error=error, login_page=True)

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    # Get vote counts for each party with a single query
    vote_counts = {}
    party_counts = db.session.query(Vote.party, func.count(Vote.id)).group_by(Vote.party).all()
    for party, count in party_counts:
        vote_counts[party] = count

    # Get total number of voters with a more efficient query
    total_voters = db.session.query(func.count(Voter.id)).scalar()

    # Calculate total votes and percentages
    total_votes = sum(vote_counts.values())
    vote_data = {}

    for party in parties:
        vote_count = vote_counts.get(party, 0)
        percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
        vote_data[party] = {
            "count": vote_count,
            "percentage": round(percentage, 1)
        }

    # Get all voters and their votes for the database view
    all_voters = Voter.query.order_by(Voter.voted_at.desc()).all()

    # Get current election status
    status = get_election_status()

    # Calculate the countdown status
    countdown_active = False
    time_remaining = None

    if status.countdown_end and status.countdown_end > datetime.datetime.now():
        countdown_active = True
        time_remaining = status.countdown_end - datetime.datetime.now()
        time_remaining = time_remaining.total_seconds() // 60  # Convert to minutes

    return render_template(
        "admin.html", 
        vote_data=vote_data, 
        total_voters=total_voters,
        total_votes=total_votes,
        all_voters=all_voters,
        election_open=status.is_open,
        admin_message=status.message,
        countdown_active=countdown_active,
        time_remaining=time_remaining,
        winner=status.winner,
        login_page=False
    )

@app.route("/admin/reset", methods=["POST"])
@admin_required
def admin_reset():
    confirmation = request.form.get("confirmation")

    if confirmation == "RESET":
        # Delete all votes and voters from the database
        Vote.query.delete()
        Voter.query.delete()

        # Reset the election status
        status = get_election_status()
        status.is_open = True
        status.message = None
        status.countdown_end = None
        status.winner = None

        db.session.commit()

        flash("All votes have been reset successfully", "success")
    else:
        flash("Invalid confirmation text. Votes were not reset.", "error")

    return redirect(url_for('admin_dashboard'))

@app.route("/admin/message", methods=["POST"])
@admin_required
def admin_message():
    message = request.form.get("message", "").strip()

    status = get_election_status()
    status.message = message if message else None
    db.session.commit()

    flash("Message updated successfully", "success")
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/toggle_voting", methods=["POST"])
@admin_required
def toggle_voting():
    status = get_election_status()
    status.is_open = not status.is_open
    db.session.commit()

    state = "opened" if status.is_open else "closed"
    flash(f"Voting has been {state} successfully", "success")
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/countdown", methods=["POST"])
@admin_required
def start_countdown():
    minutes = int(request.form.get("minutes", 5))

    status = get_election_status()
    status.countdown_end = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    db.session.commit()

    flash(f"Countdown timer for {minutes} minutes has been started", "success")
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/declare_winner", methods=["POST"])
@admin_required
def declare_winner():
    confirmation = request.form.get("confirmation")

    if confirmation != "CONFIRM":
        flash("Please type CONFIRM to declare the winner", "error")
        return redirect(url_for('admin_dashboard'))

    # Get vote counts
    vote_counts = db.session.query(Vote.party, func.count(Vote.id)).group_by(Vote.party).all()
    
    if not vote_counts:
        flash("No votes recorded yet", "error")
        return redirect(url_for('admin_dashboard'))

    # Find winner(s)
    max_votes = max(count for _, count in vote_counts)
    winners = [party for party, count in vote_counts if count == max_votes]
    
    # Update election status
    status = get_election_status()
    status.winner = " & ".join(winners)
    status.is_open = False
    status.countdown_end = None
    db.session.commit()

    flash("Winner has been declared!", "success")
    return redirect(url_for('winner', party=status.winner))

@app.route("/check_winner_status")
def check_winner_status():
    status = get_election_status()
    
    # Check if countdown has ended
    if status.countdown_end and datetime.datetime.now() >= status.countdown_end:
        if not status.winner:  # Only set winner if not already set
            # Get vote counts
            vote_counts = {}
            party_counts = db.session.query(Vote.party, func.count(Vote.id)).group_by(Vote.party).all()
            for party, count in party_counts:
                vote_counts[party] = count

            if vote_counts:
                # Find the highest vote count
                max_votes = max(vote_counts.values())
                # Get all parties with the highest vote count
                winners = [party for party, count in vote_counts.items() if count == max_votes]
                status.winner = " & ".join(winners)  # Join multiple winners with &
                status.is_open = False
                status.countdown_end = None  # Clear countdown
                db.session.commit()

        if status.winner:  # Check if winner is set
            return jsonify({"redirect": url_for('winner', party=status.winner)})

    return jsonify({
        "redirect": None,
        "countdown": {
            "seconds_remaining": int((status.countdown_end - datetime.datetime.now()).total_seconds()) if status.countdown_end else None
        } if status.countdown_end else None
    })

@app.route("/admin/cancel_winner", methods=["POST"])
@admin_required
def cancel_winner():
    status = get_election_status()
    status.winner = None
    db.session.commit()

    flash("Winner declaration has been cancelled", "success")
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route("/winner/<party>")
def winner(party):
    """Display the winner page with confetti"""
    # Get election status to verify winner
    status = get_election_status()
    if not status.winner:
        return redirect(url_for('index'))

    # Verify that this is a valid party
    if party not in parties:
        return redirect(url_for('index'))

    # Get current vote counts with a single efficient query
    vote_counts = {}
    party_counts = db.session.query(Vote.party, func.count(Vote.id)).group_by(Vote.party).all()
    for party, count in party_counts:
        vote_counts[party] = count

    # Prepare data for the template
    display_data = {}
    for p in parties:
        display_data[p] = {
            "image": parties[p]["image"],
            "count": vote_counts.get(p, 0)
        }

    return render_template(
        "winner.html", 
        winner=party,
        winner_image=parties[party]["image"],
        votes=display_data
    )

@app.route("/get_vote_counts")
def get_vote_counts():
    """API endpoint to get current vote counts for AJAX updates"""
    # Get current election status
    status = get_election_status()

    # Get current vote counts with a single efficient query
    vote_counts = {}
    party_counts = db.session.query(Vote.party, func.count(Vote.id)).group_by(Vote.party).all()
    for party, count in party_counts:
        vote_counts[party] = count

    # Prepare data for JSON response
    display_data = {}
    for party in parties:
        display_data[party] = {
            "count": vote_counts.get(party, 0)
        }

    # Add countdown timer info if it exists
    countdown_info = None
    if status.countdown_end and status.countdown_end > datetime.datetime.now():
        countdown_info = {
            "end_time": status.countdown_end.strftime("%B %d, %Y %H:%M:%S"),
            "seconds_remaining": int((status.countdown_end - datetime.datetime.now()).total_seconds())
        }

    # Return JSON response with all necessary data
    return jsonify({
        "votes": display_data,
        "admin_message": status.message,
        "election_open": status.is_open,
        "winner": status.winner,
        "countdown": countdown_info
    })

# Create database tables and initial election status
with app.app_context():
    db.create_all()

    # Initialize election status if it doesn't exist
    if not ElectionStatus.query.first():
        status = ElectionStatus(is_open=True)
        db.session.add(status)
        db.session.commit()
        logging.info("Created initial election status")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)