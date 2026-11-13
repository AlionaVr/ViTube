// The theme picked in Appearance (src/theme/theme.ts), set before the first paint: no white flash.
// A file, not an inline script: the CSP allows scripts from this site only (nginx/default.conf.template).
try {
  const theme = localStorage.getItem('vitube:theme')
  if (theme === 'dark' || theme === 'light') document.documentElement.dataset.theme = theme
} catch {}
