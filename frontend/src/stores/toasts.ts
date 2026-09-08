import { ref } from "vue";
import { defineStore } from "pinia";

export type ToastKind = "success" | "error";

export interface ToastMessage {
  id: number;
  title: string;
  description?: string;
  kind: ToastKind;
  duration: number;
}

interface ToastInput {
  title: string;
  description?: string;
}

let nextToastId = 1;

export const useToastStore = defineStore("toasts", () => {
  const messages = ref<ToastMessage[]>([]);

  function add(kind: ToastKind, input: ToastInput): number {
    const id = nextToastId++;
    messages.value.push({
      id,
      kind,
      duration: kind === "success" ? 4_000 : 8_000,
      ...input,
    });
    return id;
  }

  function success(input: ToastInput): number {
    return add("success", input);
  }

  function error(input: ToastInput): number {
    return add("error", input);
  }

  function remove(id: number): void {
    messages.value = messages.value.filter((message) => message.id !== id);
  }

  return { error, messages, remove, success };
});
