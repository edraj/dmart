interface WebsiteConfig {
  title: string;
  footer: string;
  short_name: string;
  display_name: string;
  description: string;
  default_language: string;
  languages: Record<string, string>;
  backend: string;
  websocket?: string;
}

const loadConfig = async (): Promise<WebsiteConfig> => {
  try {
    const basePath = import.meta.env.BASE_URL || '/';
    const configPath = `${basePath}/config.json`.replace('//', '/');
    const response = await fetch(configPath);
    if (!response.ok) {
      throw new Error(`Failed to load config: ${response.status} ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error loading configuration:', error);
    return {
      title: "DMART Unified Data Platform",
      footer: "dmart.cc unified data platform",
      short_name: "dmart",
      display_name: "dmart",
      description: "dmart unified data platform",
      default_language: "ar",
      languages: { ar: "العربية", en: "English" },
      backend: "http://localhost:8282",
      websocket: "ws://0.0.0.0:8484/ws"
    };
  }
};

export let website: WebsiteConfig = {
  title: "DMART Unified Data Platform",
  footer: "dmart.cc unified data platform",
  short_name: "dmart",
  display_name: "dmart",
  description: "dmart unified data platform",
  default_language: "ar",
  languages: { ar: "العربية", en: "English" },
  backend: "http://localhost:8282",
  websocket: "ws://0.0.0.0:8484/ws"
};

loadConfig().then(config => {
  website = config;
});
