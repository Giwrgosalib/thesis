import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";

export default createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: "ebayTheme", // Set the default theme
    themes: {
      ebayTheme: {
        dark: false, // Light theme
        colors: {
          primary: "#E53238", // eBay Red
          secondary: "#0064D2", // eBay Blue
          accent: "#86B817", // eBay Green
          error: "#FF5252", // Default error color
          info: "#2196F3", // Default info color
          success: "#4CAF50", // Default success color
          warning: "#F5AF02", // eBay Yellow
          background: "#FFFFFF", // White background
          surface: "#FFFFFF", // White surface
          "on-primary": "#FFFFFF", // Text on primary color (white)
          "on-secondary": "#FFFFFF", // Text on secondary color (white)
          "on-background": "#333333", // Text on background (eBay Gray)
          "on-surface": "#333333", // Text on surface (eBay Gray)
        },
      },
    },
  },
});
