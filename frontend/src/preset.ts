import { definePreset } from "@primeuix/themes";
import Aura from "@primeuix/themes/aura";

const AppPreset = definePreset(Aura, {
  components: {
    selectbutton: {
      css: () => `
        .p-selectbutton button {
          width: 100%;
        }

        .p-selectbutton .p-togglebutton:is(.p-highlight, .p-togglebutton-checked) .p-togglebutton-content {
          border-radius: var(--s-app-radius-sm);
        }
      `,
    },
    card: {
      css: () => `
        .p-card {
          border: 1px solid var(--s-content-border-color);
        }
      `,
    },
    formfield: {
      css: () => `
        .p-formfield {
          display: flex;
          flex-direction: column;
          gap: var(--s-app-space-2);
        }
      `,
    },
    inputtext: {
      css: () => `
        .p-inputtext:autofill,
        .p-password-input:autofill,
        .p-inputtext:-webkit-autofill,
        .p-inputtext:-webkit-autofill:hover,
        .p-inputtext:-webkit-autofill:focus,
        .p-inputtext:-webkit-autofill:active,
        .p-password-input:-webkit-autofill,
        .p-password-input:-webkit-autofill:hover,
        .p-password-input:-webkit-autofill:focus,
        .p-password-input:-webkit-autofill:active {
          -webkit-text-fill-color: var(--s-form-field-color);
          caret-color: var(--s-form-field-color);
          box-shadow: 0 0 0 2rem var(--s-form-field-background) inset;
          -webkit-box-shadow: 0 0 0 2rem var(--s-form-field-background) inset;
        }
      `,
    },
  },
  primitive: {
    borderRadius: {
      lg: "1rem",
      md: "0.75rem",
      sm: "0.5rem",
      xl: "1.25rem",
    },
  },
  semantic: {
    app: {
      radius: {
        lg: "{border.radius.lg}",
        md: "{border.radius.md}",
        sm: "{border.radius.sm}",
        xl: "{border.radius.xl}",
      },
      space: {
        1: "0.25rem",
        2: "0.5rem",
        3: "0.75rem",
        4: "1rem",
        5: "1.25rem",
        6: "1.5rem",
        8: "2rem",
        10: "2.5rem",
        12: "3rem",
      },
    },
    colorScheme: {
      dark: {
        app: {
          background: "{surface.950}",
        },
        content: {
          background: "{surface.900}",
          borderColor: "{surface.700}",
          color: "#d7e5ff",
          hoverBackground: "{surface.800}",
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
          0: "#f3f5f9",
          50: "#e1e5ee",
          100: "#c5ccda",
          200: "#9eaac1",
          300: "#7584a1",
          400: "#52627f",
          500: "#394864",
          600: "#26324a",
          700: "#1a2438",
          800: "#0f172a",
          900: "#0b1020",
          950: "#020617",
        },
      },
      light: {
        app: {
          background: "{surface.50}",
        },
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
