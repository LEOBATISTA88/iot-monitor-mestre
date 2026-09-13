import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuração do banco de dados (Ajusta a URL fornecida pelo Render)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelo para registrar as máquinas (Agentes)
class Agent(db.Model):
    id = db.Column(db.String(100), primary_key=True)  # Endereço MAC
    hostname = db.Column(db.String(100), nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    telemetries = db.relationship('Telemetry', backref='agent', lazy=True, cascade="all, delete-orphan")

# Modelo para armazenar o histórico de dados recolhidos
class Telemetry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(100), db.ForeignKey('agent.id'), nullable=False)
    cpu_percent = db.Column(db.Float, nullable=False)
    ram_percent = db.Column(db.Float, nullable=False)
    disk_percent = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# Endpoint para receber dados enviados pelos Agentes Windows
@app.route('/api/v1/telemetry', methods=['POST'])
def receive_telemetry():
    data = request.json
    if not data or 'agent_id' not in data:
        return jsonify({"error": "Payload inválido"}), 400

    agent_id = data['agent_id']
    hostname = data.get('hostname', 'Desconhecido')

    # Atualiza ou insere a máquina na base centralizada
    agent = Agent.query.get(agent_id)
    if not agent:
        agent = Agent(id=agent_id, hostname=hostname)
        db.session.add(agent)
    else:
        agent.hostname = hostname
        agent.last_seen = datetime.utcnow()

    # Salva os dados de consumo de hardware
    telemetry = Telemetry(
        agent_id=agent_id,
        cpu_percent=float(data.get('cpu_percent', 0.0)),
        ram_percent=float(data.get('ram_percent', 0.0)),
        disk_percent=float(data.get('disk_percent', 0.0))
    )
    db.session.add(telemetry)
    db.session.commit()

    return jsonify({"status": "sucesso"}), 201

# Dashboard principal para visualização dos ativos da rede
@app.route('/')
def dashboard():
    agents = Agent.query.all()
    # Pega a última leitura de cada agente
    latest_data = []
    for agent in agents:
        last_telemetry = Telemetry.query.filter_by(agent_id=agent.id).order_by(Telemetry.timestamp.desc()).first()
        latest_data.append({
            'agent': agent,
            'telemetry': last_telemetry
        })
    return render_template('Dashboard.html', agents_data=latest_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
