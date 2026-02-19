<template>
  <div class="demo-page">
    <header class="demo-page__header">
      <img class="demo-page__logo" src="/logo.svg" alt="Strumok Logo" />

      <div class="demo-page__controls">
        <Button
          :label="languageLabel"
          variant="text"
          rounded
          :aria-label="languageAriaLabel"
          :title="languageAriaLabel"
          @click="toggleLocale"
        />
        <Button
          :icon="themeIcon"
          variant="text"
          rounded
          :aria-label="themeAriaLabel"
          :title="themeAriaLabel"
          @click="toggleTheme"
        />
      </div>
    </header>

    <main class="demo-page__content">
      <h1>PrimeVue Theme Demo</h1>
      <p>Toggle theme and locale to preview component tokens in light and dark modes.</p>

      <section class="demo-grid">
        <Card>
          <template #title>Inputs</template>
          <template #content>
            <div class="demo-stack">
              <InputText v-model="form.email" placeholder="Email" type="email" />
              <Password
                v-model="form.password"
                input-class="w-full"
                placeholder="Password"
                toggle-mask
                :feedback="false"
              />
              <Textarea v-model="form.notes" rows="3" placeholder="Notes" />
              <Select
                v-model="form.role"
                :options="roleOptions"
                option-label="label"
                option-value="value"
                placeholder="Select role"
              />
              <div class="demo-row">
                <Checkbox v-model="form.active" binary input-id="active" />
                <label for="active">Active account</label>
              </div>
              <div class="demo-row">
                <RadioButton v-model="form.plan" input-id="starter" value="starter" />
                <label for="starter">Starter</label>
                <RadioButton v-model="form.plan" input-id="pro" value="pro" />
                <label for="pro">Pro</label>
              </div>
              <Slider v-model="form.quota" :max="100" />
            </div>
          </template>
        </Card>

        <Card>
          <template #title>Actions & Status</template>
          <template #content>
            <div class="demo-stack">
              <div class="demo-actions">
                <Button label="Primary" />
                <Button label="Secondary" severity="secondary" />
                <Button label="Success" severity="success" />
                <Button label="Danger" severity="danger" />
              </div>
              <div class="demo-actions">
                <Tag value="New" />
                <Tag value="In review" severity="warn" />
                <Tag value="Done" severity="success" />
              </div>
              <div class="demo-actions">
                <Chip label="Design" />
                <Chip label="Frontend" />
                <Chip label="Backend" />
              </div>
              <Button label="Open dialog" variant="outlined" @click="isDialogVisible = true" />
            </div>
          </template>
        </Card>

        <Card>
          <template #title>Feedback</template>
          <template #content>
            <div class="demo-stack">
              <Message severity="info">Informational message example.</Message>
              <Message severity="warn">Warning message example.</Message>
              <ProgressBar :value="68" />
            </div>
          </template>
        </Card>

        <Card>
          <template #title>Data Table</template>
          <template #content>
            <DataTable :value="users" table-style="min-width: 24rem">
              <Column field="name" header="Name"></Column>
              <Column field="role" header="Role"></Column>
              <Column field="status" header="Status"></Column>
            </DataTable>
          </template>
        </Card>
      </section>
    </main>

    <Dialog v-model:visible="isDialogVisible" header="Preview Dialog" modal :style="{ width: '28rem' }">
      <p>
        This dialog uses your current semantic tokens. Switch themes to compare surfaces, text, borders, and
        focus states.
      </p>
      <template #footer>
        <Button label="Close" variant="text" @click="isDialogVisible = false" />
        <Button label="Confirm" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { useTheme } from "@/features/theme/composables/useTheme";
  import Button from "primevue/button";
  import Card from "primevue/card";
  import Checkbox from "primevue/checkbox";
  import Chip from "primevue/chip";
  import Column from "primevue/column";
  import DataTable from "primevue/datatable";
  import Dialog from "primevue/dialog";
  import InputText from "primevue/inputtext";
  import Message from "primevue/message";
  import Password from "primevue/password";
  import ProgressBar from "primevue/progressbar";
  import RadioButton from "primevue/radiobutton";
  import Select from "primevue/select";
  import Slider from "primevue/slider";
  import Tag from "primevue/tag";
  import Textarea from "primevue/textarea";
  import { computed, ref } from "vue";
  import { useI18n } from "vue-i18n";

  interface DemoUser {
    name: string;
    role: string;
    status: string;
  }

  interface DemoFormState {
    active: boolean;
    email: string;
    notes: string;
    password: string;
    plan: "starter" | "pro";
    quota: number;
    role: string | null;
  }

  const { t } = useI18n();
  const { currentLocale, toggleLocale } = useLocale();
  const { theme, toggleTheme } = useTheme();

  const isDialogVisible = ref(false);

  const roleOptions = [
    { label: "Viewer", value: "viewer" },
    { label: "Editor", value: "editor" },
    { label: "Admin", value: "admin" },
  ];

  const users = ref<DemoUser[]>([
    { name: "Olivia Reed", role: "Admin", status: "Active" },
    { name: "Ethan Cole", role: "Editor", status: "Invited" },
    { name: "Mila Hart", role: "Viewer", status: "Suspended" },
  ]);

  const form = ref<DemoFormState>({
    active: true,
    email: "",
    notes: "",
    password: "",
    plan: "starter",
    quota: 42,
    role: null,
  });

  const themeIcon = computed(() => (theme.value === "dark" ? "pi pi-moon" : "pi pi-sun"));

  const themeAriaLabel = computed(() =>
    theme.value === "dark" ? t("layout.switchToLightTheme") : t("layout.switchToDarkTheme")
  );

  const languageLabel = computed(() => (currentLocale.value === "ua" ? "UA" : "EN"));

  const languageAriaLabel = computed(() =>
    currentLocale.value === "ua" ? t("layout.switchToEnglish") : t("layout.switchToUkrainian")
  );
</script>

<style scoped lang="scss">
  .demo-page {
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--s-primary-color), transparent 92%),
        transparent 45%
      ),
      var(--s-surface-100);
    color: var(--s-text-color);
    min-height: 100vh;
    padding: var(--space-4);
  }

  .demo-page__header {
    align-items: center;
    display: flex;
    justify-content: space-between;
    margin: 0 auto;
    max-width: 72rem;
  }

  .demo-page__logo {
    display: block;
    height: auto;
    max-width: clamp(8rem, 7rem + 6vw, 11rem);
    width: 100%;
  }

  .demo-page__controls {
    align-items: center;
    display: flex;
    gap: var(--space-2);
  }

  .demo-page__content {
    margin: var(--space-8) auto 0;
    max-width: 72rem;
  }

  .demo-page__content > h1 {
    font-size: var(--font-size-xl);
    margin: 0;
  }

  .demo-page__content > p {
    color: var(--s-text-muted-color);
    margin: var(--space-2) 0 var(--space-6);
  }

  .demo-grid {
    display: grid;
    gap: var(--space-4);
    grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  }

  .demo-stack {
    display: grid;
    gap: var(--space-3);
  }

  .demo-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .demo-row {
    align-items: center;
    display: flex;
    gap: var(--space-2);
  }

</style>
