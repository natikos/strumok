<template>
  <div class="electricity-rates">
    <ul v-if="rates.length > 0" class="electricity-rates__list">
      <li v-for="rate in rates" :key="rate.id" class="electricity-rates__item">
        <span class="electricity-rates__period">{{ rate.effective_from }}</span>
        <span class="electricity-rates__values">
          {{ t("admin.dayRateShort") }} {{ formatUah(rate.day_rate_uah, currentLocale) }} ·
          {{ t("admin.nightRateShort") }} {{ formatUah(rate.night_rate_uah, currentLocale) }}
        </span>
      </li>
    </ul>
    <p v-else class="electricity-rates__empty">{{ t("admin.noRatesConfigured") }}</p>

    <div class="electricity-rates__field">
      <label class="electricity-rates__label" for="rate-effective-from">
        {{ t("admin.effectiveFrom") }}
      </label>
      <InputMask
        id="rate-effective-from"
        v-model="effectiveFrom"
        class="electricity-rates__input"
        mask="9999-99"
        :placeholder="t('admin.effectiveFromPlaceholder')"
        :invalid="!!errors.effectiveFrom"
        :disabled="isLoading"
        :pt="{
          root: {
            'aria-invalid': !!errors.effectiveFrom,
            'aria-describedby': errors.effectiveFrom ? 'rate-effective-from-error' : undefined,
          },
        }"
      />
      <span
        v-if="errors.effectiveFrom"
        id="rate-effective-from-error"
        role="alert"
        class="electricity-rates__field-error"
      >
        {{ t(errors.effectiveFrom) }}
      </span>
    </div>

    <div class="electricity-rates__field">
      <label class="electricity-rates__label" for="rate-day">{{ t("admin.dayRate") }}</label>
      <InputNumber
        id="rate-day"
        v-model="dayRateUah"
        class="electricity-rates__input"
        inputmode="decimal"
        :min-fraction-digits="2"
        :max-fraction-digits="4"
        :min="0"
        :invalid="!!errors.dayRateUah"
        :disabled="isLoading"
        :pt="{
          pcInputText: {
            root: {
              'aria-invalid': !!errors.dayRateUah,
              'aria-describedby': errors.dayRateUah ? 'rate-day-error' : undefined,
            },
          },
        }"
      />
      <span
        v-if="errors.dayRateUah"
        id="rate-day-error"
        role="alert"
        class="electricity-rates__field-error"
      >
        {{ t(errors.dayRateUah) }}
      </span>
    </div>

    <div class="electricity-rates__field">
      <label class="electricity-rates__label" for="rate-night">{{ t("admin.nightRate") }}</label>
      <InputNumber
        id="rate-night"
        v-model="nightRateUah"
        class="electricity-rates__input"
        inputmode="decimal"
        :min-fraction-digits="2"
        :max-fraction-digits="4"
        :min="0"
        :invalid="!!errors.nightRateUah"
        :disabled="isLoading"
        :pt="{
          pcInputText: {
            root: {
              'aria-invalid': !!errors.nightRateUah,
              'aria-describedby': errors.nightRateUah ? 'rate-night-error' : undefined,
            },
          },
        }"
      />
      <span
        v-if="errors.nightRateUah"
        id="rate-night-error"
        role="alert"
        class="electricity-rates__field-error"
      >
        {{ t(errors.nightRateUah) }}
      </span>
    </div>

    <p v-if="errors.form" class="electricity-rates__form-error" role="alert">
      {{ t(errors.form) }}
    </p>

    <Button
      class="electricity-rates__submit"
      :label="t('admin.addRate')"
      :loading="isLoading"
      @click="handleSubmit"
    />
  </div>
</template>

<script setup lang="ts">
  import { useToast } from "primevue/usetoast";
  import { onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";
  import { z } from "zod";

  import { useLocale } from "@features/i18n/composables/useLocale";
  import { ApiError } from "@shared/api/client";
  import {
    createElectricityRate,
    EFFECTIVE_FROM_ALREADY_EXISTS_ERROR_CODE,
    type ElectricityRateOut,
    listElectricityRates,
  } from "@shared/api/electricity-rates";
  import { formatUah } from "@shared/utils/format";

  interface FieldErrors {
    effectiveFrom?: string;
    dayRateUah?: string;
    nightRateUah?: string;
    form?: string;
  }

  const schema = z.object({
    effectiveFrom: z
      .string({ error: "admin.effectiveFromRequired" })
      .regex(/^\d{4}-(0[1-9]|1[0-2])$/, "admin.effectiveFromInvalid"),
    dayRateUah: z.number({ error: "admin.dayRateRequired" }).positive("admin.rateMustBePositive"),
    nightRateUah: z
      .number({ error: "admin.nightRateRequired" })
      .positive("admin.rateMustBePositive"),
  });

  const { t } = useI18n();
  const { currentLocale } = useLocale();
  const toast = useToast();

  const rates = ref<ElectricityRateOut[]>([]);
  const isLoading = ref(false);
  const errors = ref<FieldErrors>({});

  const effectiveFrom = ref("");
  const dayRateUah = ref<number | null>(null);
  const nightRateUah = ref<number | null>(null);

  onMounted(async () => {
    isLoading.value = true;

    try {
      rates.value = await listElectricityRates();
    } finally {
      isLoading.value = false;
    }
  });

  function resetForm(): void {
    effectiveFrom.value = "";
    dayRateUah.value = null;
    nightRateUah.value = null;
  }

  async function handleSubmit(): Promise<void> {
    errors.value = {};

    const parsed = schema.safeParse({
      effectiveFrom: effectiveFrom.value,
      dayRateUah: dayRateUah.value,
      nightRateUah: nightRateUah.value,
    });

    if (!parsed.success) {
      const flat = z.flattenError(parsed.error).fieldErrors;
      const next: FieldErrors = {};
      if (flat.effectiveFrom?.[0]) {
        next.effectiveFrom = flat.effectiveFrom[0];
      }
      if (flat.dayRateUah?.[0]) {
        next.dayRateUah = flat.dayRateUah[0];
      }
      if (flat.nightRateUah?.[0]) {
        next.nightRateUah = flat.nightRateUah[0];
      }
      errors.value = next;
      return;
    }

    isLoading.value = true;

    try {
      const rate = await createElectricityRate({
        day_rate_uah: parsed.data.dayRateUah.toString(),
        night_rate_uah: parsed.data.nightRateUah.toString(),
        effective_from: parsed.data.effectiveFrom,
      });

      rates.value = [...rates.value, rate].sort((a, b) =>
        b.effective_from.localeCompare(a.effective_from)
      );

      toast.add({
        life: 4000,
        severity: "success",
        summary: t("admin.addRateSuccess", { period: rate.effective_from }),
      });

      resetForm();
    } catch (error) {
      if (error instanceof ApiError && error.message === EFFECTIVE_FROM_ALREADY_EXISTS_ERROR_CODE) {
        errors.value = { form: "admin.effectiveFromAlreadyExists" };
      } else if (error instanceof Error) {
        console.error(error);
        errors.value = { form: "errors.requestFailed" };
      }
    } finally {
      isLoading.value = false;
    }
  }
</script>

<style scoped lang="scss">
  .electricity-rates {
    @include layout.stack(var(--s-app-space-4));
  }

  .electricity-rates__list {
    @include layout.stack(var(--s-app-space-2));
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .electricity-rates__item {
    @include layout.stack(var(--s-app-space-1));
    font-size: 0.85rem;
    min-width: 0;

    @include layout.respond-to("sm") {
      @include layout.row(var(--s-app-space-3), center, space-between);
    }
  }

  .electricity-rates__period {
    color: var(--s-content-color);
    font-weight: 500;
  }

  .electricity-rates__values {
    color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    min-width: 0;
    text-align: left;

    @include layout.respond-to("sm") {
      text-align: right;
    }
  }

  .electricity-rates__empty {
    color: color-mix(in srgb, var(--s-content-color), transparent 45%);
    font-size: 0.85rem;
    margin: 0;
  }

  .electricity-rates__field {
    @include layout.stack(var(--s-app-space-2));
  }

  .electricity-rates__label {
    color: var(--s-content-color);
    font-size: 0.85rem;
    font-weight: 500;
  }

  .electricity-rates__input {
    min-width: 0;
    width: 100%;
  }

  .electricity-rates__field-error {
    font-size: 0.75rem;
    color: var(--s-red-500);
  }

  .electricity-rates__form-error {
    margin: 0;
    padding: var(--s-app-space-2);
    border-radius: var(--s-app-radius-sm);
    background: color-mix(in srgb, var(--s-red-500), transparent 88%);
    font-size: 0.78rem;
    color: var(--s-red-700);
  }

  .electricity-rates__submit {
    width: 100%;
  }
</style>
