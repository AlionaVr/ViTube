// Not inline in index.html: the CSP allows scripts from this site only. Same options as FastAPI's own page.
window.ui = SwaggerUIBundle({
  url: '/api/openapi.json',
  dom_id: '#swagger-ui',
  layout: 'BaseLayout',
  presets: [SwaggerUIBundle.presets.apis],
  deepLinking: true,
  showExtensions: true,
  showCommonExtensions: true,
})
