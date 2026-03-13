from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, date, timedelta
from sqlalchemy import func
import os

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'postgresql://fituser:fitpass@db:5432/fittracker'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ── Models ──────────────────────────────────────────────────────────────────

class Exercise(db.Model):
    __tablename__ = 'exercises'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False, unique=True)
    category    = db.Column(db.String(50), nullable=False)   # strength / cardio / bodyweight / custom
    muscle_group = db.Column(db.String(80))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

class Workout(db.Model):
    __tablename__ = 'workouts'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120))
    workout_date = db.Column(db.Date, nullable=False, default=date.today)
    notes       = db.Column(db.Text)
    duration_min = db.Column(db.Integer)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    sets        = db.relationship('WorkoutSet', backref='workout', lazy=True, cascade='all, delete-orphan')

class WorkoutSet(db.Model):
    __tablename__ = 'workout_sets'
    id          = db.Column(db.Integer, primary_key=True)
    workout_id  = db.Column(db.Integer, db.ForeignKey('workouts.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    set_number  = db.Column(db.Integer, default=1)
    reps        = db.Column(db.Integer)
    weight_kg   = db.Column(db.Float)
    distance_km = db.Column(db.Float)
    duration_sec = db.Column(db.Integer)
    notes       = db.Column(db.String(200))
    exercise    = db.relationship('Exercise')

class BodyWeight(db.Model):
    __tablename__ = 'body_weights'
    id          = db.Column(db.Integer, primary_key=True)
    weight_kg   = db.Column(db.Float, nullable=False)
    logged_date = db.Column(db.Date, nullable=False, default=date.today)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

# ── Helpers ──────────────────────────────────────────────────────────────────

def serialize_exercise(e):
    return {'id': e.id, 'name': e.name, 'category': e.category, 'muscle_group': e.muscle_group}

def serialize_set(s):
    return {
        'id': s.id, 'set_number': s.set_number,
        'exercise_id': s.exercise_id,
        'exercise_name': s.exercise.name if s.exercise else '',
        'exercise_category': s.exercise.category if s.exercise else '',
        'reps': s.reps, 'weight_kg': s.weight_kg,
        'distance_km': s.distance_km, 'duration_sec': s.duration_sec,
        'notes': s.notes
    }

def serialize_workout(w, include_sets=True):
    d = {
        'id': w.id, 'name': w.name,
        'workout_date': w.workout_date.isoformat(),
        'notes': w.notes, 'duration_min': w.duration_min,
        'created_at': w.created_at.isoformat()
    }
    if include_sets:
        d['sets'] = [serialize_set(s) for s in w.sets]
    else:
        d['set_count'] = len(w.sets)
    return d

# ── Exercises ─────────────────────────────────────────────────────────────────

@app.route('/api/exercises', methods=['GET'])
def get_exercises():
    exercises = Exercise.query.order_by(Exercise.category, Exercise.name).all()
    return jsonify([serialize_exercise(e) for e in exercises])

@app.route('/api/exercises', methods=['POST'])
def create_exercise():
    data = request.json
    e = Exercise(name=data['name'], category=data['category'], muscle_group=data.get('muscle_group'))
    db.session.add(e)
    db.session.commit()
    return jsonify(serialize_exercise(e)), 201

@app.route('/api/exercises/<int:eid>', methods=['DELETE'])
def delete_exercise(eid):
    e = Exercise.query.get_or_404(eid)
    db.session.delete(e)
    db.session.commit()
    return jsonify({'deleted': eid})

# ── Workouts ──────────────────────────────────────────────────────────────────

@app.route('/api/workouts', methods=['GET'])
def get_workouts():
    limit = request.args.get('limit', 50, type=int)
    workouts = Workout.query.order_by(Workout.workout_date.desc()).limit(limit).all()
    return jsonify([serialize_workout(w, include_sets=False) for w in workouts])

@app.route('/api/workouts/<int:wid>', methods=['GET'])
def get_workout(wid):
    w = Workout.query.get_or_404(wid)
    return jsonify(serialize_workout(w))

@app.route('/api/workouts', methods=['POST'])
def create_workout():
    data = request.json
    w = Workout(
        name=data.get('name'),
        workout_date=date.fromisoformat(data['workout_date']) if 'workout_date' in data else date.today(),
        notes=data.get('notes'),
        duration_min=data.get('duration_min')
    )
    db.session.add(w)
    db.session.flush()
    for s in data.get('sets', []):
        ws = WorkoutSet(
            workout_id=w.id,
            exercise_id=s['exercise_id'],
            set_number=s.get('set_number', 1),
            reps=s.get('reps'),
            weight_kg=s.get('weight_kg'),
            distance_km=s.get('distance_km'),
            duration_sec=s.get('duration_sec'),
            notes=s.get('notes')
        )
        db.session.add(ws)
    db.session.commit()
    return jsonify(serialize_workout(w)), 201

@app.route('/api/workouts/<int:wid>', methods=['PUT'])
def update_workout(wid):
    w = Workout.query.get_or_404(wid)
    data = request.json
    if 'name' in data: w.name = data['name']
    if 'notes' in data: w.notes = data['notes']
    if 'duration_min' in data: w.duration_min = data['duration_min']
    if 'workout_date' in data: w.workout_date = date.fromisoformat(data['workout_date'])
    if 'sets' in data:
        WorkoutSet.query.filter_by(workout_id=wid).delete()
        for s in data['sets']:
            ws = WorkoutSet(
                workout_id=w.id, exercise_id=s['exercise_id'],
                set_number=s.get('set_number', 1), reps=s.get('reps'),
                weight_kg=s.get('weight_kg'), distance_km=s.get('distance_km'),
                duration_sec=s.get('duration_sec'), notes=s.get('notes')
            )
            db.session.add(ws)
    db.session.commit()
    return jsonify(serialize_workout(w))

@app.route('/api/workouts/<int:wid>', methods=['DELETE'])
def delete_workout(wid):
    w = Workout.query.get_or_404(wid)
    db.session.delete(w)
    db.session.commit()
    return jsonify({'deleted': wid})

# ── Body Weight ───────────────────────────────────────────────────────────────

@app.route('/api/bodyweight', methods=['GET'])
def get_bodyweight():
    entries = BodyWeight.query.order_by(BodyWeight.logged_date.desc()).limit(90).all()
    return jsonify([{'id': e.id, 'weight_kg': e.weight_kg, 'logged_date': e.logged_date.isoformat()} for e in entries])

@app.route('/api/bodyweight', methods=['POST'])
def log_bodyweight():
    data = request.json
    e = BodyWeight(
        weight_kg=data['weight_kg'],
        logged_date=date.fromisoformat(data['logged_date']) if 'logged_date' in data else date.today()
    )
    db.session.add(e)
    db.session.commit()
    return jsonify({'id': e.id, 'weight_kg': e.weight_kg, 'logged_date': e.logged_date.isoformat()}), 201

@app.route('/api/bodyweight/<int:bid>', methods=['DELETE'])
def delete_bodyweight(bid):
    e = BodyWeight.query.get_or_404(bid)
    db.session.delete(e)
    db.session.commit()
    return jsonify({'deleted': bid})

# ── Stats ─────────────────────────────────────────────────────────────────────

@app.route('/api/stats/overview', methods=['GET'])
def stats_overview():
    total_workouts = Workout.query.count()
    total_sets = WorkoutSet.query.count()

    # Streak
    workout_dates = db.session.query(Workout.workout_date).distinct().order_by(Workout.workout_date.desc()).all()
    workout_dates = [r[0] for r in workout_dates]
    streak = 0
    if workout_dates:
        check = date.today()
        for d in workout_dates:
            if d == check or d == check - timedelta(days=1):
                streak += 1
                check = d
            else:
                break

    # PRs - max weight per exercise
    prs = db.session.query(
        Exercise.name,
        func.max(WorkoutSet.weight_kg).label('max_weight')
    ).join(WorkoutSet, WorkoutSet.exercise_id == Exercise.id)\
     .filter(WorkoutSet.weight_kg.isnot(None))\
     .group_by(Exercise.name)\
     .order_by(func.max(WorkoutSet.weight_kg).desc())\
     .limit(10).all()

    # Volume last 12 weeks
    twelve_weeks_ago = date.today() - timedelta(weeks=12)
    volume_rows = db.session.query(
        Workout.workout_date,
        func.sum(WorkoutSet.weight_kg * WorkoutSet.reps).label('volume')
    ).join(WorkoutSet, WorkoutSet.workout_id == Workout.id)\
     .filter(Workout.workout_date >= twelve_weeks_ago)\
     .filter(WorkoutSet.weight_kg.isnot(None))\
     .group_by(Workout.workout_date)\
     .order_by(Workout.workout_date).all()

    # Workouts per week last 12 weeks
    weekly_counts = {}
    wk_rows = db.session.query(Workout.workout_date).filter(Workout.workout_date >= twelve_weeks_ago).all()
    for (d,) in wk_rows:
        iso = d.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        weekly_counts[key] = weekly_counts.get(key, 0) + 1

    # Category distribution
    cat_rows = db.session.query(
        Exercise.category,
        func.count(WorkoutSet.id).label('cnt')
    ).join(WorkoutSet, WorkoutSet.exercise_id == Exercise.id)\
     .group_by(Exercise.category).all()

    # Latest bodyweight
    latest_bw = BodyWeight.query.order_by(BodyWeight.logged_date.desc()).first()

    return jsonify({
        'total_workouts': total_workouts,
        'total_sets': total_sets,
        'current_streak': streak,
        'prs': [{'exercise': r[0], 'max_weight_kg': float(r[1])} for r in prs],
        'volume_over_time': [{'date': str(r[0]), 'volume': float(r[1] or 0)} for r in volume_rows],
        'weekly_frequency': [{'week': k, 'count': v} for k, v in sorted(weekly_counts.items())],
        'category_distribution': [{'category': r[0], 'count': r[1]} for r in cat_rows],
        'latest_bodyweight': {'weight_kg': latest_bw.weight_kg, 'date': latest_bw.logged_date.isoformat()} if latest_bw else None
    })

@app.route('/api/stats/exercise/<int:eid>', methods=['GET'])
def stats_exercise(eid):
    rows = db.session.query(
        Workout.workout_date,
        func.max(WorkoutSet.weight_kg).label('max_weight'),
        func.sum(WorkoutSet.weight_kg * WorkoutSet.reps).label('volume')
    ).join(WorkoutSet, WorkoutSet.workout_id == Workout.id)\
     .filter(WorkoutSet.exercise_id == eid)\
     .group_by(Workout.workout_date)\
     .order_by(Workout.workout_date).all()
    return jsonify([{'date': str(r[0]), 'max_weight': float(r[1] or 0), 'volume': float(r[2] or 0)} for r in rows])

# ── Init DB ───────────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

def seed_exercises():
    if Exercise.query.count() > 0:
        return
    defaults = [
        # ── Chest ────────────────────────────────────────────────────────
        ('Bench Press',                   'strength',   'Chest'),
        ('Incline Bench Press',           'strength',   'Chest'),
        ('Decline Bench Press',           'strength',   'Chest'),
        ('Close-Grip Bench Press',        'strength',   'Chest'),
        ('Dumbbell Bench Press',          'strength',   'Chest'),
        ('Incline Dumbbell Press',        'strength',   'Chest'),
        ('Dumbbell Fly',                  'strength',   'Chest'),
        ('Incline Dumbbell Fly',          'strength',   'Chest'),
        ('Cable Fly',                     'strength',   'Chest'),
        ('Low-to-High Cable Fly',         'strength',   'Chest'),
        ('High-to-Low Cable Fly',         'strength',   'Chest'),
        ('Chest Dip',                     'bodyweight', 'Chest'),
        ('Push-up',                       'bodyweight', 'Chest'),
        ('Wide Push-up',                  'bodyweight', 'Chest'),
        ('Diamond Push-up',               'bodyweight', 'Chest'),
        ('Decline Push-up',               'bodyweight', 'Chest'),
        ('Incline Push-up',               'bodyweight', 'Chest'),
        ('Pec Deck Machine',              'strength',   'Chest'),
        ('Chest Press Machine',           'strength',   'Chest'),

        # ── Back ─────────────────────────────────────────────────────────
        ('Deadlift',                      'strength',   'Back'),
        ('Romanian Deadlift',             'strength',   'Hamstrings'),
        ('Sumo Deadlift',                 'strength',   'Back'),
        ('Barbell Row',                   'strength',   'Back'),
        ('Pendlay Row',                   'strength',   'Back'),
        ('T-Bar Row',                     'strength',   'Back'),
        ('Dumbbell Row',                  'strength',   'Back'),
        ('Seated Cable Row',              'strength',   'Back'),
        ('Wide-Grip Cable Row',           'strength',   'Back'),
        ('Lat Pulldown',                  'strength',   'Back'),
        ('Close-Grip Lat Pulldown',       'strength',   'Back'),
        ('Single-Arm Lat Pulldown',       'strength',   'Back'),
        ('Pull-up',                       'bodyweight', 'Back'),
        ('Wide-Grip Pull-up',             'bodyweight', 'Back'),
        ('Chin-up',                       'bodyweight', 'Biceps'),
        ('Neutral-Grip Pull-up',          'bodyweight', 'Back'),
        ('Straight-Arm Pulldown',         'strength',   'Back'),
        ('Back Extension',                'strength',   'Lower Back'),
        ('Good Morning',                  'strength',   'Lower Back'),
        ('Rack Pull',                     'strength',   'Back'),
        ('Face Pull',                     'strength',   'Rear Delts'),
        ('Shrug',                         'strength',   'Traps'),
        ('Dumbbell Shrug',                'strength',   'Traps'),

        # ── Shoulders ────────────────────────────────────────────────────
        ('Overhead Press',                'strength',   'Shoulders'),
        ('Seated Dumbbell Press',         'strength',   'Shoulders'),
        ('Arnold Press',                  'strength',   'Shoulders'),
        ('Push Press',                    'strength',   'Shoulders'),
        ('Lateral Raise',                 'strength',   'Shoulders'),
        ('Cable Lateral Raise',           'strength',   'Shoulders'),
        ('Front Raise',                   'strength',   'Shoulders'),
        ('Dumbbell Front Raise',          'strength',   'Shoulders'),
        ('Rear Delt Fly',                 'strength',   'Rear Delts'),
        ('Reverse Pec Deck',              'strength',   'Rear Delts'),
        ('Upright Row',                   'strength',   'Shoulders'),
        ('Pike Push-up',                  'bodyweight', 'Shoulders'),
        ('Handstand Push-up',             'bodyweight', 'Shoulders'),
        ('Shoulder Press Machine',        'strength',   'Shoulders'),

        # ── Biceps ───────────────────────────────────────────────────────
        ('Barbell Curl',                  'strength',   'Biceps'),
        ('EZ-Bar Curl',                   'strength',   'Biceps'),
        ('Wide-Grip Barbell Curl',        'strength',   'Biceps'),
        ('Narrow-Grip Barbell Curl',      'strength',   'Biceps'),
        ('Preacher Curl',                 'strength',   'Biceps'),
        ('EZ-Bar Preacher Curl',          'strength',   'Biceps'),
        ('Concentration Curl',            'strength',   'Biceps'),
        ('Dumbbell Curl',                 'strength',   'Biceps'),
        ('Alternating Dumbbell Curl',     'strength',   'Biceps'),
        ('Hammer Curl',                   'strength',   'Biceps'),
        ('Cross-Body Hammer Curl',        'strength',   'Biceps'),
        ('Incline Dumbbell Curl',         'strength',   'Biceps'),
        ('Cable Curl',                    'strength',   'Biceps'),
        ('High Cable Curl',               'strength',   'Biceps'),
        ('Reverse Curl',                  'strength',   'Biceps'),
        ('Zottman Curl',                  'strength',   'Biceps'),
        ('Spider Curl',                   'strength',   'Biceps'),

        # ── Triceps ──────────────────────────────────────────────────────
        ('Tricep Pushdown',               'strength',   'Triceps'),
        ('Rope Pushdown',                 'strength',   'Triceps'),
        ('Overhead Tricep Extension',     'strength',   'Triceps'),
        ('EZ-Bar Skull Crusher',          'strength',   'Triceps'),
        ('Barbell Skull Crusher',         'strength',   'Triceps'),
        ('Dumbbell Skull Crusher',        'strength',   'Triceps'),
        ('Tricep Close-Grip Press',        'strength',   'Triceps'),
        ('Dip',                           'bodyweight', 'Triceps'),
        ('Bench Dip',                     'bodyweight', 'Triceps'),
        ('Tricep Kickback',               'strength',   'Triceps'),
        ('Single-Arm Cable Extension',    'strength',   'Triceps'),
        ('Overhead Cable Extension',      'strength',   'Triceps'),

        # ── Legs — Quads ─────────────────────────────────────────────────
        ('Squat',                         'strength',   'Legs'),
        ('Front Squat',                   'strength',   'Quads'),
        ('Low Bar Squat',                 'strength',   'Quads'),
        ('Pause Squat',                   'strength',   'Quads'),
        ('Box Squat',                     'strength',   'Quads'),
        ('Hack Squat',                    'strength',   'Quads'),
        ('Leg Press',                     'strength',   'Legs'),
        ('Leg Extension',                 'strength',   'Quads'),
        ('Bulgarian Split Squat',         'strength',   'Quads'),
        ('Walking Lunge',                 'strength',   'Quads'),
        ('Reverse Lunge',                 'strength',   'Quads'),
        ('Forward Lunge',                 'strength',   'Quads'),
        ('Side Lunge',                    'strength',   'Quads'),
        ('Step-up',                       'strength',   'Quads'),
        ('Sissy Squat',                   'bodyweight', 'Quads'),
        ('Wall Sit',                      'bodyweight', 'Quads'),
        ('Pistol Squat',                  'bodyweight', 'Legs'),

        # ── Legs — Hamstrings & Glutes ───────────────────────────────────
        ('Leg Curl',                      'strength',   'Hamstrings'),
        ('Seated Leg Curl',               'strength',   'Hamstrings'),
        ('Nordic Curl',                   'bodyweight', 'Hamstrings'),
        ('Glute Ham Raise',               'bodyweight', 'Hamstrings'),
        ('Hip Thrust',                    'strength',   'Glutes'),
        ('Barbell Hip Thrust',            'strength',   'Glutes'),
        ('Cable Kickback',                'strength',   'Glutes'),
        ('Donkey Kick',                   'bodyweight', 'Glutes'),
        ('Glute Bridge',                  'bodyweight', 'Glutes'),
        ('Single-Leg Glute Bridge',       'bodyweight', 'Glutes'),
        ('Sumo Squat',                    'strength',   'Glutes'),
        ('Abductor Machine',              'strength',   'Glutes'),
        ('Adductor Machine',              'strength',   'Inner Thigh'),

        # ── Legs — Calves ────────────────────────────────────────────────
        ('Standing Calf Raise',           'strength',   'Calves'),
        ('Seated Calf Raise',             'strength',   'Calves'),
        ('Leg Press Calf Raise',          'strength',   'Calves'),
        ('Single-Leg Calf Raise',         'bodyweight', 'Calves'),
        ('Donkey Calf Raise',             'strength',   'Calves'),

        # ── Core — Planks ────────────────────────────────────────────────
        ('Plank',                         'bodyweight', 'Core'),
        ('Side Plank',                    'bodyweight', 'Core'),
        ('Reverse Plank',                 'bodyweight', 'Core'),
        ('Plank with Shoulder Tap',       'bodyweight', 'Core'),
        ('Plank Hip Dip',                 'bodyweight', 'Core'),
        ('Plank Row',                     'bodyweight', 'Core'),
        ('RKC Plank',                     'bodyweight', 'Core'),
        ('Plank to Push-up',              'bodyweight', 'Core'),
        ('Long Lever Plank',              'bodyweight', 'Core'),

        # ── Core — Crunches & Sit-ups ────────────────────────────────────
        ('Crunch',                        'bodyweight', 'Core'),
        ('Bicycle Crunch',                'bodyweight', 'Core'),
        ('Reverse Crunch',                'bodyweight', 'Core'),
        ('Cable Crunch',                  'strength',   'Core'),
        ('Oblique Crunch',                'bodyweight', 'Core'),
        ('Sit-up',                        'bodyweight', 'Core'),
        ('Decline Sit-up',                'bodyweight', 'Core'),
        ('V-up',                          'bodyweight', 'Core'),
        ('Toe Touch Crunch',              'bodyweight', 'Core'),
        ('Cross-Body Crunch',             'bodyweight', 'Core'),

        # ── Core — Other ─────────────────────────────────────────────────
        ('Hanging Leg Raise',             'bodyweight', 'Core'),
        ('Hanging Knee Raise',            'bodyweight', 'Core'),
        ('Toes to Bar',                   'bodyweight', 'Core'),
        ('Dragon Flag',                   'bodyweight', 'Core'),
        ('Ab Wheel Rollout',              'bodyweight', 'Core'),
        ('Russian Twist',                 'bodyweight', 'Core'),
        ('Weighted Russian Twist',        'strength',   'Core'),
        ('Dead Bug',                      'bodyweight', 'Core'),
        ('Bird Dog',                      'bodyweight', 'Core'),
        ('Hollow Body Hold',              'bodyweight', 'Core'),
        ('L-Sit',                         'bodyweight', 'Core'),
        ('Windshield Wiper',              'bodyweight', 'Core'),
        ('Landmine Twist',                'strength',   'Core'),
        ('Pallof Press',                  'strength',   'Core'),
        ('Woodchop',                      'strength',   'Core'),

        # ── Cardio ───────────────────────────────────────────────────────
        ('Running',                       'cardio',     'Cardio'),
        ('Treadmill Walk',                'cardio',     'Cardio'),
        ('Cycling',                       'cardio',     'Cardio'),
        ('Stationary Bike',               'cardio',     'Cardio'),
        ('Rowing Machine',                'cardio',     'Cardio'),
        ('Jump Rope',                     'cardio',     'Cardio'),
        ('Swimming',                      'cardio',     'Cardio'),
        ('Elliptical',                    'cardio',     'Cardio'),
        ('Stair Climber',                 'cardio',     'Cardio'),
        ('Assault Bike',                  'cardio',     'Cardio'),
        ('Sled Push',                     'strength',   'Cardio'),
        ('Sled Pull',                     'strength',   'Cardio'),
        ('Battle Ropes',                  'cardio',     'Cardio'),
        ('Box Jump',                      'cardio',     'Legs'),
        ('Burpee',                        'bodyweight', 'Full Body'),
        ('Mountain Climber',              'bodyweight', 'Core'),
        ('Jumping Jack',                  'cardio',     'Cardio'),
        ('High Knees',                    'cardio',     'Cardio'),
        ('Sprint Interval',               'cardio',     'Cardio'),

        # ── Olympic & Full Body ──────────────────────────────────────────
        ('Power Clean',                   'strength',   'Full Body'),
        ('Hang Clean',                    'strength',   'Full Body'),
        ('Clean and Jerk',                'strength',   'Full Body'),
        ('Snatch',                        'strength',   'Full Body'),
        ('Thruster',                      'strength',   'Full Body'),
        ('Farmers Carry',                 'strength',   'Full Body'),
        ('Kettlebell Swing',              'strength',   'Full Body'),
        ('Kettlebell Turkish Get-up',     'strength',   'Full Body'),
        ('Sandbag Carry',                 'strength',   'Full Body'),
    ]
    for name, cat, mg in defaults:
        db.session.add(Exercise(name=name, category=cat, muscle_group=mg))
    db.session.commit()

with app.app_context():
    db.create_all()
    seed_exercises()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
