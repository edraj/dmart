interface WebsiteConfig {
  title: string;
  footer: string;
  short_name: string;
  display_name: string;
  description: string;
  default_language: string;
  languages: Record<string, string>;
  backend: string;
  backend_timeout: number;
  websocket?: string;
  delay_total_count?: boolean;
  theme?: {
    type: "solid" | "gradient";
    value: string;
  };
}

const loadConfig = async (): Promise<WebsiteConfig> => {
  try {
    const configUrl = new URL('config.json', document.baseURI).href;
    const response = await fetch(configUrl);
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
      websocket: "ws://localhost:8484/ws",
      backend_timeout: 30000,
      delay_total_count: false
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
  websocket: "ws://localhost:8484/ws",
  backend_timeout: 30000,
  delay_total_count: false
};

export const configReady: Promise<void> = loadConfig().then(config => {
  website = config;
});
