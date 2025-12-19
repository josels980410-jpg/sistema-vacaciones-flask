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

        user = df.loc[
            (df["correo"] == correo) &
            (df["password"] == password)
        ]

        if len(user) == 1:
            session["user_id"] = int(user.iloc[0]["id"])
            session["rol"] = user.iloc[0]["rol"]

            flash("Bienvenido al sistema", "success")

            if session["rol"] == "admin":
                return redirect(url_for("admin"))
            elif session["rol"] == "responsable":
                return redirect(url_for("responsable"))
            elif session["rol"] == "trabajador":
                return redirect(url_for("trabajador"))

            flash("Rol no reconocido", "warning")
            return redirect("/")

        flash("Credenciales incorrectas", "danger")
        return redirect("/")

    return render_template("login.html")


# =========================
# TRABAJADOR
# =========================
@app.route("/trabajador", methods=["GET", "POST"])
def trabajador():
    if "rol" not in session or session["rol"] != "trabajador":
        flash("Acceso no autorizado", "danger")
        return redirect("/")

    user_id = session["user_id"]

    df_users = pd.read_excel(USUARIOS_FILE)
    df_users = df_users.fillna("")
    user = df_users[df_users["id"] == user_id].iloc[0]

    fecha_ingreso = pd.to_datetime(user["fecha_ingreso"]).date()
    dias_totales, _ = calcular_dias_vacaciones(fecha_ingreso)

    df_vac = pd.read_excel(VACACIONES_FILE)

    df_aprobadas = df_vac[
        (df_vac["id_usuario"] == user_id) &
        (df_vac["estado"] == "Aprobado")
    ]

    dias_usados = df_aprobadas["dias"].sum() if not df_aprobadas.empty else 0
    dias_disponibles = dias_totales - dias_usados

    if request.method == "POST":
        inicio = datetime.strptime(request.form["fecha_inicio"], "%Y-%m-%d").date()
        fin = datetime.strptime(request.form["fecha_fin"], "%Y-%m-%d").date()

        dias_solicitados = (fin - inicio).days + 1

        if dias_solicitados <= 0:
            flash("Fechas inválidas", "warning")
            return redirect("/trabajador")

        if dias_solicitados <= dias_disponibles:
            nuevo = {
                "id": len(df_vac) + 1,
                "id_usuario": user_id,
                "fecha_inicio": inicio,
                "fecha_fin": fin,
                "dias": dias_solicitados,
                "estado": "Pendiente",
                "aprobado_por": ""
            }

            df_vac = pd.concat([df_vac, pd.DataFrame([nuevo])], ignore_index=True)
            df_vac.to_excel(VACACIONES_FILE, index=False)

            flash("Solicitud enviada correctamente", "info")
            return redirect("/trabajador")

        flash("No tienes días suficientes disponibles", "danger")
        return redirect("/trabajador")

    return render_template(
        "trabajador.html",
        dias_totales=dias_totales,
        dias_usados=dias_usados,
        dias_disponibles=dias_disponibles
    )


# =========================
# RESPONSABLE
# =========================
@app.route("/responsable")
def responsable():
    if "rol" not in session or session["rol"] != "responsable":
        flash("Acceso no autorizado", "danger")
        return redirect("/")

    user_id = session["user_id"]

    df_users = pd.read_excel(USUARIOS_FILE)
    responsable = df_users[df_users["id"] == user_id].iloc[0]
    area_resp = responsable["area"]

    df_vac = pd.read_excel(VACACIONES_FILE)
    df_vac = df_vac[df_vac["estado"] == "Pendiente"]

    solicitudes = []

    for _, row in df_vac.iterrows():
        empleado = df_users[df_users["id"] == row["id_usuario"]].iloc[0]

        if empleado["area"] == area_resp:
            solicitudes.append({
                "id": row["id"],
                "nombre": empleado["nombre"],
                "area": empleado["area"],
                "fecha_inicio": row["fecha_inicio"],
                "fecha_fin": row["fecha_fin"],
                "dias": row["dias"]
            })

    return render_template("responsable.html", solicitudes=solicitudes)


# =========================
# APROBAR / RECHAZAR
# =========================
@app.route("/aprobar/<int:id_solicitud>")
def aprobar(id_solicitud):
    if "rol" not in session or session["rol"] != "responsable":
        flash("Acceso no autorizado", "danger")
        return redirect("/")

    df = pd.read_excel(VACACIONES_FILE)

    df.loc[df["id"] == id_solicitud, "estado"] = "Aprobado"
    df.loc[df["id"] == id_solicitud, "aprobado_por"] = session["user_id"]

    df.to_excel(VACACIONES_FILE, index=False)

    flash("Solicitud aprobada correctamente", "success")
    return redirect("/responsable")


@app.route("/rechazar/<int:id_solicitud>")
def rechazar(id_solicitud):
    if "rol" not in session or session["rol"] != "responsable":
        flash("Acceso no autorizado", "danger")
        return redirect("/")

    df = pd.read_excel(VACACIONES_FILE)

    df.loc[df["id"] == id_solicitud, "estado"] = "Rechazado"
    df.loc[df["id"] == id_solicitud, "aprobado_por"] = session["user_id"]

    df.to_excel(VACACIONES_FILE, index=False)

    flash("Solicitud rechazada", "warning")
    return redirect("/responsable")


# =========================
# ADMIN
# =========================
@app.route("/admin")
def admin():
    if "rol" not in session or session["rol"] != "admin":
        return redirect("/")

    # Leer archivos
    df_users = pd.read_excel(USUARIOS_FILE)
    df_vac = pd.read_excel(VACACIONES_FILE)

    # Normalizar rol (IMPORTANTE para las tarjetas)
    df_users["rol"] = df_users["rol"].astype(str).str.strip().str.lower()

    # =========================
    # TARJETAS RESUMEN
    # =========================
    total_usuarios = len(df_users)
    total_trabajadores = len(df_users[df_users["rol"] == "trabajador"])
    total_responsables = len(df_users[df_users["rol"] == "responsable"])
    total_admins = len(df_users[df_users["rol"] == "admin"])

    # =========================
    # TABLA DE USUARIOS
    # =========================
    usuarios = []

    for _, u in df_users.iterrows():
        fecha_ingreso = pd.to_datetime(u["fecha_ingreso"]).date()

        # Calcula años laborados y días según política
        dias_totales, anios = calcular_dias_vacaciones(fecha_ingreso)

        # Vacaciones aprobadas
        usados = df_vac[
            (df_vac["id_usuario"] == u["id"]) &
            (df_vac["estado"] == "Aprobado")
        ]["dias"].sum()

        # Vacaciones pendientes
        pendientes = df_vac[
            (df_vac["id_usuario"] == u["id"]) &
            (df_vac["estado"] == "Pendiente")
        ]["dias"].sum()

        usuarios.append({
            "id": u["id"],
            "nombre": u["nombre"],
            "correo": u["correo"],
            "rol": u["rol"],
            "area": u["area"],
            "fecha_ingreso": fecha_ingreso,
            "anios_laborados": anios,
            "dias_totales": dias_totales,
            "dias_usados": usados,
            "dias_pendientes": pendientes,
            "dias_disponibles": dias_totales - usados,
            "correo_notificaciones": u["correo_notificaciones"],
            "activo": u["activo"],
            "id_responsable": u["id_responsable"],
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
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente", "info")
    return redirect("/")


if __name__ == "__main__":
    app.run()
