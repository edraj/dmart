#!/bin/bash

# Basic setup
npx @roxi/routify@next create frontend
cd frontend
npm install
npm run dev

# Add typescript support
npm install svelte-preprocess # Adds 26 new packages
npm install typescript # Adds 1 package
mv src/main.js src/main.ts
sed -i 's/main.js/main.ts/g' index.html

sed -i "1i import preprocess from 'svelte-preprocess'" vite.config.js
sed -i "s/preprocess: \[/preprocess: [ preprocess(), /g" vite.config.js

# Install Sveltestrap with bootstrap and icons
npm install bootstrap
npm install bootstrap-icons
npm install sveltestrap


# I18N
npm install svelte-i18n # Adds 36 packages


# Notifications
npm install svelte-notifications
