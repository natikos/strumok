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
    toast: {
      css: () => `
        .p-toast .p-toast-message .p-toast-message-content {
          align-items: center;
        }

        .p-toast .p-toast-message .p-toast-message-text {
          display: flex;
          flex: 1;
          justify-content: center;
          margin: 0;
          min-height: 2rem;
        }

        .p-toast .p-toast-message .p-toast-summary {
          line-height: 1.2;
          margin: 0;
        }

        .p-toast .p-toast-message .p-toast-close-button {
          align-self: center;
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
          background: "{surface.800}",
        },
        shell: {
          background: "{content.background}",
          borderColor: "transparent",
          itemHoverBackground: "{content.hoverBackground}",
        },
        content: {
          background: "{surface.900}",
          borderColor: "{surface.700}",
          color: "{surface.50}",
          hoverBackground: "{surface.800}",
          hoverColor: "{surface.0}",
          shadow:
            "0 1px 2px color-mix(in srgb, {surface.950}, transparent 65%), 0 10px 24px color-mix(in srgb, {surface.950}, transparent 76%)",
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
        shell: {
          background:
            "linear-gradient(to top left, var(--s-primary-900) 0%, var(--s-primary-100) 60%)",
          borderColor: "{surface.200}",
          itemHoverBackground: "{surface.200}",
        },
        content: {
          background: "{surface.0}",
          borderColor: "{surface.200}",
          color: "{surface.900}",
          hoverBackground: "{surface.100}",
          hoverColor: "{surface.800}",
          shadow: "0 1px 2px {surface.100}, 0 10px 28px {surface.100}",
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
          0: "#f4f9ff",
          50: "#e9f2ff",
          100: "#dce9fb",
          200: "#c4d9f2",
          300: "#a8c5e6",
          400: "#86abcf",
          500: "#658fb5",
          600: "#4b7195",
          700: "#375878",
          800: "#29435c",
          900: "#1d2f42",
          950: "#13202f",
        },
      },
    },
    primary: {
      50: "#eaf3ff",
      100: "#cfe1ff",
      200: "#a8c6f0",
      300: "#7eabd8",
      400: "#5f92c0",
      500: "#3f79a8",
      600: "#1f5f87",
      700: "#003566",
      800: "#002b52",
      900: "#00223f",
      950: "#00172b",
    },
  },
});

export default AppPreset;
