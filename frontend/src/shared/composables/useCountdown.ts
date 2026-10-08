import { computed, onBeforeUnmount, ref } from "vue";

export function useCountdown() {
  const seconds = ref(0);
  let timer: ReturnType<typeof setInterval> | null = null;

  const formatted = computed(() => {
    const minutes = Math.floor(seconds.value / 60);
    const rest = seconds.value % 60;
    return `${minutes.toString().padStart(2, "0")}:${rest.toString().padStart(2, "0")}`;
  });

  function stop(): void {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function start(fromSeconds: number): void {
    stop();
    seconds.value = fromSeconds;

    timer = setInterval(() => {
      if (seconds.value <= 1) {
        seconds.value = 0;
        stop();
        return;
      }

      seconds.value -= 1;
    }, 1000);
  }

  onBeforeUnmount(stop);

  return { formatted, seconds, start };
}
