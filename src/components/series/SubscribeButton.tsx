"use client";

import { useState } from "react";
import { Bell, BellOff } from "lucide-react";

export default function SubscribeButton({
  seriesId,
  initiallySubscribed,
}: {
  seriesId: string;
  initiallySubscribed: boolean;
}) {
  const [subscribed, setSubscribed] = useState(initiallySubscribed);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    setLoading(true);
    const res = await fetch("/api/subscriptions", {
      method: subscribed ? "DELETE" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seriesId }),
    });
    if (res.ok) setSubscribed(!subscribed);
    setLoading(false);
  }

  return (
    <button
      onClick={toggle}
      disabled={loading}
      className="flex items-center gap-2 rounded-lg border border-white/10 bg-neutral-800 px-4 py-2 text-sm font-medium hover:bg-neutral-700 disabled:opacity-50"
    >
      {subscribed ? <BellOff className="h-4 w-4" /> : <Bell className="h-4 w-4" />}
      {subscribed ? "Abonniert" : "Abonnieren"}
    </button>
  );
}
