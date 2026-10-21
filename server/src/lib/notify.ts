import { col } from "./store.js";

export async function notify(input: {
  userId: string;
  type: string;
  title: string;
  body: string;
  meta?: Record<string, unknown>;
}) {
  return col("notifications").create({
    ...input,
    read: false,
  });
}
