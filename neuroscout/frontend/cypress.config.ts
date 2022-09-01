import { defineConfig } from 'cypress'

export default defineConfig({
  projectId: 'jfpnqv',
  retries: {
    runMode: 1,
    openMode: 1,
  },
  defaultCommandTimeout: 30000,
  pageLoadTimeout: 180000,
  requestTimeout: 30000,
  e2e: {
    // We've imported your old cypress plugins here.
    // You may want to clean this up later by importing these.
    setupNodeEvents(on, config) {
      return require('./cypress/plugins/index.js')(on, config)
    },
    baseUrl: 'https://localhost:3000',
    specPattern: 'cypress/e2e/**/*.{js,jsx,ts,tsx}',
  },
})
