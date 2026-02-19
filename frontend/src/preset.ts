import { definePreset } from "@primeuix/themes";
import Aura from "@primeuix/themes/aura";

const AppPreset = definePreset(Aura, {
  semantic: {
    colorScheme: {
      dark: {
        content: {
          background: "#0f172a",
          borderColor: "#26324a",
          color: "#d7e5ff",
          hoverBackground: "#17213a",
          hoverColor: "#f1f6ff",
        },
        highlight: {
          background: "color-mix(in srgb, {primary.400}, transparent 84%)",
          color: "rgba(255,255,255,0.87)",
          focusBackground: "color-mix(in srgb, {primary.400}, transparent 76%)",
          focusColor: "rgba(255,255,255,0.87)",
        },
        primary: {
          activeColor: "{primary.700}",
          color: "{primary.400}",
          hoverColor: "{primary.400}",
          inverseColor: "#ffffff",
        },
        surface: {
          0: "#020617",
          50: "#0b1020",
          100: "#0f172a",
          200: "#1a2438",
          300: "#26324a",
          400: "#394864",
          500: "#52627f",
          600: "#7584a1",
          700: "#9eaac1",
          800: "#c5ccda",
          900: "#e1e5ee",
          950: "#f3f5f9",
        },
      },
      light: {
        content: {
          background: "#ffffff",
          borderColor: "#d5e0ea",
          color: "#1f2d3a",
          hoverBackground: "#f4f8fc",
          hoverColor: "#18232e",
        },
        highlight: {
          background: "{primary.50}",
          color: "{primary.700}",
          focusBackground: "{primary.100}",
          focusColor: "{primary.800}",
        },
        primary: {
          activeColor: "{primary.800}",
          color: "{primary.600}",
          hoverColor: "{primary.700}",
          inverseColor: "#ffffff",
        },
        surface: {
          0: "#ffffff",
          50: "#f4f8fc",
          100: "#edf3f8",
          200: "#d5e0ea",
          300: "#b7c8d8",
          400: "#90abc0",
          500: "#6a88a3",
          600: "#4f6d85",
          700: "#3b5569",
          800: "#2c4253",
          900: "#1f2d3a",
          950: "#151f28",
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
      50: "#eff6ff",
      100: "#dbeafe",
      200: "#bfdbfe",
      300: "#93c5fd",
      400: "#60a5fa",
      500: "#3b82f6",
      600: "#2563eb",
      700: "#1d4ed8",
      800: "#1e40af",
      900: "#1e3a8a",
      950: "#172554",
    },
  },
});

export default AppPreset;
