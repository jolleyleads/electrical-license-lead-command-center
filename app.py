from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hashlib
import os

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///electrical_leads.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

HIGH_INTENT_KEYWORDS = [
    "licensed electrical contractor",
    "master electrician",
    "electrical qualifier",
    "qualifying master electrician",
    "need electrical license",
    "electrical license holder",
    "need ec license",
    "permit electrical contractor",
    "need contractor license",
    "looking for electrical contractor",
    "licensed electrician needed",
    "need license for permit",
    "texas electrical contractor",
    "virginia electrical contractor"
]

MEDIUM_INTENT_KEYWORDS = [
    "electrical subcontractor",
    "electrician needed",
    "commercial electrical",
    "residential electrical",
    "electrical work",
    "contractor needed",
    "permit help",
    "licensed trade partner"
]

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.String(80), unique=True)
    company = db.Column(db.String(200))
    contact_name = db.Column(db.String(200))
    phone = db.Column(db.String(80))
    email = db.Column(db.String(200))
    city = db.Column(db.String(120))
    state = db.Column(db.String(80))
    source = db.Column(db.String(200))
    need = db.Column(db.Text)
    license_state_needed = db.Column(db.String(80))
    intent_score = db.Column(db.Integer)
    priority = db.Column(db.String(80))
    recommended_action = db.Column(db.Text)
    status = db.Column(db.String(80), default="New")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(120))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def make_lead_id(company, phone, email, need):
    raw = f"{company}|{phone}|{email}|{need}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

def score_intent(text):
    text_lower = (text or "").lower()
    score = 20

    for keyword in HIGH_INTENT_KEYWORDS:
        if keyword in text_lower:
            score += 18

    for keyword in MEDIUM_INTENT_KEYWORDS:
        if keyword in text_lower:
            score += 8

    if "asap" in text_lower or "urgent" in text_lower or "immediately" in text_lower:
        score += 15

    if "permit" in text_lower:
        score += 12

    if "license" in text_lower or "licensed" in text_lower:
        score += 15

    if score > 100:
        score = 100

    if score >= 75:
        priority = "High"
        action = "High intent: call or email today. Position as licensed electrical contractor coverage for qualified projects."
    elif score >= 45:
        priority = "Medium"
        action = "Medium intent: create outreach draft and follow up within 48 hours."
    else:
        priority = "Low"
        action = "Low intent: save for monitoring or future nurture."

    return score, priority, action

def sample_leads():
    examples = [
        {
            "company": "Prime Build Contractors",
            "contact_name": "Operations Manager",
            "phone": "",
            "email": "",
            "city": "Richmond",
            "state": "VA",
            "source": "Manual Lead Example",
            "need": "Looking for a licensed electrical contractor in Virginia for permit support on commercial buildouts.",
            "license_state_needed": "Virginia"
        },
        {
            "company": "Lone Star Renovation Group",
            "contact_name": "Project Lead",
            "phone": "",
            "email": "",
            "city": "Dallas",
            "state": "TX",
            "source": "Manual Lead Example",
            "need": "Need master electrician or electrical contractor license holder for Texas projects ASAP.",
            "license_state_needed": "Texas"
        },
        {
            "company": "Coastal Development Services",
            "contact_name": "Hiring Manager",
            "phone": "",
            "email": "",
            "city": "Virginia Beach",
            "state": "VA",
            "source": "Manual Lead Example",
            "need": "Need electrical subcontractor for residential projects. Licensed trade partner preferred.",
            "license_state_needed": "Virginia"
        }
    ]

    for item in examples:
        lead_id = make_lead_id(item["company"], item["phone"], item["email"], item["need"])
        existing = Lead.query.filter_by(lead_id=lead_id).first()

        if not existing:
            score, priority, action = score_intent(item["need"])

            lead = Lead(
                lead_id=lead_id,
                company=item["company"],
                contact_name=item["contact_name"],
                phone=item["phone"],
                email=item["email"],
                city=item["city"],
                state=item["state"],
                source=item["source"],
                need=item["need"],
                license_state_needed=item["license_state_needed"],
                intent_score=score,
                priority=priority,
                recommended_action=action,
                status="New",
                notes="Seed lead for demo"
            )

            db.session.add(lead)

    db.session.commit()

@app.before_request
def setup():
    db.create_all()
    if Lead.query.count() == 0:
        sample_leads()

@app.route("/")
def index():
    leads = Lead.query.order_by(Lead.intent_score.desc(), Lead.created_at.desc()).all()
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
    return render_template("index.html", leads=leads, logs=logs)

@app.route("/api/leads", methods=["GET"])
def get_leads():
    state = request.args.get("state", "").lower()
    priority = request.args.get("priority", "").lower()

    query = Lead.query

    if state:
        query = query.filter(Lead.state.ilike(f"%{state}%"))

    if priority:
        query = query.filter(Lead.priority.ilike(f"%{priority}%"))

    leads = query.order_by(Lead.intent_score.desc()).all()

    return jsonify({
        "count": len(leads),
        "leads": [
            {
                "id": lead.lead_id,
                "company": lead.company,
                "contact_name": lead.contact_name,
                "phone": lead.phone,
                "email": lead.email,
                "city": lead.city,
                "state": lead.state,
                "source": lead.source,
                "need": lead.need,
                "license_state_needed": lead.license_state_needed,
                "intent_score": lead.intent_score,
                "priority": lead.priority,
                "recommended_action": lead.recommended_action,
                "status": lead.status,
                "notes": lead.notes
            }
            for lead in leads
        ]
    })

@app.route("/api/score", methods=["POST"])
def score_lead():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    score, priority, action = score_intent(text)

    return jsonify({
        "intent_score": score,
        "priority": priority,
        "recommended_action": action
    })

@app.route("/api/add-lead", methods=["POST"])
def add_lead():
    data = request.get_json(silent=True) or {}

    company = data.get("company", "Unknown Company")
    phone = data.get("phone", "")
    email = data.get("email", "")
    need = data.get("need", "")

    lead_id = make_lead_id(company, phone, email, need)

    existing = Lead.query.filter_by(lead_id=lead_id).first()
    if existing:
        return jsonify({
            "status": "duplicate",
            "message": "Lead already exists",
            "lead_id": lead_id
        })

    score, priority, action = score_intent(need)

    lead = Lead(
        lead_id=lead_id,
        company=company,
        contact_name=data.get("contact_name", ""),
        phone=phone,
        email=email,
        city=data.get("city", ""),
        state=data.get("state", ""),
        source=data.get("source", "Manual/API"),
        need=need,
        license_state_needed=data.get("license_state_needed", ""),
        intent_score=score,
        priority=priority,
        recommended_action=action,
        status=data.get("status", "New"),
        notes=data.get("notes", "")
    )

    db.session.add(lead)

    log = ActivityLog(
        event_type="lead_added",
        details=f"Added lead: {company} with {priority} priority and score {score}"
    )

    db.session.add(log)
    db.session.commit()

    return jsonify({
        "status": "saved",
        "lead_id": lead_id,
        "intent_score": score,
        "priority": priority,
        "recommended_action": action
    })

@app.route("/api/update-lead", methods=["POST"])
def update_lead():
    data = request.get_json(silent=True) or {}
    lead_id = data.get("id")

    lead = Lead.query.filter_by(lead_id=lead_id).first()

    if not lead:
        return jsonify({"status": "not_found"}), 404

    lead.status = data.get("status", lead.status)
    lead.notes = data.get("notes", lead.notes)

    log = ActivityLog(
        event_type="lead_updated",
        details=f"Updated lead {lead.company} to status {lead.status}"
    )

    db.session.add(log)
    db.session.commit()

    return jsonify({"status": "updated", "lead_id": lead_id})

@app.route("/api/outreach-draft", methods=["POST"])
def outreach_draft():
    data = request.get_json(silent=True) or {}

    company = data.get("company", "your company")
    need = data.get("need", "licensed electrical contractor support")
    state = data.get("state", "your state")

    subject = f"Licensed Electrical Contractor Coverage for {company}"

    body = f"""Hi,

I saw that {company} may be looking for licensed electrical contractor support.

We work with qualified contractors who need licensed electrical contractor coverage for projects, permits, and compliant electrical work in states such as {state}.

If you are currently looking for a licensed electrical contractor partner, I would be open to a quick conversation to see whether there is a fit.

Best,
Licensed Electrical Contractor Partner Team
"""

    return jsonify({
        "subject": subject,
        "body": body,
        "note": "Draft only. Human approval recommended before sending."
    })

@app.route("/api/health")
def health():
    return jsonify({
        "status": "Electrical License Lead Command Center online",
        "leads_endpoint": "/api/leads",
        "add_lead_endpoint": "/api/add-lead",
        "score_endpoint": "/api/score"
    })

if __name__ == "__main__":
    app.run(debug=True)
