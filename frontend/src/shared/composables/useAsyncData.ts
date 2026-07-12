import { ref } from "vue";

export interface AsyncDataState<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
}

export function useAsyncData<T>(
  asyncFn: () => Promise<T>,
  immediate = true
) {
  const data = ref<T | null>(null);
  const isLoading = ref(immediate);
  const error = ref<Error | null>(null);

  async function execute(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      data.value = await asyncFn();
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
    } finally {
      isLoading.value = false;
    }
  }

  if (immediate) {
    void execute();
  }

  return { data, isLoading, error, execute };
}
