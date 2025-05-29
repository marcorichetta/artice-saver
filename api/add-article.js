// api/add-article.js
const admin = require("firebase-admin");

// Inicializa Firebase Admin SDK si no está inicializado
// Usa variables de entorno para las credenciales de forma segura
if (!admin.apps.length) {
	try {
		const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_KEY);
		admin.initializeApp({
			credential: admin.credential.cert(serviceAccount),
		});
	} catch (error) {
		console.error("Error inicializando Firebase Admin SDK:", error);
		// En Vercel/Netlify, serviceAccount debería ser el JSON directamente de una ENV var.
		// Si estás en un entorno como Google Cloud Functions, se puede usar applicationDefault().
		console.error(
			"Asegúrate de que FIREBASE_SERVICE_ACCOUNT_KEY está configurada correctamente."
		);
	}
}

const db = admin.firestore();

module.exports = async (req, res) => {
	// CORS para permitir peticiones desde cualquier origen (ajusta para producción si es necesario)
	res.setHeader("Access-Control-Allow-Origin", "*");
	res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
	res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

	// Responde a las peticiones OPTIONS (preflight CORS)
	if (req.method === "OPTIONS") {
		return res.status(204).end();
	}

	// 1. Verificación de Método HTTP
	if (req.method !== "POST") {
		return res.status(405).send("Method Not Allowed");
	}

	// 2. Verificación de Clave API (¡MUY IMPORTANTE para seguridad!)
	const API_KEY = process.env.ADD_ARTICLE_API_KEY; // Obtén la clave desde tus variables de entorno de Vercel/Netlify
	if (!API_KEY || req.headers.authorization !== `Bearer ${API_KEY}`) {
		return res.status(401).send("Unauthorized");
	}

	// 3. Procesamiento de la Petición
	const { url, title, content } = req.body;

	if (!url) {
		return res.status(400).json({ error: "URL es requerida." });
	}

	try {
		const newArticle = {
			url: url,
			title: title || "Sin Título",
			content: content || "",
			createdAt: admin.firestore.FieldValue.serverTimestamp(), // Timestamp del servidor de Firestore
		};
		await db.collection("articles").add(newArticle); // Guarda en la colección 'articles'
		res.status(200).json({ message: "Artículo añadido con éxito.", article: newArticle });
	} catch (error) {
		console.error("Error al añadir artículo:", error);
		res.status(500).json({ error: "Fallo al añadir artículo." });
	}
};
