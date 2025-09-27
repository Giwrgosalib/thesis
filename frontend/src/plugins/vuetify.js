/* eslint-disable prettier/prettier */
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";

export default createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: "ebayTheme",
    themes: {
      ebayTheme: {
        dark: false,
        colors: {
          // eBay Brand Colors
          'ebay-red': '#e53238',
          'ebay-blue': '#0064d2', 
          'ebay-yellow': '#f5af02',
          'ebay-green': '#86b817',
          
          // Vuetify Standard Colors
          primary: '#e53238', // eBay Red
          secondary: '#0064d2', // eBay Blue
          accent: '#86b817', // eBay Green
          error: '#e53238', // eBay Red for errors
          info: '#0064d2', // eBay Blue for info
          success: '#86b817', // eBay Green for success
          warning: '#f5af02', // eBay Yellow for warnings
          
          // Background and Surface
          background: '#f8f9fa',
          surface: '#ffffff',
          
          // Text Colors
          'on-primary': '#ffffff',
          'on-secondary': '#ffffff', 
          'on-background': '#2c2c2c',
          'on-surface': '#2c2c2c',
          'on-error': '#ffffff',
          'on-info': '#ffffff',
          'on-success': '#ffffff',
          'on-warning': '#2c2c2c',
        },
      },
    },
  },
});
