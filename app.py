from flask import Flask,render_template, request, redirect
import pymysql
import jsonify
app = Flask(__name__)

db_host = "127.0.0.1"
db_user = 'root'
db_password = 'LauNM#17%Domoney!'
db_name = 'reserva_equipamentos'

@app.route ("/teste_banco")
def conectDB():
    try:
        db = pymysql.connect(host=db_host, user=db_user, passwd = db_password, database =db_name)
        db.close()
        return "conexão realizada com sucesso!"
    
    except Exception as e:
        return f"Erro: {e}"
    
    
@app.route('/cadastrarEquipamemto', methods=['POST'])
def cadastrarEquipamemto():
    
    dadosRecebidos = request.get.json()
    
    return render_template("index.html")

@app.route("/login")
def sobre():
    return render_template('login.html')

app.route('/')
def index():
    bdConectado = conectDB()
    cursor = dbConectado.cursor()
    sql = "select * from equipamento"
    cursor.execute(sql)
    resultado = cursor.fetchall()
    print (resultado)
    return render_template("index.html, resulDB = resultado")

if __name__ == "_main_":
    app.run(debug=True)

#http://127.0.0.1:5000