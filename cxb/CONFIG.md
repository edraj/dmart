# Dynamic Configuration System

This project uses a dynamic configuration system that loads settings from a JSON file at runtime, allowing you to change configuration without rebuilding the application.

## How It Works

1. Configuration values are stored in `public/config.json`
2. The `src/config.ts` file loads these values dynamically at runtime using the fetch API
3. Changes to `config.json` are reflected immediately on page refresh without requiring a rebuild

## Modifying Configuration

To change configuration values:

1. Edit the `public/config.json` file
2. Save your changes
3. Refresh the application in your browser

No rebuild is required - the configuration is loaded fresh on each session.

## Available Configuration Options

| JSON Key | Description |
|----------|-------------|
| title | Website title |
| footer | Footer text |
| short_name | Short name for the application |
| display_name | Display name for the application |
| description | Website description |
| default_language | Default language code (e.g., "en", "ar") |
| languages | Object mapping language codes to display names |
| backend | Backend API URL |
| websocket | WebSocket URL (optional) |

## Example Configuration

```json
{
  "title": "DMART Unified Data Platform",
  "footer": "dmart.cc unified data platform",
  "short_name": "dmart",
  "display_name": "dmart",
  "description": "dmart unified data platform",
  "default_language": "ar",
  "languages": { "ar": "العربية", "en": "English" },
  "backend": "http://localhost:8282",
  "websocket": "ws://0.0.0.0:8484/ws"
}
```

## Development vs Production

For different environments, you can maintain different versions of the config.json file and deploy the appropriate one:

- For development: Use a local config.json with development settings
- For production: Deploy with a production-ready config.json
- For testing: Use a config.json with test environment settings

Since the configuration is loaded at runtime, you can even change settings on a live production server by updating the config.json file without redeploying the application.
