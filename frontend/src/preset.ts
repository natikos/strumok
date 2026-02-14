import { definePreset } from "@primeuix/themes";
import Aura from "@primeuix/themes/aura";

const AppPreset = definePreset(Aura, {
  semantic: {
    colorScheme: {
      dark: {
        content: {
          background: "#1e293b",
          borderColor: "#475569",
          color: "rgba(255,255,255,0.87)",
          hoverBackground: "#334155",
          hoverColor: "rgba(255,255,255,0.95)",
        },
        highlight: {
          background: "color-mix(in srgb, {blue.400}, transparent 84%)",
          color: "rgba(255,255,255,.87)",
          focusBackground: "color-mix(in srgb, {blue.400}, transparent 76%)",
          focusColor: "rgba(255,255,255,.87)",
        },
        layout: {
          cardBackground: "#0f1b43",
          cardBorder: "#1f315d",
          chromeBackground: "#0f1b43",
          chromeText: "#e6eefb",
          contentBackground: "#020b2e",
          iconButtonBackground: "#172850",
          panelBackground: "#0f1b43",
          panelBorder: "#1f315d",
        },
        primary: {
          activeColor: "{blue.200}",
          color: "{blue.400}",
          hoverColor: "{blue.300}",
          inverseColor: "{slate.950}",
        },
        surface: {
          0: "#1e293b", // slate-800 - comfortable dark background
          50: "#334155", // slate-700
          100: "#475569", // slate-600
          200: "#64748b", // slate-500
          300: "#94a3b8", // slate-400
          400: "#cbd5e1", // slate-300
          500: "#e2e8f0", // slate-200
          600: "#f1f5f9", // slate-100
          700: "#f8fafc", // slate-50
          800: "#0f172a", // slate-900 - deeper backgrounds
          900: "#020617", // slate-950 - deepest
          950: "#0a0f1e", // custom very dark slate-blue
        },
      },
      light: {
        content: {
          background: "#ffffff",
          borderColor: "{slate.200}",
          color: "{slate.700}",
          hoverBackground: "{slate.50}",
          hoverColor: "{slate.800}",
        },
        highlight: {
          background: "{blue.50}",
          color: "{blue.700}",
          focusBackground: "{blue.100}",
          focusColor: "{blue.800}",
        },
        layout: {
          cardBackground: "{content.background}",
          cardBorder: "{content.border.color}",
          chromeBackground: "linear-gradient(120deg, {primary.400}, {primary.600})",
          chromeText: "{primary.contrast.color}",
          contentBackground: "{surface.100}",
          iconButtonBackground: "color-mix(in srgb, #ffffff, transparent 14%)",
          panelBackground: "{content.background}",
          panelBorder: "{content.border.color}",
        },
        primary: {
          activeColor: "{blue.800}",
          color: "{blue.600}",
          hoverColor: "{blue.700}",
          inverseColor: "#ffffff",
        },
        surface: {
          0: "#ffffff",
          50: "{slate.50}",
          100: "{slate.100}",
          200: "{slate.200}",
          300: "{slate.300}",
          400: "{slate.400}",
          500: "{slate.500}",
          600: "{slate.600}",
          700: "{slate.700}",
          800: "{slate.800}",
          900: "{slate.900}",
          950: "{slate.950}",
        },
      },
    },
    formField: {
      borderRadius: "{border.radius.md}",
      focusRing: {
        color: "{primary.color}",
        offset: "-1px",
        shadow: "none",
        style: "solid",
        width: "2px",
      },
      paddingX: "0.75rem",
      paddingY: "0.625rem",
      transitionDuration: "{transition.duration}",
    },

    primary: {
      50: "{blue.50}",
      100: "{blue.100}",
      200: "{blue.200}",
      300: "{blue.300}",
      400: "{blue.400}",
      500: "{blue.500}",
      600: "{blue.600}",
      700: "{blue.700}",
      800: "{blue.800}",
      900: "{blue.900}",
      950: "{blue.950}",
    },
  },
});

export default AppPreset;
