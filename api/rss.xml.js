// api/rss.xml.js
const admin = require("firebase-admin");

// Initialize Firebase Admin SDK if it's not already initialized.
// This uses environment variables for secure credential handling,
// which is crucial for deployment on platforms like Vercel or Netlify.
if (!admin.apps.length) {
	try {
		// Parse the service account key from the environment variable.
		// It's expected to be a stringified JSON object.
		const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_KEY);
		admin.initializeApp({
			credential: admin.credential.cert(serviceAccount),
		});
	} catch (error) {
		console.error("Error initializing Firebase Admin SDK:", error);
		console.error(
			"Please ensure the FIREBASE_SERVICE_ACCOUNT_KEY environment variable is configured correctly."
		);
	}
}

// Get a reference to the Firestore database.
const db = admin.firestore();

/**
 * Escapes characters that are reserved in XML to ensure valid output.
 * This is essential for preventing issues with special characters in titles, links, and GUIDs.
 * @param {string} text - The text string to escape.
 * @returns {string} The XML-escaped string.
 */
function escapeXml(text) {
	if (typeof text !== "string") return ""; // Ensure input is a string
	return text
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&apos;");
}

/**
 * Main handler for the RSS feed API endpoint.
 * This function queries Firestore for articles, generates an RSS 2.0 XML feed,
 * and sends it as the response.
 * @param {object} req - The HTTP request object.
 * @param {object} res - The HTTP response object.
 */
module.exports = async (req, res) => {
	// Set the Content-Type header to indicate an RSS XML feed.
	res.setHeader("Content-Type", "application/rss+xml; charset=utf-8");
	// Set cache control headers for better performance and reduced database load.
	// Caches for 60 seconds and allows stale content while revalidating.
	res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate");

	try {
		const articlesRef = db.collection("articles");
		// Fetch articles, ordering them by creation date (newest first)
		// and limiting the number of items in the feed to 50.
		const snapshot = await articlesRef.orderBy("createdAt", "desc").limit(50).get();

		let rssItems = "";
		// Iterate over each article document fetched from Firestore.
		snapshot.forEach((doc) => {
			const article = doc.data();
			// Format the publication date to UTC string as required by RSS.
			// Fallback to current date if createdAt is not available.
			const pubDate = article.createdAt
				? new Date(article.createdAt.toDate()).toUTCString()
				: new Date().toUTCString();
			// Use the article's URL as the GUID for uniqueness, or the Firestore document ID if no URL.
			const guid = article.url || doc.id;
			// Wrap content in CDATA to safely include HTML or special characters without breaking XML structure.
			const contentCdata = article.content ? `<![CDATA[${article.content}]]>` : "";

			// Append each article as an <item> element to the RSS feed string.
			rssItems += `
        <item>
            <title>${escapeXml(article.title)}</title>
            <link>${escapeXml(article.url)}</link>
            <guid isPermaLink="true">${escapeXml(guid)}</guid>
            <pubDate>${pubDate}</pubDate>
            <description>${contentCdata}</description>
        </item>`;
		});

		// Construct the full base URL for the feed.
		// req.headers.host will give you the domain (e.g., 'your-vercel-domain.vercel.app').
		const baseUrl = `https://${req.headers.host}`;

		// Assemble the complete RSS 2.0 XML feed.
		const rssFeed = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>Mi Feed de Artículos Personal</title>
    <link>${baseUrl}/api/rss.xml</link> <description>Artículos y enlaces guardados personalmente.</description>
    <language>es-es</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${baseUrl}/api/rss.xml" rel="self" type="application/rss+xml" />
    ${rssItems}
</channel>
</rss>`;

		// Send the generated RSS XML as the response with a 200 OK status.
		res.status(200).send(rssFeed);
	} catch (error) {
		// Log any errors and send a generic error response.
		console.error("Error generating RSS feed:", error);
		res.status(500).send("<error>Failed to generate RSS feed</error>");
	}
};
