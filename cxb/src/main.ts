import {configReady} from './config';

// Wait for runtime config.json to load before mounting.
// Dynamic imports ensure all modules (i18n, stores, etc.) see the populated config.
configReady.then(async () => {
  const {mount} = await import('svelte');
  const {default: App} = await import('./App.svelte');
  mount(App, {
    target: document.body,
  });
});