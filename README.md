# WebRegistroExyt

**WebRegistroExyt** es una aplicación web para la recolección, almacenamiento y visualización de datos de registro de usuarios. Está diseñada para enviar automáticamente los registros a Google BigQuery y visualizarlos en dashboards personalizados con Looker Studio.

---

## 🧩 Tecnologías utilizadas

- **Python 3.12+**
- **Google BigQuery** (como base de datos)
- **Looker Studio** (para dashboards)
- **Docker** (opcional, para despliegue)
- **Git + GitHub** (control de versiones)

---

## 🚀 Características principales

- Formulario web de registro de personas
- Datos enviados automáticamente a Google BigQuery
- Visualización de estadísticas en Looker Studio:
  - Registros por año de nacimiento
  - Distribución por proveedor de correo electrónico
  - Filtros dinámicos para explorar registros
 
---

## 📁 Estructura del proyecto

    WebRegistroExyt/
    │
    ├── main.py # Archivo principal de la aplicación
    ├── requirements.txt # Dependencias del proyecto
    ├── Dockerfile # (Opcional) Para despliegue en contenedores
    ├── .gitignore
    ├── exyt-control/ # Subdirectorio adicional del proyecto que contiene el frontend
    └── ...

---

## ⚙️ Instalación local

```bash
# Clona el repositorio
git clone https://github.com/emiliojg10/WebRegistro.git
cd WebRegistro

# (Opcional) Crea un entorno virtual
python -m venv env
env\Scripts\activate  # En Windows

# Instala las dependencias
pip install -r requirements.txt

# Ejecuta la aplicación
python main.py

---

## 📊 Dashboard Looker Studio
Puedes acceder al dashboard creado en Looker Studio con estadísticas en tiempo real

---

## ✍️ Autor
Desarrollado por Emilio Jiménez
