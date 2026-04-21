const { defineConfig } = require("@vue/cli-service");
module.exports = defineConfig({
  transpileDependencies: true,

  pluginOptions: {
    vuetify: {
      // https://github.com/vuetifyjs/vuetify-loader/tree/next/packages/vuetify-loader
    },
  },

  devServer: {
    host: "0.0.0.0",
    port: 8080,
    allowedHosts: "all",
    client: {
      webSocketURL: "auto://0.0.0.0:0/ws",
    },
    proxy: {
      // NextGen routes must come BEFORE the catch-all /api rule
      "^/api/nextgen": {
        target: "http://backend:5001",
        changeOrigin: true,
      },
      // Legacy backend routes
      "^/api": {
        target: "http://backend:5000",
        changeOrigin: true,
      },
      "^/auth": {
        target: "http://backend:5000",
        changeOrigin: true,
      },
      "^/health": {
        target: "http://backend:5000",
        changeOrigin: true,
      },
    },
  },
});
