from flask import Flask, render_template, request, redirect, session, url_for, flash
import pandas as pd
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = "clave_secreta"

USUARIOS_FILE = "data/usuarios.xlsx"
VACACIONES_FILE = "data/vacaciones.xlsx"
POLITICA_FILE = "data/politica_vacaciones.xlsx"

# =========================
# FUNCIÓN CÁLCULO VACACIONES
# =========================
def calcular_dias_vacaciones(fecha_ingreso):
    hoy = date.today()
    anios_laborados = (hoy - fecha_ingreso).days // 365

    politica = pd.read_excel(POLITICA_FILE)

    fila = politica[
        (politica["anios_min"] <= anios_laborados) &
        (politica["anios_max"] > anios_laborados)
    ]

    if fila.empty:
        return 0, anios_laborados

    dias = int(fila.iloc[0]["dias_vacaciones"])
    return dias, anios_laborados


# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form["correo"].strip()
        password = request.form["password"].strip()

        df = pd.read_excel(USUARIOS_FILE)
        df["correo"] = df["correo"].astype(str).str.strip()
        df["password"] = df["password"].astype(str).str.strip()
        df["rol"] = df["rol"].astype(str).str.strip().str.lower()

        user = df.loc[(df["correo"] == correo) & (df["password"] == password)]

        if len(user) == 1:
            session["user_id"] = int(user.iloc[0]["id"])
            session["rol"] = user.iloc[0]["rol"]

            flash("Bienvenido al sistema", "success")

            return redirect(url_for(session["rol"]))

        flash("Credenciales incorrectas", "danger")
        return redirect("/")

    return render_template("login.html")


# =========================
# TRABAJADOR
# =========================
@app.route("/trabajador", methods=["GET", "POST"])
def trabajador():
    if session.get("rol") != "trabajador":
        return redirect("/")

    user_id = session["user_id"]
    df_users = pd.read_excel(USUARIOS_FILE).fillna("")
    user = df_users[df_users["id"] == user_id].iloc[0]

    fecha_ingreso = pd.to_datetime(user["fecha_ingreso"]).date()
    dias_totales, _ = calcular_dias_vacaciones(fecha_ingreso)

    df_vac = pd.read_excel(VACACIONES_FILE)

    usados = df_vac[
        (df_vac["id_usuario"] == user_id) &
        (df_vac["estado"] == "Aprobado")
    ]["dias"].sum()

    disponibles = dias_totales - usados

    if request.method == "POST":
        inicio = datetime.strptime(request.form["fecha_inicio"], "%Y-%m-%d").date()
        fin = datetime.strptime(request.form["fecha_fin"], "%Y-%m-%d").date()
        dias = (fin - inicio).days + 1

        if dias <= disponibles:
            df_vac.loc[len(df_vac)] = [
                len(df_vac) + 1, user_id, inicio, fin, dias, "Pendiente", ""
            ]
            df_vac.to_excel(VACACIONES_FILE, index=False)
            flash("Solicitud enviada", "success")
        else:
            flash("No tienes días suficientes", "danger")

        return redirect("/trabajador")

    return render_template(
        "trabajador.html",
        dias_totales=dias_totales,
        dias_usados=usados,
        dias_disponibles=disponibles
    )


# =========================
# RESPONSABLE
# =========================
@app.route("/responsable")
def responsable():
    if session.get("rol") != "responsable":
        return redirect("/")

    df_users = pd.read_excel(USUARIOS_FILE)
    df_vac = pd.read_excel(VACACIONES_FILE)

    responsable = df_users[df_users["id"] == session["user_id"]].iloc[0]
    area = responsable["area"]

    solicitudes = []

    for _, v in df_vac[df_vac["estado"] == "Pendiente"].iterrows():
        emp = df_users[df_users["id"] == v["id_usuario"]].iloc[0]
        if emp["area"] == area:
            solicitudes.append({
                "id": v["id"],
                "nombre": emp["nombre"],
                "area": emp["area"],
                "fecha_inicio": v["fecha_inicio"],
                "fecha_fin": v["fecha_fin"],
                "dias": v["dias"]
            })

    return render_template("responsable.html", solicitudes=solicitudes)


@app.route("/aprobar/<int:id_solicitud>")
def aprobar(id_solicitud):
    df = pd.read_excel(VACACIONES_FILE)
    df.loc[df["id"] == id_solicitud, "estado"] = "Aprobado"
    df.to_excel(VACACIONES_FILE, index=False)
    return redirect("/responsable")


@app.route("/rechazar/<int:id_solicitud>")
def rechazar(id_solicitud):
    df = pd.read_excel(VACACIONES_FILE)
    df.loc[df["id"] == id_solicitud, "estado"] = "Rechazado"
    df.to_excel(VACACIONES_FILE, index=False)
    return redirect("/responsable")


# =========================
# ADMIN
# =========================
@app.route("/admin")
def admin():
    if session.get("rol") != "admin":
        return redirect("/")

    df_users = pd.read_excel(USUARIOS_FILE)
    df_vac = pd.read_excel(VACACIONES_FILE)

    df_users["rol"] = df_users["rol"].astype(str).str.lower()

    total_usuarios = len(df_users)
    total_trabajadores = len(df_users[df_users["rol"] == "trabajador"])
    total_responsables = len(df_users[df_users["rol"] == "responsable"])
    total_admins = len(df_users[df_users["rol"] == "admin"])

    usuarios = []

    for _, u in df_users.iterrows():
        fecha = pd.to_datetime(u["fecha_ingreso"]).date()
        dias_totales, anios = calcular_dias_vacaciones(fecha)

        usados = df_vac[
            (df_vac["id_usuario"] == u["id"]) &
            (df_vac["estado"] == "Aprobado")
        ]["dias"].sum()

        pendientes = df_vac[
            (df_vac["id_usuario"] == u["id"]) &
            (df_vac["estado"] == "Pendiente")
        ]["dias"].sum()

        usuarios.append({
            "id": u["id"],
            "nombre": u["nombre"],
            "rol": u["rol"],
            "area": u["area"],
            "fecha_ingreso": fecha,
            "anios_laborados": anios,
            "dias_totales": dias_totales,
            "dias_usados": usados,
            "dias_pendientes": pendientes,
            "correo_notificaciones": u["correo_notificaciones"],
            "id_responsable": u["id_responsable"],
            "activo": u["activo"]
        })

    return render_template(
        "admin.html",
        usuarios=usuarios,
        total_usuarios=total_usuarios,
        total_trabajadores=total_trabajadores,
        total_responsables=total_responsables,
        total_admins=total_admins
    )


# =========================
# CRUD USUARIOS
# =========================
@app.route("/admin/nuevo", methods=["GET", "POST"])
def nuevo_usuario():
    if request.method == "POST":
        df = pd.read_excel(USUARIOS_FILE)

        nuevo = request.form.to_dict()
        nuevo["id"] = df["id"].max() + 1

        df = pd.concat([df, pd.DataFrame([nuevo])])
        df.to_excel(USUARIOS_FILE, index=False)

        return redirect("/admin")

    return render_template("usuario_form.html", usuario=None)


@app.route("/admin/editar/<int:user_id>", methods=["GET", "POST"])
def editar_usuario(user_id):
    df = pd.read_excel(USUARIOS_FILE)

    if request.method == "POST":
        for k, v in request.form.items():
            df.loc[df["id"] == user_id, k] = v
        df.to_excel(USUARIOS_FILE, index=False)
        return redirect("/admin")

    usuario = df[df["id"] == user_id].iloc[0].to_dict()
    return render_template("usuario_form.html", usuario=usuario)


@app.route("/admin/eliminar/<int:user_id>")
def eliminar_usuario(user_id):
    df = pd.read_excel(USUARIOS_FILE)
    df = df[df["id"] != user_id]
    df.to_excel(USUARIOS_FILE, index=False)
    return redirect("/admin")


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run()
