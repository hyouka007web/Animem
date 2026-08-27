import UserMention from "./UserMention";

// Erkennt @handle-Erwähnungen in einem Text und macht sie klickbar (Long-Press-Menü),
// der Rest des Textes bleibt normaler Fließtext.
export default function MentionText({ text }: { text: string }) {
  const parts = text.split(/(@[a-zA-Z0-9_]+)/g);

  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("@") && part.length > 1 ? (
          <UserMention key={i} username={part.slice(1)} showAt />
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}
