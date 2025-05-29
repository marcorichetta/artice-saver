# Article Saver

JS function to save articles from a URL to a database in Firebase.

## Usage

### Read RSS

https://artice-saver.vercel.app/api/rss.xml

### Save Article

Save articles by sending a POST request to the API endpoint with the article details in JSON format.

```shell
curl -X POST \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer key" \
     -d '{"url": "https://www.website.com", "title": "La Noticia del Día", "content": "Un resumen breve de la noticia más importante."}' \
     https://artice-saver.vercel.app/api/add-article

# Example Response
{
    "message":"Artículo añadido con éxito.",
    "article":{
        "url":"https://www.website.com",
        "title":"La Noticia del Día",
        "content":"Un resumen breve de la noticia más importante.",
        "createdAt":{}
    }
}
```
