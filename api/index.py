import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from feedgen.feed import FeedGenerator
from firebase_admin import credentials, firestore, initialize_app
from flask import Flask, Response, jsonify, request

load_dotenv(dotenv_path="../.env", verbose=True)
env: str = os.environ.get("ENVIRONMENT", "dev").lower()
app = Flask(__name__)


try:
    if env == "dev":
        # En desarrollo, puedes usar un archivo JSON local para las credenciales.
        cred_path = "../firebase_creds.json"
        if not os.path.exists(cred_path):
            raise FileNotFoundError(
                "El archivo de credenciales de Firebase no se encontró en el directorio de desarrollo."
            )
        credentials = credentials.Certificate(cred_path)
    else:
        cred_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")
        credentials = credentials.Certificate(cred_json)

except Exception as e:
    print(f"Error initializing Firestore client for RSS feed: {e}")
    raise RuntimeError("Failed to initialize Firestore client for RSS feed.") from e

initialize_app(credentials)
db = firestore.client()
print("Firestore client initialized successfully for RSS feed.")


@app.route("/")
def home():
    return "Hello, World!"


@app.route("/api/add_article", methods=["POST", "OPTIONS"])
def add_article_handler():
    # --- Configuración de CORS ---
    # Permite peticiones desde cualquier origen. Ajusta en producción si es necesario.
    res = jsonify({"message": "OK"})  # Default response for options
    res.headers["Access-Control-Allow-Origin"] = "*"
    res.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    res.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

    if request.method == "OPTIONS":
        return res  # Responde a las peticiones OPTIONS (preflight CORS)

    # --- Verificación de Clave API (¡MUY IMPORTANTE para seguridad!) ---
    # La clave API se debe configurar como una variable de entorno en Vercel.
    API_KEY = os.environ.get("ADD_ARTICLE_API_KEY")
    auth_header = request.headers.get("Authorization")

    if not API_KEY or not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    provided_key = auth_header.split(" ")[1]
    if provided_key != API_KEY:
        return jsonify({"error": "Invalid API Key"}), 401

    # --- Procesamiento de la Petición ---
    if not db:
        return jsonify({"error": "Database not initialized. Check server logs."}), 500

    try:
        data = request.get_json()
    except Exception as e:
        return jsonify({"error": f"Invalid JSON in request body: {e}"}), 400

    url = data.get("url")
    title = data.get("title")
    content = data.get("content")

    if not url:
        return jsonify({"error": "URL es requerida."}), 400

    try:
        new_article = {
            "url": url,
            "title": title if title else "Sin Título",
            "content": content if content else "",
            "createdAt": firestore.firestore.SERVER_TIMESTAMP,  # Firestore gestiona el timestamp
        }
        # Guarda en la colección 'articles'
        doc_ref = db.collection("articles").add(new_article)

        # Retorna el artículo guardado (sin el createdAt real hasta que se complete)
        # Para una respuesta más precisa, podrías hacer un get() después de add()
        response_article = {
            "id": doc_ref[1].id,  # doc_ref[1] es la referencia del documento
            "url": url,
            "title": title if title else "Sin Título",
            "content": content if content else "",
            "createdAt": datetime.now(timezone.utc).isoformat()
            + "Z",  # Timestamp aproximado para la respuesta
        }

        return jsonify(
            {"message": "Artículo añadido con éxito.", "article": response_article}
        ), 200

    except Exception as e:
        print(f"Error al añadir artículo: {e}")
        return jsonify({"error": f"Fallo al añadir artículo: {e}"}), 500


@app.route("/api/rss_feed", methods=["GET", "OPTIONS"])
def rss_feed_handler():
    # --- Configuración de CORS ---
    # Esto permite que tu API sea accedida desde cualquier origen.
    # En producción, considera restringir 'Access-Control-Allow-Origin' a dominios específicos.
    res = Response()  # Una respuesta básica para el método OPTIONS
    res.headers["Access-Control-Allow-Origin"] = "*"
    res.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    res.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

    if request.method == "OPTIONS":
        return res  # Responde a las peticiones OPTIONS (preflight CORS)

    # --- Generación del Feed RSS ---
    if not db:
        return Response(
            "<error>Database not initialized. Check server logs.</error>",
            mimetype="application/xml",
            status=500,
        )

    try:
        # Crea una nueva instancia de FeedGenerator
        fg = FeedGenerator()
        fg.title("Mi Feed de Artículos Personal (Python)")
        fg.link(
            href=request.url_root.replace("http://", "https://") + "api/rss_feed",
            rel="self",
        )  # Asegura HTTPS
        fg.description(
            "Artículos y enlaces guardados personalmente con Python y Firebase."
        )
        fg.language("es-es")

        # Opcional: Puedes establecer un autor o un logo si quieres
        # fg.author({'name': 'Tu Nombre', 'email': 'tu.email@ejemplo.com'})
        # fg.logo('http://example.com/logo.png')

        # Obtiene los artículos de Firestore
        articles_ref = db.collection("articles")
        snapshot = (
            articles_ref.order_by(
                "createdAt", direction=firestore.firestore.Query.DESCENDING
            )
            .limit(50)
            .stream()
        )

        # Añade cada artículo como una entrada al feed
        for doc in snapshot:
            article = doc.to_dict()
            fe = fg.add_entry()  # Crea una nueva entrada de feed

            fe.title(article.get("title", "Sin Título"))
            fe.link(href=article.get("url", "#"), rel="alternate")  # link del artículo
            fe.guid(
                article.get("url") or doc.id, permalink=True
            )  # GUID para identificar el artículo

            # Convierte el timestamp de Firestore a un objeto datetime si existe
            if article.get("createdAt"):
                if isinstance(article["createdAt"], datetime):
                    fe.pubDate(article["createdAt"].astimezone(timezone.utc))
                elif hasattr(
                    article["createdAt"], "toDate"
                ):  # Para objetos Timestamp de Firestore
                    fe.pubDate(article["createdAt"].toDate().astimezone(timezone.utc))
            else:
                fe.pubDate(
                    datetime.now(timezone.utc)
                )  # Fecha actual si no hay createdAt

            # Contenido HTML para la descripción
            fe.content(article.get("content", ""), type="html")

        # Genera el XML del feed RSS
        rss_feed_xml = fg.rss_str(pretty=True)  # pretty=True para un XML legible

        # Envía la respuesta con el Content-Type correcto
        return Response(
            rss_feed_xml, mimetype="application/rss+xml; charset=utf-8", status=200
        )

    except Exception as e:
        print(f"Error al generar el feed RSS: {e}")
        # En caso de error, devuelve un XML de error para que los clientes RSS puedan manejarlo
        error_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>Error en Mi Feed de Artículos Personal</title>
    <link>#</link>
    <description>Fallo al generar el feed RSS: {str(e)}</description>
</channel>
</rss>"""
        return Response(error_xml, mimetype="application/xml", status=500)
