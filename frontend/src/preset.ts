import { definePreset } from "@primeuix/themes";
import Aura from "@primeuix/themes/aura";

const AppPreset = definePreset(Aura, {
  semantic: {
    colorScheme: {
      dark: {
        content: {
          background: "#0f1822",
          borderColor: "#26384b",
          color: "#d7e4f1",
          hoverBackground: "#172433",
          hoverColor: "#eef4fb",
        },
        highlight: {
          background: "color-mix(in srgb, {primary.400}, transparent 82%)",
          color: "rgba(255,255,255,0.87)",
          focusBackground: "color-mix(in srgb, {primary.400}, transparent 74%)",
          focusColor: "rgba(255,255,255,0.87)",
        },
        primary: {
          activeColor: "{primary.700}",
          color: "{primary.500}",
          hoverColor: "{primary.400}",
          inverseColor: "#ffffff",
        },
        surface: {
          0: "#0f1822",
          50: "#152131",
          100: "#1c2b3d",
          200: "#26384b",
          300: "#32475c",
          400: "#48637d",
          500: "#6a88a3",
          600: "#8fa4b6",
          700: "#b5c2cf",
          800: "#d2dce5",
          900: "#e9eff5",
          950: "#f6f9fc",
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
