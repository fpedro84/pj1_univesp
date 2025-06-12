from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from zoneinfo import ZoneInfo
import io
from openpyxl import Workbook
import os

# Criação do app e configuração
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///caixa.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# MODELOS


class MovimentoCaixa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    quem = db.Column(db.String(100), nullable=False)
    motivo = db.Column(db.String(200), nullable=False)
    horario = db.Column(db.DateTime, default=datetime.now)


class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco = db.Column(db.Float, nullable=False)

# ROTAS - CAIXA


@app.route('/')
def index():
    movimentos = MovimentoCaixa.query.all()
    produtos = Produto.query.all()

    saldo = sum(m.valor if m.tipo == 'entrada' else -
                m.valor for m in movimentos)
    valor_estoque = sum(p.quantidade * p.preco for p in produtos)
    total_movimentos = len(movimentos)

    # Gráfico: agrupar por data
    from collections import defaultdict
    resumo_data = defaultdict(lambda: {'entrada': 0, 'saida': 0})
    for m in movimentos:
        data_str = m.horario.strftime('%d/%m')
        if m.tipo == 'entrada':
            resumo_data[data_str]['entrada'] += m.valor
        else:
            resumo_data[data_str]['saida'] += m.valor

    datas = list(resumo_data.keys())
    entradas = [resumo_data[d]['entrada'] for d in datas]
    saidas = [resumo_data[d]['saida'] for d in datas]

    return render_template('index.html', saldo=saldo, valor_estoque=valor_estoque,
                           total_movimentos=total_movimentos, datas=datas,
                           entradas=entradas, saidas=saidas)


@app.route('/novo', methods=['GET', 'POST'])
def novo_movimento():
    if request.method == 'POST':
        tipo = request.form['tipo']
        valor = float(request.form['valor'])
        quem = request.form['quem']
        motivo = request.form['motivo']
        movimento = MovimentoCaixa(
            tipo=tipo, valor=valor, quem=quem, motivo=motivo)
        db.session.add(movimento)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('novo.html')


@app.route('/excluir/<int:id>', methods=['GET'])
def excluir_movimento(id):
    movimento = MovimentoCaixa.query.get_or_404(id)
    db.session.delete(movimento)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/exportar')
def exportar_excel():
    movimentos = MovimentoCaixa.query.order_by(MovimentoCaixa.horario).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Movimentações de Caixa"
    ws.append(["Tipo", "Valor", "Serviço", "Motivo", "Horário"])
    for m in movimentos:
        horario_brasil = m.horario.replace(tzinfo=ZoneInfo(
            "UTC")).astimezone(ZoneInfo("America/Sao_Paulo"))
        ws.append([
            m.tipo,
            m.valor,
            m.quem,
            m.motivo,
            horario_brasil.strftime("%d/%m/%Y %H:%M")
        ])
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return send_file(
        file_stream,
        as_attachment=True,
        download_name="movimentacoes_caixa.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ROTAS - ESTOQUE


@app.route('/estoque')
def listar_estoque():
    produtos = Produto.query.all()
    return render_template('estoque.html', produtos=produtos)


@app.route('/estoque/novo', methods=['GET', 'POST'])
def novo_produto():
    if request.method == 'POST':
        nome = request.form['nome']
        quantidade = int(request.form['quantidade'])
        preco = float(request.form['preco'])
        produto = Produto(nome=nome, quantidade=quantidade, preco=preco)
        db.session.add(produto)
        db.session.commit()
        return redirect(url_for('listar_estoque'))
    return render_template('novo_produto.html')


@app.route('/estoque/excluir/<int:id>')
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    return redirect(url_for('listar_estoque'))


@app.route('/resumo')
def resumo():
    movimentos = MovimentoCaixa.query.order_by(
        MovimentoCaixa.horario.desc()).all()
    for m in movimentos:
        m.horario = m.horario.replace(tzinfo=ZoneInfo(
            "UTC")).astimezone(ZoneInfo("America/Sao_Paulo"))
    saldo = sum(m.valor if m.tipo == 'entrada' else -
                m.valor for m in movimentos)
    return render_template('resumo.html', movimentos=movimentos, saldo=saldo)

# INICIALIZAÇÃO


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
